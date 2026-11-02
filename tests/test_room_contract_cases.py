"""Contracts for source-generated cross-consumer Room fixtures."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
FLAT_VALIDATOR = TOOLS / "validate_locus_asset.py"
V2_VALIDATOR = TOOLS / "validate_locusplace.py"
sys.path.insert(0, str(TESTS := ROOT / "tests"))
sys.path.insert(0, str(TOOLS))

import room_contract_cases  # noqa: E402
import export_room_contract_fixtures as exporter  # noqa: E402


class RoomContractFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-room-contract-")
        self.root = Path(self.temporary.name)
        self.output = self.root / "fixtures"
        self.manifest_path = exporter.build(self.output)
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.cases = {case["id"]: case for case in self.manifest["cases"]}

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, case_id, archive_format):
        case = self.cases[case_id]
        record = next(item for item in case["archives"] if item["format"] == archive_format)
        return self.output / record["path"]

    def metadata(self, case_id, archive_format):
        archive = self.archive(case_id, archive_format)
        with zipfile.ZipFile(archive) as source:
            if archive_format == "flat":
                return json.loads(source.read("space.json")), json.loads(source.read("teleport-points.json")), source.read("scene.usdz")
            base = "catalog/spaces/space.minimal-reading-room/"
            return (json.loads(source.read(base + "space.json")),
                    json.loads(source.read(base + "teleport-points.json")),
                    source.read(base + "scene.usdz"))

    def test_manifest_covers_every_expected_case_and_contract_layer(self):
        expected = [case.identifier for case in room_contract_cases.CASES]
        self.assertEqual([case["id"] for case in self.manifest["cases"]], expected)
        self.assertEqual(self.manifest["annotationStatus"], "expected-app-behavior")
        self.assertEqual(self.manifest["fixtureSource"], "tests/room_fixtures.py")
        self.assertEqual(self.manifest["thumbnailSource"], exporter.THUMBNAIL_SOURCE)
        self.assertEqual(self.manifest["thumbnailSource"], "examples/atrium-loft-room.zip#thumbnail.jpg")
        for case in self.manifest["cases"]:
            with self.subTest(case=case["id"]):
                annotations = case["annotations"]
                self.assertEqual(annotations["expectation"], "expected-app-behavior")
                self.assertEqual(set(annotations) & {"importer", "entry", "checker"},
                                 {"importer", "entry", "checker"})
                for layer in ("importer", "entry"):
                    self.assertIn(annotations[layer]["outcome"], {"accept", "reject"})
                    self.assertIn("error", annotations[layer])
                self.assertIn("expectedECode", annotations["checker"])
                self.assertEqual({item["format"] for item in case["archives"]}, {"flat", "package-v2"})

    def test_each_archive_hash_matches_manifest_and_is_source_generated(self):
        for case in self.manifest["cases"]:
            for record in case["archives"]:
                with self.subTest(case=case["id"], archive=record["format"]):
                    archive = self.output / record["path"]
                    data = archive.read_bytes()
                    self.assertEqual(len(data), record["byteCount"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
                    with zipfile.ZipFile(archive) as source:
                        if record["format"] == "flat":
                            self.assertIn("scene.usdz", source.namelist())
                            self.assertIn("space.json", source.namelist())
                            self.assertIn("thumbnail.jpg", source.namelist())
                        else:
                            self.assertIn("locusplace.json", source.namelist())
                            self.assertIn("catalog/spaces/space.minimal-reading-room/space.json", source.namelist())
                            self.assertIn("catalog/spaces/space.minimal-reading-room/scene.usdz", source.namelist())

    def test_source_mutations_are_present_in_both_archive_formats(self):
        for archive_format in ("flat", "package-v2"):
            with self.subTest(archive_format=archive_format):
                space, _seats, _model = self.metadata("missingbinding", archive_format)
                self.assertEqual(space["spatialAdaptation"]["roofEntities"], ["Roof_MISSING"])

                space, _seats, _model = self.metadata("tilted-seated-origin", archive_format)
                self.assertEqual(space["seatedOrigin"]["orientationXYZW"], [0.1, 0, 0, 0.995])
                space, _seats, _model = self.metadata("zero-seated-origin", archive_format)
                self.assertEqual(space["seatedOrigin"]["orientationXYZW"], [0, 0, 0, 0])

                space, _seats, model = self.metadata("nonemissive-luminaire", archive_format)
                self.assertIn("Pendant_Glow", space["lighting"]["luminaireGroups"][0]["entities"])
                self.assertNotIn("emissiveColor", self.usda(model, "Lamp_Glow"))

                space, _seats, model = self.metadata("nonopaque-illuminated", archive_format)
                self.assertEqual(space["lighting"]["luminaireGroups"][0]["illuminatedEntities"], ["Illuminated_Panel"])
                self.assertNotIn("Illuminated_Panel", space["lighting"]["luminaireGroups"][0]["entities"])
                self.assertNotIn("Illuminated_Panel", (space["lighting"].get("bakedIndirect") or {}).get("entities", []))
                self.assertIn("float inputs:opacity = 0.5", self.usda(model, "Illuminated_Glow"))
                self.assertIn("emissiveColor", self.usda(model, "Illuminated_Glow"))

                space, _seats, model = self.metadata("nonopaque-baked-indirect", archive_format)
                self.assertEqual(space["lighting"]["bakedIndirect"]["entities"], ["Indirect_Panel"])
                self.assertIn("float inputs:opacity = 0.5", self.usda(model, "Indirect_Glow"))

                space, _seats, _model = self.metadata("missing-animation", archive_format)
                self.assertEqual(space["ambientAnimations"][0]["animationName"], "missing")

                space, _seats, _model = self.metadata("desk-outside-group", archive_format)
                self.assertEqual(space["spatialAdaptation"]["deskGroupEntitiesByTeleportID"], {"seat.primary": "Chair_Seat"})

                _space, _seats, model = self.metadata("zero-thickness-desk", archive_format)
                scene = self.scene_usda(model)
                table_top = self.subtree(scene, "Table_Top", "Table_Leg_0")
                points = re.findall(r"\(([^)]+)\)", table_top.split("point3f[] points = [", 1)[1].split("]", 1)[0])
                self.assertEqual(len(points), 8)
                self.assertEqual({point.split(", ")[1] for point in points}, {"0.7"})

                _space, seats, _model = self.metadata("no-seats", archive_format)
                self.assertEqual(seats["points"] if archive_format == "flat"
                                 else seats["houses"]["space.minimal-reading-room"], [])

                _space, _seats, model = self.metadata("degenerate-bounds", archive_format)
                source = self.usda(model, "Warm_Wood")
                self.assertIn("def Material \"Warm_Wood\"", source)
                scene = self.scene_usda(model)
                self.assertIn('def Xform "Floor"', scene)
                self.assertNotIn('def Xform "Back_Wall"', scene)

    def test_zero_thickness_annotation_records_the_intentional_difference(self):
        annotation = self.cases["zero-thickness-desk"]["annotations"]
        self.assertEqual(annotation["importer"], {"outcome": "accept", "error": None})
        self.assertEqual(annotation["entry"], {"outcome": "accept", "error": None})
        self.assertEqual(annotation["checker"]["expectedECode"], "deskBounds")
        self.assertIn("Intentional conservative checker difference", annotation["intentionalDifference"])

    def test_uncertain_stage_boundaries_are_explicit(self):
        for case_id in ("degenerate-bounds", "no-seats"):
            with self.subTest(case=case_id):
                annotation = self.cases[case_id]["annotations"]
                self.assertEqual(annotation["expectation"], "expected-app-behavior")
                self.assertIn("app", annotation["uncertainty"].lower())

    def test_export_is_byte_deterministic(self):
        second = self.root / "second"
        second_manifest = json.loads(exporter.build(second).read_text(encoding="utf-8"))
        self.assertEqual(self.manifest, second_manifest)
        for case in self.manifest["cases"]:
            for record in case["archives"]:
                with self.subTest(case=case["id"], archive=record["path"]):
                    self.assertEqual((self.output / record["path"]).read_bytes(),
                                     (second / record["path"]).read_bytes())

    def test_valid_fixture_passes_the_public_flat_and_v2_validators(self):
        commands = (
            (FLAT_VALIDATOR, self.archive("valid", "flat")),
            (V2_VALIDATOR, "--current-app-version", "1.4.4",
             self.archive("valid", "package-v2")),
        )
        for command in commands:
            with self.subTest(tool=Path(command[0]).name):
                result = subprocess.run([sys.executable, *map(str, command)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_exports_manifest_and_documents_the_pinned_thumbnail_source(self):
        help_result = subprocess.run([sys.executable, str(TOOLS / "export_room_contract_fixtures.py"), "--help"],
                                     capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("examples/atrium-loft-room.zip#thumbnail.jpg", help_result.stdout.replace("\n", ""))

        command_output = self.root / "cli"
        result = subprocess.run([sys.executable, str(TOOLS / "export_room_contract_fixtures.py"), str(command_output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), command_output / "manifest.json")

    @staticmethod
    def usda(model, material):
        text = RoomContractFixtureTests.scene_usda(model)
        start = text.index('def Material "' + material + '"')
        end = text.find('\n        }', start) + len('\n        }')
        return text[start:end]

    @staticmethod
    def scene_usda(model):
        with zipfile.ZipFile(io.BytesIO(model)) as usdz:
            return usdz.read("scene.usda").decode("utf-8")

    @staticmethod
    def subtree(scene, start_name, next_name):
        start = scene.index('def Xform "' + start_name + '"')
        end = scene.index('def Xform "' + next_name + '"', start)
        return scene[start:end]


if __name__ == "__main__":
    unittest.main()
