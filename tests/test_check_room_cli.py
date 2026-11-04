"""End-to-end command-line checks for the public Room checker.

These use source-generated USDZ archives and invoke ``tools/check_room.py``
as an author would.  The checker therefore performs its real Package/flat
validation, RealityKit binding load, and entry-condition inspection; this
module has no test-only checker seam or substitute implementation.
"""

from __future__ import annotations

import json
import platform
import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from tests import room_fixtures


ROOT = Path(__file__).resolve().parents[1]
CHECK_ROOM = ROOT / "tools" / "check_room.py"


def introduce_binding_typo(room: room_fixtures.Room) -> None:
    room.space["spatialAdaptation"]["deskEntitiesByTeleportID"][
        room_fixtures.SEAT_ID
    ] = "Table_Top_TYPO"


@unittest.skipUnless(
    platform.system() == "Darwin",
    "Room checking requires macOS RealityKit; no reduced validation is provided",
)
class CheckRoomCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-check-room-cli-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_checker(self, archive: Path, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(CHECK_ROOM),
                str(archive),
                "--current-app-version",
                "1.4.4",
                "--json",
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=360,
        )

    def assert_valid(self, archive: Path) -> dict:
        result = self.run_checker(archive)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["layers"], ["S", "B", "E", "W"])
        self.assertEqual(len(report["rooms"]), 1)
        return report

    def assert_binding_typo_rejected(self, archive: Path) -> None:
        result = self.run_checker(archive)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["valid"])
        self.assertIn("Table_Top_TYPO", report["errors"][0]["message"])

    def test_minimal_flat_room_passes(self) -> None:
        report = self.assert_valid(
            room_fixtures.Room().write_flat(self.root / "minimal-flat.zip")
        )
        self.assertEqual(report["summary"]["kind"], "room")

    def test_minimal_v2_room_passes(self) -> None:
        report = self.assert_valid(
            room_fixtures.Room().write_v2(self.root / "minimal-v2.locusplace")
        )
        self.assertEqual(report["summary"]["packageID"], "place.minimal-reading-room")

    def test_modelio_rejects_repeated_material_bindings_over_app_limit(self) -> None:
        room = room_fixtures.Room()
        # One authored USD material can become one ModelIO material object per
        # mesh. USD prim counts alone therefore miss the App's actual limit.
        for index in range(1050):
            room.boxes.append({"name": f"Extra_{index}", "center": (0, 0, 0),
                               "size": (.1, .1, .1), "material": "Warm_Wood"})
        result = self.run_checker(room.write_v2(self.root / "many-materials.locusplace"))
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(any(e.get("code") == "modelIOBudget" and "materials" in e["message"]
                            for e in report["errors"]))
        group = report["modelIO"]["groups"][0]
        self.assertGreater(group["totals"]["materials"], group["limits"]["materials"])
        self.assertLess(report["rooms"][0]["budgets"]["materials"]["used"], 1024)

    def test_modelio_combines_scene_and_separate_collision(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import check_room
        import validate_locusplace
        room = room_fixtures.Room()
        for index in range(520):
            room.boxes.append({"name": f"Extra_{index}", "center": (0, 0, 0),
                               "size": (.1, .1, .1), "material": "Warm_Wood"})
        model = self.root / "scene.usdz"
        collision = self.root / "collision.usdz"
        model.write_bytes(room.usdz())
        collision.write_bytes(model.read_bytes())
        groups, errors = check_room.check_modelio_groups(
            self.root, [("room", "test", [("scene", model), ("collision", collision)])],
            check_room.executable(), validate_locusplace)
        scene, second = groups[0]["models"]
        self.assertLessEqual(scene["statistics"]["materials"], 1024)
        self.assertEqual(scene["statistics"], second["statistics"])
        self.assertGreater(groups[0]["totals"]["materials"], 1024)
        self.assertTrue(any("materials" in error["message"] for error in errors))

    def test_modelio_checks_destination_midground(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import check_room
        import validate_locusplace
        room = room_fixtures.Room()
        directory = self.root / "catalog/destinations/view.test"
        directory.mkdir(parents=True)
        (directory / "terrain.usdz").write_bytes(room.usdz())
        (directory / "destination.json").write_text(json.dumps({"midground": {"path": "terrain.usdz"}}))
        groups, errors = check_room.check_modelio(
            self.root, {"contents": {"spaceIDs": [], "destinationIDs": ["view.test"]}},
            check_room.executable(), validate_locusplace)
        self.assertEqual(errors, [])
        self.assertEqual(groups[0]["kind"], "midground")
        self.assertGreater(groups[0]["totals"]["triangles"], 0)
        self.assertEqual(groups[0]["models"][0]["role"], "midground")

    def test_flat_binding_typo_is_rejected(self) -> None:
        room = room_fixtures.Room()
        introduce_binding_typo(room)
        self.assert_binding_typo_rejected(room.write_flat(self.root / "typo-flat.zip"))

    def test_v2_binding_typo_is_rejected(self) -> None:
        room = room_fixtures.Room()
        introduce_binding_typo(room)
        self.assert_binding_typo_rejected(room.write_v2(self.root / "typo-v2.locusplace"))

    def test_render_minimal_room_or_report_unavailable_gpu(self) -> None:
        archive = room_fixtures.Room().write_v2(self.root / "render.locusplace")
        output = self.root / "renders"
        result = self.run_checker(archive, "--renders", str(output))
        report = json.loads(result.stdout)
        if not report['valid'] and any('Metal GPU unavailable' in e['message'] for e in report['errors']):
            self.skipTest('Metal GPU unavailable; macOS RealityKit render was not executed')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('R', report['layers'])
        files = [Path(p) for p in report['rooms'][0]['files']]
        self.assertEqual(len(files), 12)
        self.assertTrue(all(p.is_file() for p in files))
        self.assertTrue((output / 'room-0/contact-sheet.png').is_file())
        png = (output / 'room-0/seat-0/yaw-0.png').read_bytes()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (640, 360))

    def test_entry_error_still_produces_diagnostic_renders(self) -> None:
        room = room_fixtures.Room()
        room.materials['Lamp_Glow'] = ((1, .64, .3), .5, None, 1)
        archive = room.write_v2(self.root / 'nonemissive.locusplace')
        result = self.run_checker(archive, '--renders', str(self.root / 'renders'))
        report = json.loads(result.stdout)
        if any('Metal GPU unavailable' in e['message'] for e in report['errors']):
            self.skipTest('Metal GPU unavailable; macOS render not executed')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('entityHasNoPositiveEmissive', [e.get('code') for e in report['errors']])
        self.assertIn('R', report['layers'])
        self.assertGreater(report['rooms'][0]['renderDurationSeconds'], 0)
        self.assertTrue((self.root / 'renders/room-0/contact-sheet.png').exists())

    def test_explicit_current_app_version_is_required(self) -> None:
        archive = room_fixtures.Room().write_flat(self.root / "minimal-flat.zip")
        result = subprocess.run(
            [sys.executable, str(CHECK_ROOM), str(archive)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--current-app-version", result.stderr)


if __name__ == "__main__":
    unittest.main()
