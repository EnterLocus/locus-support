"""Shared RealityKit Room binding check used by both public validators.

The Swift source exists once (tools/room-bindings/). The flat validator and
the Package v2 validator both compile it with `xcrun --sdk macosx swiftc` and
must reject a Room whose metadata names an entity the model does not contain,
exactly like Locus's import. Fixtures are generated from source.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SKILL_SCRIPTS = ROOT / ".agents" / "skills" / "build-original-locus-room" / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(TOOLS))

import room_bindings  # noqa: E402
import room_fixtures  # noqa: E402

HAS_REALITYKIT = platform.system() == "Darwin" and shutil.which("xcrun") is not None


def typo(room):
    adaptation = room.space["spatialAdaptation"]
    adaptation["deskEntitiesByTeleportID"][room_fixtures.SEAT_ID] = "Table_Top_TYPO"
    adaptation["roofEntities"] = ["Roof_MISSING"]


class SharedSourceTests(unittest.TestCase):
    def test_swift_source_exists_once(self):
        for validator in ("validate_locus_asset.py", "validate_locusplace.py"):
            source = (TOOLS / validator).read_text(encoding="utf-8")
            with self.subTest(validator=validator):
                self.assertNotIn("enum RoomEntityBindings", source)
                self.assertNotIn("import RealityKit", source)
                self.assertIn("room_bindings", source)
        definitions = [
            path.relative_to(ROOT) for path in TOOLS.rglob("*.swift")
            if not path.is_symlink()
            and "enum RoomEntityBindings" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(definitions, [Path("tools/room-bindings/RoomBindings.swift")])

    def test_skill_bundles_a_byte_identical_copy(self):
        for relative in ("validate_locus_asset.py", "room_bindings.py",
                         *("room-bindings/" + name for name in room_bindings.SWIFT_SOURCES)):
            with self.subTest(relative=relative):
                self.assertEqual((SKILL_SCRIPTS / relative).read_bytes(),
                                 (TOOLS / relative).read_bytes())

    def test_compiles_against_the_macos_sdk(self):
        command = room_bindings.compile_command(Path("/tmp/out"))
        self.assertEqual(command[:5], ["xcrun", "--sdk", "macosx", "swiftc", "-parse-as-library"])

    def test_reference_fields_match_the_swift_contract(self):
        swift = (TOOLS / "room-bindings" / "RoomBindings.swift").read_text(encoding="utf-8")
        contract = swift[swift.index("struct RoomModelBindingContract"):]
        contract = contract[:contract.index("var textureFlowNames")]
        declared = {
            line.split("let ", 1)[1].split(":", 1)[0]
            for line in contract.splitlines()
            if line.startswith("    let ")
        }
        self.assertEqual(declared, set(room_bindings.ENTITY_REFERENCE_FIELDS))
        self.assertFalse(room_bindings.references_entities({"title": "Room"}))
        self.assertTrue(room_bindings.references_entities({"lighting": {}}))


@unittest.skipUnless(HAS_REALITYKIT, "RealityKit binding check requires macOS with Xcode")
class BindingCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-binding-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def run_tool(self, *arguments):
        return subprocess.run([sys.executable, *map(str, arguments)],
                              capture_output=True, text=True)

    def validate_v2(self, archive):
        return self.run_tool(TOOLS / "validate_locusplace.py",
                             "--current-app-version", "1.4.4", archive)

    def test_minimal_room_passes_in_both_formats(self):
        room = room_fixtures.minimal_room()
        flat = self.run_tool(TOOLS / "validate_locus_asset.py",
                             room.write_flat(self.root / "minimal.zip"))
        self.assertEqual(flat.returncode, 0, flat.stdout + flat.stderr)
        v2 = self.validate_v2(room.write_v2(self.root / "minimal.locusplace"))
        self.assertEqual(v2.returncode, 0, v2.stdout + v2.stderr)

    def test_flat_entity_typo_fails_with_the_name(self):
        room = room_fixtures.minimal_room(typo)
        result = self.run_tool(TOOLS / "validate_locus_asset.py",
                               room.write_flat(self.root / "typo.zip"))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("INVALID", result.stderr)
        self.assertIn("Room entity 'Roof_MISSING' was not found.", result.stderr)

    def test_v2_entity_typo_fails_with_the_name(self):
        room = room_fixtures.minimal_room(typo)
        result = self.validate_v2(room.write_v2(self.root / "typo.locusplace"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("INVALID", result.stderr)
        self.assertIn("Room entity 'Roof_MISSING' was not found.", result.stderr)

        # Only the desk typo: the error names the desk entity instead.
        def desk_only(room):
            room.space["spatialAdaptation"]["deskEntitiesByTeleportID"][
                room_fixtures.SEAT_ID] = "Table_Top_TYPO"
        archive = room_fixtures.minimal_room(desk_only).write_v2(self.root / "desk.locusplace")
        result = self.validate_v2(archive)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Room entity 'Table_Top_TYPO' was not found.", result.stderr)

    def test_v2_packer_refuses_an_entity_typo(self):
        archive = room_fixtures.minimal_room(typo).write_v2(self.root / "typo.locusplace")
        editable = self.root / "editable"
        with zipfile.ZipFile(archive) as source:
            source.extractall(editable)
        envelope = json.loads((editable / "locusplace.json").read_text())
        for field in ("files", "contentHash"):
            envelope.pop(field)
        (editable / "locusplace.json").write_text(json.dumps(envelope))
        output = self.root / "packed.locusplace"
        result = self.run_tool(TOOLS / "pack_locusplace.py",
                               "--current-app-version", "1.4.4", editable, output)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Roof_MISSING", result.stderr)
        self.assertFalse(output.exists())

    def test_v2_rendering_subtrees_and_duplicates_match_the_app(self):
        def duplicate(room):
            room.boxes.append(dict(room.box("Roof"), name="Chair_Seat", parent="Roof"))
        result = self.validate_v2(
            room_fixtures.minimal_room(duplicate).write_v2(self.root / "dup.locusplace"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Room entity 'Chair_Seat' is not uniquely named.", result.stderr)

        def overlap(room):
            room.boxes.append(dict(room.box("Roof"), name="Table_Inlay", parent="Table_Top"))
            room.space["rendering"]["uiFadeEntities"].append("Table_Inlay")
        result = self.validate_v2(
            room_fixtures.minimal_room(overlap).write_v2(self.root / "overlap.locusplace"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("overlap in the model hierarchy", result.stderr)

        def empty_group(room):
            room.boxes.append({"name": "Empty_Group", "shape": "group",
                               "center": (0, 0, 0), "size": (0, 0, 0)})
            room.space["rendering"]["softenedReflectionEntities"] = ["Empty_Group"]
        result = self.validate_v2(
            room_fixtures.minimal_room(empty_group).write_v2(self.root / "empty.locusplace"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Room entity 'Empty_Group' has no renderable geometry.", result.stderr)

    def test_v2_room_without_entity_references_skips_realitykit(self):
        def unbound(room):
            for field in ("spatialAdaptation", "lighting", "rendering"):
                room.space.pop(field)
        room = room_fixtures.minimal_room(unbound)
        result = self.validate_v2(room.write_v2(self.root / "unbound.locusplace"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
