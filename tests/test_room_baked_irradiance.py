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


if __name__ == "__main__":
    unittest.main()
