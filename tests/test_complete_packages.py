"""Public complete-package CLI coverage with generated, disposable fixtures."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
BUILD_EXAMPLES = ROOT / "examples" / "locusplace" / "build_examples.py"
VALIDATE = TOOLS / "validate_locusplace.py"
PACK = TOOLS / "pack_locusplace.py"


def load_example_builder():
    spec = importlib.util.spec_from_file_location(
        "public_locusplace_examples", BUILD_EXAMPLES
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


EXAMPLES = load_example_builder()


def load_flat_validator():
    spec = importlib.util.spec_from_file_location(
        "public_validate_locus_asset", TOOLS / "validate_locus_asset.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompletePackageCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.generated = self.root / "generated"
        result = self.run_cli(BUILD_EXAMPLES, self.generated)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, tool, *arguments):
        return subprocess.run(
            [sys.executable, str(tool), *map(str, arguments)],
            capture_output=True,
            text=True,
        )

    def assert_valid(self, archive):
        result = self.run_cli(
            VALIDATE, "--current-app-version", "1.4.4", archive
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def editable_room(self, name):
        editable = self.root / name
        with zipfile.ZipFile(self.generated / "room-only.locusplace") as source:
            source.extractall(editable)
        return editable

    def write_complete_feature_room(self, editable, *, layer_sizes=(8, 8)):
        envelope_path = editable / "locusplace.json"
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        envelope["minimumAppVersion"] = "1.4.4"
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
        base = editable / "catalog" / "spaces" / "space.example-room"
        manifest_path = base / "space.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["lighting"] = {
            "luminaireGroups": [
                {
                    "id": "cove-light",
                    "displayName": "Cove Light",
                    "entities": ["Cove_Fixture_Glow"],
                    "illuminatedEntities": ["Living_Room_Wall"],
                    "controls": {
                        "brightnessEVRange": [-4, 1],
                        "supportsFullColor": False,
                    },
                },
                {
                    "id": "reading-light",
                    "displayName": "Reading Light",
                    "entities": ["Reading_Lamp_Glow"],
                    "controls": {
                        "brightnessEVRange": [-4, 1],
                        "supportsFullColor": False,
                    },
                },
            ],
            "bakedIndirect": {
                "entities": ["Locus_BakedIndirect"],
                "layers": [
                    {"luminaireGroupID": "cove-light", "image": "light-cove.png"},
                    {"luminaireGroupID": "reading-light", "image": "light-reading.png"},
                ],
            },
        }
        manifest["videoSurfaces"] = [{
            "id": "fireplace-fire",
            "displayName": "Fireplace Fire",
            "entityName": "Video_Surface",
            "video": "fireplace-fire.mp4",
        }]
        manifest["particleEffects"] = [{
            "id": "fireplace-sparks",
            "displayName": "Fireplace Sparks",
            "preset": "fire",
            "anchorEntity": "Particle_Anchor",
            "sizeMeters": [0.62, 0.04, 0.22],
        }]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        (base / "fireplace-fire.mp4").write_bytes(minimal_mp4())
        (base / "light-cove.png").write_bytes(EXAMPLES.rgb_png(layer_sizes[0], layer_sizes[0]))
        (base / "light-reading.png").write_bytes(EXAMPLES.rgb_png(layer_sizes[1], layer_sizes[1]))

    def pack_complete(self, editable, name):
        output = self.root / name
        result = self.run_cli(
            PACK, "--current-app-version", "1.4.4", editable, output
        )
        return output, result

    def test_generated_view_room_and_combined_packages_pack_and_validate(self):
        for name in ("view-only", "room-only", "combined"):
            with self.subTest(name=name):
                archive = self.generated / (name + ".locusplace")
                self.assert_valid(archive)
                editable = self.root / (name + "-editable")
                with zipfile.ZipFile(archive) as source:
                    source.extractall(editable)
                repacked = self.root / (name + "-repacked.locusplace")
                result = self.run_cli(
                    PACK,
                    "--current-app-version", "1.4.4",
                    editable,
                    repacked,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assert_valid(repacked)

    def write_archive_with(self, output, source, transform):
        with zipfile.ZipFile(source) as archive:
            members = {info.filename: archive.read(info) for info in archive.infolist()}
        transform(members)
        with zipfile.ZipFile(output, "w") as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)

    def test_validator_rejects_tampered_hash_unsafe_path_and_incompatible_version(self):
        source = self.generated / "view-only.locusplace"

        def bad_hash(members):
            envelope = json.loads(members["locusplace.json"])
            envelope["contentHash"] = "0" * 64
            members["locusplace.json"] = json.dumps(envelope).encode("utf-8")

        def unsafe_path(members):
            members["../outside.json"] = b"not a package member"

        def incompatible_version(members):
            envelope = json.loads(members["locusplace.json"])
            envelope["minimumAppVersion"] = "9.0.0"
            members["locusplace.json"] = json.dumps(envelope).encode("utf-8")

        cases = (("hash", bad_hash, "contentHash mismatch"),
                 ("path", unsafe_path, "unsafe archive path"),
                 ("version", incompatible_version, "package requires Locus 9.0.0"))
        for name, transform, message in cases:
            with self.subTest(name=name):
                invalid = self.root / (name + ".locusplace")
                self.write_archive_with(invalid, source, transform)
                result = self.run_cli(
                    VALIDATE, "--current-app-version", "1.4.4", invalid
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(message, result.stderr)

    def test_complete_cli_rejects_retired_publisher_only_experiment(self):
        for profile_name in ("celestial", "nearOrbit"):
            with self.subTest(profile=profile_name):
                editable = self.root / ("retired-" + profile_name)
                with zipfile.ZipFile(self.generated / "view-only.locusplace") as archive:
                    archive.extractall(editable)
                manifest_path = next(editable.glob("catalog/destinations/*/destination.json"))
                manifest = json.loads(manifest_path.read_text())
                manifest[profile_name] = {"oceanGlint": {}}
                manifest_path.write_text(json.dumps(manifest))
                output, result = self.pack_complete(editable, profile_name + "-retired.zip")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("oceanGlint is retired", result.stderr)
                self.assertFalse(output.exists())

    def test_complete_cli_packs_and_validates_declared_video_lighting_and_particles(self):
        editable = self.editable_room("complete-features")
        self.write_complete_feature_room(editable)
        archive, result = self.pack_complete(editable, "complete-features.locusplace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_valid(archive)

    def test_complete_cli_rejects_mismatched_baked_light_layer_dimensions(self):
        editable = self.editable_room("mismatched-light-layers")
        self.write_complete_feature_room(editable, layer_sizes=(8, 16))
        _, result = self.pack_complete(editable, "mismatched-light-layers.locusplace")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(
            "lighting.bakedIndirect.layers images must share identical pixel dimensions",
            result.stderr,
        )


class FlatPackageCurrentContractTests(unittest.TestCase):
    def test_room_v7_to_v10_accept_canonical_localizations(self):
        validator = load_flat_validator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(ROOT / "examples" / "atrium-loft-room.zip") as source:
                members = {info.filename: source.read(info) for info in source.infolist()}
            for version in range(7, 11):
                with self.subTest(version=version):
                    manifest = json.loads(members["space.json"])
                    manifest["formatVersion"] = version
                    manifest["localizations"] = {
                        "de": {"title": "Atrium-Loft", "seatTitles": {
                            "ground-work-desk": "Arbeitsplatz"}},
                    }
                    archive = root / ("room-v%d.zip" % version)
                    with zipfile.ZipFile(archive, "w") as output:
                        for name, payload in members.items():
                            if name == "space.json":
                                payload = json.dumps(manifest).encode("utf-8")
                            output.writestr(name, payload)
                    self.assertEqual(validator.validate(archive)["kind"], "room")

    def write_feature_room(self, output, *, overlapping=False,
                           missing_particle_anchor=False, layer_sizes=(8, 8)):
        with zipfile.ZipFile(ROOT / "examples" / "atrium-loft-room.zip") as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        manifest = json.loads(members["space.json"])
        manifest.pop("spatialAdaptation", None)
        manifest.pop("rendering", None)
        manifest["formatVersion"] = 10
        manifest["lighting"] = feature_lighting()
        manifest["videoSurfaces"] = [{
            "id": "fireplace-fire",
            "displayName": "Fireplace Fire",
            "entityName": "Video_Surface",
            "video": "fireplace-fire.mp4",
        }]
        manifest["particleEffects"] = [{
            "id": "fireplace-sparks",
            "displayName": "Fireplace Sparks",
            "preset": "fire",
            "anchorEntity": (
                "Missing_Particle_Anchor" if missing_particle_anchor
                else "Particle_Anchor"
            ),
            "sizeMeters": [0.62, 0.04, 0.22],
        }]
        members["space.json"] = json.dumps(manifest).encode("utf-8")
        members["scene.usdz"] = binding_usdz(overlapping=overlapping)
        members["fireplace-fire.mp4"] = minimal_mp4()
        members["light-cove.png"] = EXAMPLES.rgb_png(layer_sizes[0], layer_sizes[0])
        members["light-reading.png"] = EXAMPLES.rgb_png(layer_sizes[1], layer_sizes[1])
        with zipfile.ZipFile(output, "w") as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)

    def test_flat_cli_exercises_v7_to_v10_assets_and_native_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "room-v10-features.zip"
            self.write_feature_room(valid)
            result = subprocess.run(
                [sys.executable, str(TOOLS / "validate_locus_asset.py"), str(valid)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            overlap = root / "room-v8-illuminated-overlap.zip"
            self.write_feature_room(overlap, overlapping=True)
            result = subprocess.run(
                [sys.executable, str(TOOLS / "validate_locus_asset.py"), str(overlap)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("overlap in the model hierarchy", result.stderr)

            missing_anchor = root / "room-v9-missing-particle-anchor.zip"
            self.write_feature_room(missing_anchor, missing_particle_anchor=True)
            result = subprocess.run(
                [sys.executable, str(TOOLS / "validate_locus_asset.py"), str(missing_anchor)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("Missing_Particle_Anchor", result.stderr)

            mismatched_layers = root / "room-v10-mismatched-layers.zip"
            self.write_feature_room(mismatched_layers, layer_sizes=(8, 16))
            result = subprocess.run(
                [sys.executable, str(TOOLS / "validate_locus_asset.py"), str(mismatched_layers)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("images must share identical pixel dimensions", result.stderr)


def minimal_mp4():
    return b"\x00\x00\x00\x0cftypisom"


def feature_lighting():
    controls = {"brightnessEVRange": [-4, 1], "supportsFullColor": False}
    return {
        "luminaireGroups": [
            {
                "id": "cove-light",
                "displayName": "Cove Light",
                "entities": ["Cove_Fixture_Glow"],
                "illuminatedEntities": ["Living_Room_Wall"],
                "controls": controls,
            },
            {
                "id": "reading-light",
                "displayName": "Reading Light",
                "entities": ["Reading_Lamp_Glow"],
                "controls": controls,
            },
        ],
        "bakedIndirect": {
            "entities": ["Locus_BakedIndirect"],
            "layers": [
                {"luminaireGroupID": "cove-light", "image": "light-cove.png"},
                {"luminaireGroupID": "reading-light", "image": "light-reading.png"},
            ],
        },
    }


def binding_usdz(*, overlapping=False):
    if overlapping:
        cove = '''    def Xform "Cove_Fixture_Glow" {
        def Cube "Living_Room_Wall" {
            double size = 2
        }
    }
'''
    else:
        cove = '''    def Cube "Cove_Fixture_Glow" {
        double size = 1
    }
    def Cube "Living_Room_Wall" {
        double size = 2
    }
'''
    additions = (cove + '''    def Cube "Reading_Lamp_Glow" {
        double size = 1
    }
    def Cube "Locus_BakedIndirect" {
        double size = 1
    }
    def Cube "Video_Surface" {
        double size = 1
    }
    def Xform "Particle_Anchor" {
    }
''').encode("utf-8")
    with zipfile.ZipFile(io.BytesIO(EXAMPLES.usdz_bytes())) as source:
        info = source.infolist()[0]
        original = source.read(info)
    source_member = b'''    def Cube "Shell" {
        double size = 2
    }
'''
    assert source_member in original
    rewritten = original.replace(source_member, additions)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
        archive.writestr(info, rewritten)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
