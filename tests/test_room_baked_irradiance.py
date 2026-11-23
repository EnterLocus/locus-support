"""Room baked irradiance lightmaps (`mode: "irradiance"`, Locus 1.5.2+):
flat v14 + Package v2 validation, 16-bit PNG checks, RealityKit UV1 bindings,
and check_room coverage."""

from __future__ import annotations

import binascii
import copy
import json
import platform
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import check_room  # noqa: E402
import room_bindings  # noqa: E402
import room_fixtures  # noqa: E402
import validate_locus_asset  # noqa: E402
import validate_locusplace  # noqa: E402

HAS_REALITYKIT = platform.system() == "Darwin" and shutil.which("xcrun") is not None


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def rgb_png(width: int = 8, height: int = 8, bit_depth: int = 16) -> bytes:
    rows = []
    for _y in range(height):
        row = bytearray([0])
        for _x in range(width):
            if bit_depth == 16:
                row.extend((0x20, 0x00, 0x18, 0x00, 0x10, 0x00))
            else:
                row.extend((64, 48, 32))
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def irradiance_room(*, with_uv1: bool = True, edit_space=None, png_bits: int = 16):
    room = room_fixtures.minimal_room()
    uv1_block = ""
    if with_uv1:
        uvs = ", ".join(["(0.25, 0.25)"] * 4)
        uv1_block = (
            f"            texCoord2f[] primvars:LocusIndirectUV = [{uvs}] (\n"
            '                interpolation = "vertex"\n'
            "            )\n"
        )
    room.extra_usda = (
        '\n    def Xform "Irradiance_Wall" (\n    )\n    {\n'
        '        def Mesh "Irradiance_Wall_Mesh" (\n'
        '            prepend apiSchemas = ["MaterialBindingAPI"]\n'
        "        )\n        {\n"
        "            int[] faceVertexCounts = [4]\n"
        "            int[] faceVertexIndices = [0, 1, 2, 3]\n"
        "            point3f[] points = [(-1, 0, -1.8), (1, 0, -1.8), (1, 2, -1.8), (-1, 2, -1.8)]\n"
        '            texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (\n'
        '                interpolation = "vertex"\n'
        "            )\n"
        + uv1_block
        + '            rel material:binding = </root/_materials/Lamp_Glow>\n'
        '            uniform token subdivisionScheme = "none"\n'
        "        }\n    }\n"
    )
    room.extra_v2_files = {
        f"catalog/spaces/{room_fixtures.SPACE_ID}/light-pendant.png": rgb_png(8, 8, bit_depth=png_bits)
    }

    original_v2_space = room.v2_space

    def v2_space():
        space = original_v2_space()
        space["lighting"] = {
            "luminaireGroups": [
                {
                    "id": "pendant",
                    "displayName": "Pendant",
                    "entities": ["Pendant_Glow"],
                    "controls": {"brightnessEVRange": [-4, 1], "supportsFullColor": False},
                }
            ],
            "bakedIndirect": {
                "entities": ["Irradiance_Wall"],
                "mode": "irradiance",
                "irradianceScale": 4.0,
                "layers": [{"luminaireGroupID": "pendant", "image": "light-pendant.png"}],
            },
        }
        if edit_space is not None:
            edit_space(space)
        return space

    room.v2_space = v2_space
    return room


class RoomBakedIrradianceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-irradiance-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_v2(self, name: str, *, minimum: str = "1.5.2", with_uv1: bool = True, edit_space=None, png_bits: int = 16) -> Path:
        room = irradiance_room(with_uv1=with_uv1, edit_space=edit_space, png_bits=png_bits)
        base = room.write_v2(self.root / f"{name}-raw.locusplace", minimum_app_version=minimum)
        if not getattr(room, "extra_v2_files", None):
            return base
        out = self.root / f"{name}.locusplace"
        with zipfile.ZipFile(base) as zf:
            files = {info.filename: zf.read(info.filename) for info in zf.infolist() if info.filename != "locusplace.json"}
            envelope = json.loads(zf.read("locusplace.json"))
        files.update(room.extra_v2_files)
        import hashlib
        records = [
            {"path": p, "byteCount": len(d), "sha256": hashlib.sha256(d).hexdigest()}
            for p, d in sorted(files.items())
        ]
        envelope["files"] = records
        envelope["contentHash"] = validate_locusplace.calculate_content_hash(records)
        with zipfile.ZipFile(out, "w") as zf:
            zf.writestr("locusplace.json", json.dumps(envelope, indent=2).encode("utf-8"))
            for p, d in sorted(files.items()):
                zf.writestr(p, d)
        return out

    def test_valid_irradiance_v2_archive_validates_and_checks(self):
        archive = self.write_v2("valid-irradiance")
        summary = validate_locusplace.validate(archive, current_app_version="1.5.2")
        self.assertEqual(summary["rooms"], 1)
        if HAS_REALITYKIT:
            report = check_room.check(archive, "1.5.2")
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["errors"], [])

    def test_minimum_app_version_and_png_bit_depth_rules(self):
        low_floor = self.write_v2("low-floor", minimum="1.5.1")
        with self.assertRaisesRegex(
            validate_locusplace.ValidationError,
            "mode=irradiance requires minimumAppVersion >= 1.5.2",
        ):
            validate_locusplace.validate(low_floor, current_app_version="1.5.2")

        eight_bit = self.write_v2("eight-bit", png_bits=8)
        with self.assertRaisesRegex(
            validate_locusplace.ValidationError,
            "must be a 16-bit RGB or RGBA PNG when irradianceScale > 1",
        ):
            validate_locusplace.validate(eight_bit, current_app_version="1.5.2")

    def test_flat_room_v14_contract_rules(self):
        lighting = {
            "luminaireGroups": [
                {
                    "id": "pendant",
                    "displayName": "Pendant",
                    "entities": ["Pendant_Glow"],
                    "controls": {"brightnessEVRange": [-4, 1], "supportsFullColor": False},
                }
            ],
            "bakedIndirect": {
                "entities": ["Irradiance_Wall"],
                "mode": "irradiance",
                "irradianceScale": 3.0,
                "image": "irradiance.png",
            },
        }
        with self.assertRaisesRegex(
            validate_locus_asset.ValidationError,
            "lighting.bakedIndirect.mode requires space.json formatVersion 14",
        ):
            validate_locus_asset.validate_lighting(lighting, {"seat.primary"}, 13)
        self.assertEqual(
            validate_locus_asset.validate_lighting(lighting, {"seat.primary"}, 14),
            {"irradiance.png"},
        )
        both = copy.deepcopy(lighting)
        both["bakedIndirect"]["layers"] = [{"luminaireGroupID": "pendant", "image": "layer.png"}]
        with self.assertRaisesRegex(
            validate_locus_asset.ValidationError,
            "requires either image or layers, not both",
        ):
            validate_locus_asset.validate_lighting(both, {"seat.primary"}, 14)

    @unittest.skipUnless(HAS_REALITYKIT, "RealityKit binding check requires macOS with Xcode")
    def test_missing_secondary_uv_is_rejected_by_bindings_and_check_room(self):
        missing_uv1 = self.write_v2("missing-uv1", with_uv1=False)
        with self.assertRaisesRegex(validate_locusplace.ValidationError, "LocusIndirectUV"):
            validate_locusplace.validate(missing_uv1, current_app_version="1.5.2")
        with zipfile.ZipFile(missing_uv1) as zf:
            tmp = self.root / "standalone-uv1"
            tmp.mkdir()
            scene = tmp / "scene.usdz"
            space_file = tmp / "space.json"
            scene.write_bytes(zf.read(f"catalog/spaces/{room_fixtures.SPACE_ID}/scene.usdz"))
            space_file.write_bytes(zf.read(f"catalog/spaces/{room_fixtures.SPACE_ID}/space.json"))
            with self.assertRaisesRegex(room_bindings.BindingCheckError, "LocusIndirectUV"):
                room_bindings.check(scene, space_file)


class RoomLightingScriptsAndSkillTests(unittest.TestCase):
    """Test standalone public bake_irradiance.py, audit_lighting_photometry.py, and Room skill hygiene."""

    def test_public_bake_config_validation_and_helpers(self):
        import importlib.util
        from array import array

        script = ROOT / ".agents" / "skills" / "build-original-locus-room" / "scripts" / "bake_irradiance.py"
        spec = importlib.util.spec_from_file_location("public_bake_irradiance", script)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)

        valid_cfg = {
            "rootName": "TestRoom_ROOT",
            "scale": "standard",
            "lightGroups": [
                {
                    "id": "overheads",
                    "role": "overheads",
                    "fixtures": [
                        {"id": "can-1", "kind": "downlight", "emitterType": "spot", "position": [0, 2.7, 0], "lumens": 450, "kelvin": 2900}
                    ],
                },
                {
                    "id": "desk",
                    "role": "task",
                    "fixtures": [
                        {"id": "desk-1", "kind": "desk_lamp", "emitterType": "spot", "position": [0, 1.1, -1], "lumens": 200, "kelvin": 2700}
                    ],
                },
            ],
        }
        report = mod.validate_bake_config(valid_cfg, 2048, 1024)
        self.assertTrue(report["passed"], report)

        bad_cfg = {
            "rootName": "TestRoom_ROOT",
            "lightGroups": [
                {
                    "id": "mixed",
                    "role": "overheads",
                    "fixtures": [
                        {"id": "can-1", "role": "overheads", "kind": "downlight", "emitterType": "spot", "position": [0, 2.7, 0], "lumens": 400},
                        {"id": "floor-1", "role": "accent", "kind": "floor_lamp", "emitterType": "point", "position": [1, 1.5, 0], "lumens": 400},
                    ],
                }
            ],
        }
        bad_report = mod.validate_bake_config(bad_cfg, 2048, 1024)
        self.assertFalse(bad_report["passed"])
        codes = {f["code"] for f in bad_report["findings"]}
        self.assertIn("LIGHTING_MIXED_QUADRANT_GROUP", codes)
        self.assertIn("LIGHTING_UNSHADED_LAMP_POINT", codes)

        self.assertEqual(mod.compute_irradiance_scale(0.8), 1.0)
        self.assertGreaterEqual(mod.compute_irradiance_scale(4.2), 4.28)
        self.assertLessEqual(mod.compute_irradiance_scale(99.0, p99999_linear=20.0), 64.0)

        px = array("f", [0.0] * (8 * 8 * 4))
        px[3 * 8 * 4 + 3 * 4] = 1.0
        blurred = mod.separable_box_blur_rgba(px, 8, 8, radius=1, passes=1)
        self.assertEqual(len(blurred), len(px))
        self.assertLess(blurred[3 * 8 * 4 + 3 * 4], 1.0)

    def test_public_photometry_audit_pass_and_failure_gates(self):
        import importlib.util

        script = ROOT / ".agents" / "skills" / "build-original-locus-room" / "scripts" / "audit_lighting_photometry.py"
        spec = importlib.util.spec_from_file_location("public_audit_photometry", script)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)

        def solid_16_png(val_u16: int, size: int = 16) -> bytes:
            row = b"\x00" + struct.pack(">HHH", val_u16, val_u16, val_u16) * size
            ihdr = struct.pack(">IIBBBBB", size, size, 16, 2, 0, 0, 0)
            return (
                b"\x89PNG\r\n\x1a\n"
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IDAT", zlib.compress(row * size, level=6))
                + _png_chunk(b"IEND", b"")
            )

        with tempfile.TemporaryDirectory(prefix="locus-photometry-test-") as directory:
            root = Path(directory)
            manifest = {
                "formatVersion": 2,
                "lighting": {
                    "luminaireGroups": [
                        {"id": "overheads", "displayName": "Ceiling Lights", "entities": ["Can_Glow"]},
                        {"id": "desk-lamp", "displayName": "Desk Lamp", "entities": ["Desk_Glow"]},
                    ],
                    "bakedIndirect": {
                        "entities": ["Locus_BakedIndirect"],
                        "mode": "irradiance",
                        "irradianceScale": 4.0,
                        "layers": [
                            {"luminaireGroupID": "overheads", "image": "light-overheads.png"},
                            {"luminaireGroupID": "desk-lamp", "image": "light-desk-lamp.png"},
                        ],
                    },
                },
            }
            (root / "space.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "light-overheads.png").write_bytes(solid_16_png(38000))
            (root / "light-desk-lamp.png").write_bytes(solid_16_png(12000))
            good = mod.audit_lighting_photometry(root)
            self.assertTrue(good["passed"], good)
            self.assertGreaterEqual(good["moodSummary"]["overheadsOffMedianDropPercent"], 65.0)

            # Overbright small mood layer washing out the room should fail
            (root / "light-desk-lamp.png").write_bytes(solid_16_png(36000))
            washed = mod.audit_lighting_photometry(root)
            self.assertFalse(washed["passed"])
            self.assertIn("LIGHTING_OVERHEADS_OFF_NO_MOOD_DELTA", {f["code"] for f in washed["findings"]})

    def test_room_skill_is_public_safe_and_weaves_irradiance_baking(self):
        skill_dir = ROOT / ".agents" / "skills" / "build-original-locus-room"
        combined = []
        for path in sorted(skill_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            combined.append(content)
            for forbidden in ("/Users/", "/Volumes/", "Dropbox", "Locus Dev", "model-preview/", "--simulator-head-pose"):
                self.assertNotIn(forbidden, content, f"{path}: contains private reference {forbidden!r}")
        joined = "\n".join(combined)
        for required in ("bake_irradiance.py", "audit_lighting_photometry.py", "mode: \"irradiance\"", "irradianceScale", "LocusIndirectUV"):
            self.assertIn(required, joined)


if __name__ == "__main__":
    unittest.main()
