# SPDX-License-Identifier: Apache-2.0
"""Public-safety, link portability, tool-path, and clean-room View build tests for build-a-view."""

from __future__ import annotations

import binascii
import hashlib
from io import BytesIO
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PACK = TOOLS / "pack_locusplace.py"
VALIDATE = TOOLS / "validate_locusplace.py"
BUILD_EXAMPLES = ROOT / "examples" / "locusplace" / "build_examples.py"

sys.path.insert(0, str(TOOLS))
import near_orbit_profile
import sun_path_contract

SKILL_DIR = ROOT / ".agents" / "skills" / "build-a-view"
LEGACY_REFERENCES = frozenset({
    "skybox-workflow.md",
    "models-and-cost.md",
    "resolution.md",
})
EXPECTED_REFERENCES = LEGACY_REFERENCES | {
    "package-v2-delivery.md",
    "sky-clouds-and-daylight.md",
    "water-and-shore.md",
    "midground-3d.md",
    "video-atmosphere-and-sound.md",
    "space-and-black-hole.md",
}


def _load_examples():
    spec = importlib.util.spec_from_file_location("public_locusplace_examples", BUILD_EXAMPLES)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


EXAMPLES = _load_examples()


def _png(width: int, height: int, bit_depth: int, color_type: int, rows: list[bytes]) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + EXAMPLES.png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0),
        )
        + EXAMPLES.png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=6))
        + EXAMPLES.png_chunk(b"IEND", b"")
    )


def _gray8_png(width: int, height: int, value: int = 255) -> bytes:
    row = bytes([0] + [value] * width)
    return _png(width, height, 8, 0, [row] * height)


def _rgba8_png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    row = bytes([0]) + bytes(rgba) * width
    return _png(width, height, 8, 6, [row] * height)


def _gray16_png_from_samples(width: int, height: int, samples_u16: list[list[int]]) -> bytes:
    rows = []
    for r in range(height):
        rows.append(b"\x00" + b"".join(struct.pack(">H", v) for v in samples_u16[r]))
    return _png(width, height, 16, 0, rows)


def _rgb16_png(width: int, height: int, samples_rgb_u16: list[list[tuple[int, int, int]]]) -> bytes:
    rows = []
    for r in range(height):
        rows.append(
            b"\x00" + b"".join(struct.pack(">HHH", *rgb) for rgb in samples_rgb_u16[r])
        )
    return _png(width, height, 16, 2, rows)


def _pcm_wav_bytes(*, channels: int = 1, sample_rate: int = 8000, frames: int = 160) -> bytes:
    block_align = channels * 2
    byte_rate = sample_rate * block_align
    data_size = frames * block_align
    fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, 16)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", data_size)
        + bytes(data_size)
    )


def _mp4_box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _minimal_avc_mp4_bytes(width: int = 16, height: int = 16) -> bytes:
    """Minimal ISO BMFF MP4 with an 8-bit 4:2:0 Baseline H.264 sample entry."""
    ftyp = _mp4_box(b"ftyp", b"isom\x00\x00\x02\x00isomavc1")
    # avcC: version=1, profile_idc=66 (Baseline -> 8-bit 4:2:0), compat=0, level=30,
    # lengthSizeMinusOne=3, numSPS=1 (dummy 2-byte SPS), numPPS=1 (dummy 2-byte PPS).
    avcc = _mp4_box(
        b"avcC",
        b"\x01\x42\x00\x1e\xff\xe1\x00\x02\x67\x42\x01\x00\x02\x68\xce",
    )
    colr = _mp4_box(b"colr", b"nclx" + struct.pack(">HHHB", 1, 1, 1, 0))
    # VisualSampleEntry: 78 bytes before child boxes; width/height sit at offset 24..28.
    visual_header = bytearray(78)
    struct.pack_into(">H", visual_header, 6, 1)
    struct.pack_into(">HH", visual_header, 24, width, height)
    struct.pack_into(">II", visual_header, 28, 0x00480000, 0x00480000)
    struct.pack_into(">H", visual_header, 40, 1)
    struct.pack_into(">H", visual_header, 74, 24)
    struct.pack_into(">H", visual_header, 76, 0xFFFF)
    avc1 = _mp4_box(b"avc1", bytes(visual_header) + avcc + colr)
    stsd = _mp4_box(b"stsd", struct.pack(">II", 0, 1) + avc1)
    stbl = _mp4_box(b"stbl", stsd)
    minf = _mp4_box(b"minf", stbl)
    mdia = _mp4_box(b"mdia", minf)
    # tkhd v0 with identity matrix at payload offset 40..76.
    tkhd_payload = bytearray(84)
    struct.pack_into(">9i", tkhd_payload, 40, 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)
    tkhd = _mp4_box(b"tkhd", bytes(tkhd_payload))
    trak = _mp4_box(b"trak", tkhd + mdia)
    moov = _mp4_box(b"moov", trak)
    return ftyp + moov


def _usdz_from_usda(usda_text: str) -> bytes:
    """Create a 64-byte-aligned single-layer uncompressed USDZ matching build_examples.py."""
    output = BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
        info = zipfile.ZipInfo("root.usda")
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        # Local header (30 bytes) + filename "root.usda" (9 bytes) + 25-byte extra = 64 bytes.
        info.extra = struct.pack("<HH", 0xFFFF, 21) + bytes(21)
        archive.writestr(info, usda_text.encode("utf-8"))
    return output.getvalue()


class BuildAViewSkillTests(unittest.TestCase):
    def test_skill_has_frontmatter_and_indexes_all_references(self):
        skill_md = (SKILL_DIR / "SKILL.md").read_text()
        self.assertTrue(skill_md.startswith("---\n"))
        actual_refs = {path.name for path in (SKILL_DIR / "references").glob("*.md")}
        self.assertEqual(actual_refs, EXPECTED_REFERENCES)
        for name in sorted(EXPECTED_REFERENCES):
            with self.subTest(reference=name):
                self.assertIn(f"references/{name}", skill_md)

    def test_skill_is_public_safe_and_has_portable_links_and_valid_repo_paths(self):
        with tempfile.TemporaryDirectory(prefix="locus-view-skill-") as directory:
            copied = (Path(directory) / SKILL_DIR.name).resolve()
            shutil.copytree(SKILL_DIR, copied)
            combined_parts = []
            links_checked = 0
            repo_paths_checked = 0

            for path in sorted(copied.rglob("*.md")):
                content = path.read_text()
                combined_parts.append(content)
                rel = path.relative_to(copied)
                with self.subTest(path=str(rel)):
                    for private_detail in (
                        "/Users/",
                        "/Volumes/",
                        "Dropbox",
                        "Locus Dev",
                        "model-preview/",
                        "--simulator-head-pose",
                        "LOCUS_SIGNING",
                        "creator_combined_cap",
                        "generator/",
                        "experiments/",
                    ):
                        self.assertNotIn(private_detail, content)
                    self.assertNotRegex(
                        content, r"github\.com/EnterLocus/locus(?:/|[)#\s]|$)"
                    )
                    self.assertNotRegex(
                        content,
                        r"(?i)train(?:ing)? (?:or fine-tune )?(?:an )?AI models?|outside Locus",
                    )

                targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)
                for target in targets:
                    parsed = urllib.parse.urlsplit(target)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    if path.name in LEGACY_REFERENCES and target.startswith("../../../../"):
                        resolved = (ROOT / parsed.path.replace("../../../../", "")).resolve()
                        self.assertTrue(resolved.is_relative_to(ROOT), target)
                        self.assertTrue(resolved.is_file(), target)
                    else:
                        resolved = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
                        self.assertTrue(resolved.is_relative_to(copied), target)
                        self.assertTrue(resolved.is_file(), target)
                    links_checked += 1

                for repo_rel in re.findall(
                    r"(?:tools/[^\s`'\"),]+\.(?:py|json)|schemas/[^\s`'\"),]+\.json)",
                    content,
                ):
                    self.assertTrue((ROOT / repo_rel).is_file(), f"{rel}: missing {repo_rel}")
                    repo_paths_checked += 1

            self.assertGreater(links_checked, 0)
            self.assertGreater(repo_paths_checked, 0)

            combined = "\n".join(combined_parts)
            for required in (
                "pack_locusplace.py",
                "validate_locusplace.py",
                "--current-app-version",
                "sunFreeSky",
                "sun-sky-mask.png",
                "panoramaBlend",
                "gpuTextures",
                "shore",
                "flowingWater",
                "primvars:st",
                "primvars:displayColor",
                "point-lights.json",
                "fireflies",
                "celestial",
                "nearOrbit",
                "blackHole",
                "azimuthDegrees",
            ):
                with self.subTest(capability_term=required):
                    self.assertIn(required, combined)


class CleanRoomViewEndToEndTests(unittest.TestCase):
    """Build and validate every major View capability using only public tools and contracts."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-cleanroom-view-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def _prepare_view_dir(
        self,
        name: str,
        dest_id: str,
        *,
        minimum_app: str,
        destination_extra: dict,
        assets: dict[str, bytes] | None = None,
    ) -> Path:
        editable = self.root / name
        dest_dir = editable / "catalog" / "destinations" / dest_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        pano = EXAMPLES.panorama_png(32, 16)
        thumb = EXAMPLES.panorama_png(32, 18)
        ibl = EXAMPLES.panorama_png(16, 8)
        (dest_dir / "panorama.png").write_bytes(pano)
        (dest_dir / "thumbnail.png").write_bytes(thumb)
        (dest_dir / "lighting-ibl.png").write_bytes(ibl)
        (dest_dir / "provenance.json").write_bytes(EXAMPLES.json_bytes(EXAMPLES.PROVENANCE))

        for rel, payload in (assets or {}).items():
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)

        destination = {
            "formatVersion": 2,
            "id": dest_id,
            "title": name,
            "panorama": {
                "path": "panorama.png",
                "projection": "equirectangular",
                "width": 32,
                "height": 16,
                "initialYawDegrees": 0,
            },
            "environment": {"imageBasedLight": "lighting-ibl.png"},
            "thumbnail": "thumbnail.png",
            "provenance": "provenance.json",
        }
        destination.update(destination_extra)
        (dest_dir / "destination.json").write_bytes(EXAMPLES.json_bytes(destination))

        envelope = {
            "formatVersion": 1,
            "packageID": f"com.example.{name}",
            "contentVersion": "1.0.0",
            "minimumAppVersion": minimum_app,
            "contents": {
                "destinationIDs": [dest_id],
                "spaceIDs": [],
                "experienceIDs": [],
            },
        }
        (editable / "locusplace.json").write_bytes(EXAMPLES.json_bytes(envelope))
        return editable

    def _pack_and_validate(self, editable: Path, archive_name: str, app_version: str = "1.4.11") -> Path:
        archive = self.root / f"{archive_name}.locusplace"
        pack = subprocess.run(
            [sys.executable, str(PACK), "--current-app-version", app_version, str(editable), str(archive)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(pack.returncode, 0, pack.stdout + pack.stderr)
        validate = subprocess.run(
            [sys.executable, str(VALIDATE), "--current-app-version", app_version, str(archive)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        return archive

    def test_clean_room_sky_media_fireflies_point_lights_and_sound_view(self):
        pano_sha = hashlib.sha256(EXAMPLES.panorama_png(32, 16)).hexdigest()
        stars_json = EXAMPLES.json_bytes({
            "format": "locus-star-catalog",
            "version": 1,
            "frame": "horizontal",
            "source": "Synthetic horizon star table",
            "stars": [
                [15.0, 42.5, -1.46, 0.0],
                [-110.0, 28.0, 1.25, 0.85],
            ],
        })
        point_lights_json = EXAMPLES.json_bytes({
            "format": "locus-point-lights",
            "version": 1,
            "groups": [
                {
                    "id": "buoy-beacons",
                    "color": [1.0, 0.35, 0.1],
                    "behavior": {
                        "type": "blink",
                        "periodSeconds": 4.0,
                        "phaseSeconds": 0.5,
                        "minimum": 0.05,
                        "softness": 1.2,
                    },
                    "lights": [[0.42, 0.52, 0.08, 1.8]],
                },
                {
                    "id": "harbor-lights",
                    "color": [1.0, 0.85, 0.55],
                    "behavior": {"type": "twinkle", "amplitude": 0.18, "speed": 0.7},
                    "lights": [[0.58, 0.51, 0.04, 1.2]],
                },
            ],
        })
        editable = self._prepare_view_dir(
            "sky-media-sound",
            "destination.clean-room-sky",
            minimum_app="1.3.4",
            assets={
                "sky-mask.png": _gray8_png(32, 16, 255),
                "stars.json": stars_json,
                "point-lights.json": point_lights_json,
                "media-mask.png": _gray8_png(32, 16, 255),
                "surf-loop.mp4": _minimal_avc_mp4_bytes(16, 16),
                "audio/surf.wav": _pcm_wav_bytes(channels=2),
                "audio/brook.wav": _pcm_wav_bytes(channels=1),
                "audio/gull-1.wav": _pcm_wav_bytes(channels=1),
                "audio/gull-2.wav": _pcm_wav_bytes(channels=1),
            },
            destination_extra={
                "environment": {
                    "imageBasedLight": "lighting-ibl.png",
                    "skyGainEV": 0.0,
                    "exposureEV": 0.0,
                },
                "sky": {
                    "mask": "sky-mask.png",
                    "defaultMode": "free",
                    "stars": {
                        "catalog": "stars.json",
                        "twinkle": 1.0,
                        "milkyWay": {"style": "realistic", "brightness": 1.0},
                    },
                    "moon": {
                        "azimuthDegrees": 120.0,
                        "elevationDegrees": 28.0,
                        "drawnDiameterDegrees": 2.0,
                    },
                    "aurora": {
                        "palette": "classic",
                        "intensity": 1.0,
                        "arcs": [{"elevationDegrees": 34.0, "brightness": 1.0}],
                    },
                },
                "media": {
                    "version": 1,
                    "sourcePanoramaSHA256": pano_sha,
                    "mask": "media-mask.png",
                    "sources": [
                        {"id": "surf-loop", "title": "Surf Loop", "video": "surf-loop.mp4", "gain": 0.0}
                    ],
                    "regions": [
                        {
                            "id": "surf-band",
                            "source": "surf-loop",
                            "bounds": [0.35, 0.65, 0.48, 0.72],
                            "mappingBounds": [0.34, 0.66, 0.47, 0.73],
                            "sourceRect": [0.0, 0.0, 1.0, 1.0],
                        }
                    ],
                },
                "fireflies": {
                    "volumes": [
                        {
                            "id": "glade",
                            "centerMeters": [0.0, 0.8, -8.5],
                            "sizeMeters": [12.0, 3.0, 8.0],
                            "count": 80,
                            "color": [0.75, 1.0, 0.35],
                            "sizeMillimeters": 6,
                            "blink": {"periodSeconds": 3.0, "duty": 0.35, "jitter": 0.5},
                            "driftMetersPerSecond": 0.15,
                        }
                    ]
                },
                "pointLights": {"table": "point-lights.json"},
                "sound": {
                    "version": 2,
                    "backgroundPriority": 0,
                    "sources": [
                        {
                            "id": "surf",
                            "title": "Surf",
                            "role": "background",
                            "gain": 0.4,
                            "clips": ["audio/surf.wav"],
                            "placement": {"type": "ambient"},
                            "playback": {"type": "loop", "fadeInSeconds": 0.5, "fadeOutSeconds": 0.5},
                        },
                        {
                            "id": "brook",
                            "title": "Brook",
                            "role": "effect",
                            "gain": 0.3,
                            "clips": ["audio/brook.wav"],
                            "placement": {
                                "type": "point",
                                "frame": "view",
                                "point": {"azimuthDegrees": 15.0, "elevationDegrees": -5.0, "distanceMeters": 10.0},
                            },
                            "playback": {"type": "loop"},
                        },
                        {
                            "id": "gulls",
                            "title": "Coastal Gulls",
                            "role": "effect",
                            "gain": 0.25,
                            "clips": ["audio/gull-1.wav", "audio/gull-2.wav"],
                            "placement": {
                                "type": "region",
                                "frame": "view",
                                "azimuthCenterDegrees": -20.0,
                                "azimuthSpanDegrees": 90.0,
                                "elevationRangeDegrees": [5.0, 30.0],
                                "distanceRangeMeters": [18.0, 45.0],
                            },
                            "playback": {
                                "type": "random",
                                "intervalSeconds": [5.0, 15.0],
                                "maxConcurrent": 1,
                                "avoidImmediateRepeat": True,
                            },
                        },
                    ],
                },
                "localizations": {
                    "es": {
                        "mediaTitles": {"surf-loop": "Oleaje"},
                        "soundTitles": {"surf": "Oleaje", "brook": "Arroyo", "gulls": "Gaviotas"},
                    }
                },
            },
        )
        self._pack_and_validate(editable, "sky-media-sound")

    def test_clean_room_clouds_and_realtime_water_view(self):
        editable = self._prepare_view_dir(
            "clouds-water",
            "destination.clean-room-water",
            minimum_app="1.4.5",
            assets={
                "clouds-mask.png": EXAMPLES.grayscale_png(32, 16),
                "clouds-fill.png": EXAMPLES.rgb_png(32, 16),
                "water-bed-albedo.png": _rgba8_png(16, 16, (180, 170, 145, 128)),
                "water-macro.png": _gray8_png(16, 16, 128),
                "water-mask.png": _gray8_png(32, 16, 255),
            },
            destination_extra={
                "clouds": {
                    "mask": "clouds-mask.png",
                    "fill": "clouds-fill.png",
                    "horizonDegrees": 0.0,
                    "altitudeMeters": 1800,
                    "windMetersPerSecond": 4.0,
                },
                "water": {
                    "preset": "tropical-lagoon",
                    "regions": [
                        {
                            "id": "lagoon",
                            "shape": "disc",
                            "pose": {
                                "translationMeters": [0, -0.62, 0],
                                "orientationXYZW": [0, 0, 0, 1],
                            },
                            "sizeMeters": [120, 120],
                            "surface": {
                                "motion": "ocean",
                                "waveHeightMeters": 0.12,
                                "waveLengthMeters": 24.0,
                                "waveSpeed": 0.85,
                                "directionDegrees": 15.0,
                                "roughness": 0.16,
                                "detailFadeMeters": [20, 90],
                            },
                            "optics": {
                                "color": [0.02, 0.24, 0.28],
                                "absorptionPerMeter": [0.65, 0.18, 0.10],
                                "reflectionBlur": 1.2,
                                "sunGlint": 1.4,
                            },
                            "bed": {
                                "albedo": "water-bed-albedo.png",
                                "depthMeters": 1.8,
                                "reliefMeters": 0.4,
                                "tileMeters": 8.0,
                                "caustics": 0.8,
                                "deepening": {
                                    "startMeters": 30.0,
                                    "endMeters": 90.0,
                                    "depthMeters": 14.0,
                                    "color": [0.01, 0.08, 0.12],
                                    "rmsSlope": 0.05,
                                    "shoreSlope": 0.08,
                                    "waveSlopeScale": 2.2,
                                    "chopSlope": 0.12,
                                    "macro": {
                                        "map": "water-macro.png",
                                        "shallowMeters": 2.4,
                                        "tileMeters": 240.0,
                                        "coverage": 0.55,
                                        "fadeMeters": [20.0, 80.0],
                                    },
                                },
                            },
                            "blend": {
                                "panoramaMask": "water-mask.png",
                                "horizonSkirt": True,
                                "roomKeepOut": True,
                            },
                            "glow": {
                                "color": [0.1, 0.85, 1.0],
                                "strength": 1.1,
                                "mover": [0.0, -6.0, 3.5, 0.35],
                            },
                        }
                    ],
                },
            },
        )
        self._pack_and_validate(editable, "clouds-water")

    def test_clean_room_shore_16bit_bed_and_sun_path_contracts(self):
        # Encode a 32x32 big-endian 16-bit grayscale bed using the documented grid & quantization.
        width, height = 32, 32
        w_m, d_m = 64.0, 64.0
        cx, cz = 0.0, -26.0
        lo, hi = -6.0, 4.0
        rows_u16 = []
        for row in range(height):
            sz = cz - d_m / 2.0 + (row + 0.5) * (d_m / height)
            # Linear slope rising seaward (-58 m -> -5.0 m) to landward (+6 m -> +2.5 m).
            rel_height = -5.0 + ((sz + 58.0) / 64.0) * 7.5
            u16 = max(0, min(65535, round((rel_height - lo) / (hi - lo) * 65535)))
            rows_u16.append([u16] * width)
        self.assertLess(rows_u16[0][0], rows_u16[-1][0])

        editable = self._prepare_view_dir(
            "shore-surf",
            "destination.clean-room-shore",
            minimum_app="1.4.11",
            assets={"shore-bed.png": _gray16_png_from_samples(width, height, rows_u16)},
            destination_extra={
                "environment": {
                    "imageBasedLight": "lighting-ibl.png",
                    "directSun": {
                        "enabled": True,
                        "illuminanceLux": 45000,
                        "azimuthDegrees": -35.0,
                        "elevationDegrees": 32.0,
                    },
                },
                "shore": {
                    "version": 1,
                    "frame": {"translationMeters": [0, -0.62, 0], "yawDegrees": 0.0},
                    "bed": {
                        "path": "shore-bed.png",
                        "sizeMeters": [w_m, d_m],
                        "centerMeters": [cx, cz],
                        "heightRangeMeters": [lo, hi],
                    },
                    "swell": {"height": 0.9, "period": 1.0, "windChop": 0.4, "curl": 0.8},
                    "light": {
                        "azimuthDegrees": -35.0,
                        "elevationDegrees": 32.0,
                        "color": [1.0, 0.95, 0.88],
                        "night": 0.05,
                        "follow": "sun",
                    },
                    "sky": {"zenith": [0.16, 0.36, 0.68], "horizon": [0.56, 0.72, 0.86]},
                    "water": {
                        "deep": [0.015, 0.09, 0.14],
                        "shallowScatter": [0.05, 0.32, 0.34],
                        "crestScatter": [0.08, 0.38, 0.38],
                        "absorption": [0.48, 0.16, 0.11],
                        "clarity": 1.05,
                    },
                    "sand": {"dry": [0.46, 0.40, 0.32], "wet": [0.18, 0.15, 0.12], "wetBand": True},
                    "foam": 1.0,
                    "sparkle": 0.9,
                    "exposure": 1.0,
                },
            },
        )
        self._pack_and_validate(editable, "shore-surf")

        # Validate the documented 24h sunPath day/night + panoramaBlend contract directly.
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise AssertionError(message)

        sun_path = {
            "sunFreeSky": True,
            "startHour": 9,
            "dayDurationSeconds": 3600,
            "maxElevationDegrees": 60,
            "disc": {
                "skyMask": "sun-sky-mask.png",
                "angularSizeDegrees": 0.53,
            },
            "daySky": {"haze": 0.25, "exposure": 1.0},
            "panoramaGrade": {
                "stops": [
                    {"elevationDegrees": -12, "color": [0.18, 0.22, 0.34]},
                    {"elevationDegrees": 15, "color": [1.0, 0.96, 0.92]},
                ]
            },
            "light": {
                "midground": True,
                "stops": [
                    {"elevationDegrees": -12, "color": [0.1, 0.14, 0.28], "ambientEV": -2.5},
                    {"elevationDegrees": 30, "color": [1.2, 1.15, 1.05], "ambientEV": 0.0},
                ],
            },
            "panoramaBlend": {
                "path": "panorama-night.jpg",
                "dayElevationDegrees": 2,
                "nightElevationDegrees": -10,
                "nightGrade": [1.0, 1.0, 1.0],
            },
        }
        sun_path_contract.validate_definition(sun_path, require, lambda *_a, **_k: None)
        sun_path_contract.validate_day_night_destination(
            {
                "sky": {"mask": "sky-mask.png", "stars": {"twinkle": 1.0}},
                "midground": {"path": "midground.usdz"},
                "environment": {"sunPath": sun_path},
            },
            require,
            minimum=(1, 4, 11),
        )

        # Validate the two-mask cloud-preserving daylight View contract without numpy.
        two_mask_assets = {
            "sky-mask.png": _gray8_png(32, 16, 255),
            "sun-sky-mask.png": _gray8_png(32, 16, 128),
        }

        def check_gray_mask(rel: str, field: str, *, grayscale: bool = False) -> None:
            require(grayscale, f"{field} must require grayscale=True")
            raw = two_mask_assets.get(rel)
            require(raw is not None and raw.startswith(b"\x89PNG\r\n\x1a\n"), f"{field}: missing PNG {rel}")
            width, height, bit_depth, color_type, *_ = struct.unpack(">IIBBBBB", raw[16:29])
            require((bit_depth, color_type) == (8, 0) and width == height * 2, f"{field}: invalid 2:1 gray8 PNG")

        two_mask_sun_path = {
            "sunFreeSky": True,
            "startHour": 9,
            "dayDurationSeconds": 3600,
            "maxElevationDegrees": 32,
            "disc": {"skyMask": "sun-sky-mask.png", "angularSizeDegrees": 0.53},
            "daySky": {"haze": 0.25, "exposure": 1.0},
            "panoramaGrade": {
                "stops": [
                    {"elevationDegrees": -18, "color": [0.005, 0.008, 0.013]},
                    {"elevationDegrees": 0, "color": [0.56, 0.35, 0.22]},
                    {"elevationDegrees": 32, "color": [1.0, 1.0, 1.0]},
                ]
            },
            "light": {
                "stops": [
                    {"elevationDegrees": -18, "color": [0.01, 0.015, 0.025], "ambientEV": -3.0},
                    {"elevationDegrees": 0, "color": [1.0, 0.58, 0.32], "ambientEV": -0.8},
                    {"elevationDegrees": 32, "color": [1.0, 1.0, 1.0], "ambientEV": 0.0},
                ]
            },
        }
        check_gray_mask("sky-mask.png", "sky.mask", grayscale=True)
        sun_path_contract.validate_definition(two_mask_sun_path, require, check_gray_mask)
        sun_path_contract.validate_day_night_destination(
            {
                "sky": {"mask": "sky-mask.png", "stars": {"twinkle": 0.8}},
                "environment": {"sunPath": two_mask_sun_path},
            },
            require,
            minimum=(1, 4, 9),
        )

    def test_clean_room_midground_usdz_with_flowing_water_and_motion(self):
        usda = """#usda 1.0
(
    defaultPrim = "Root"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "Root"
{
    def Material "WaterFallbackMat"
    {
        token outputs:surface.connect = </Root/WaterFallbackMat/Preview.outputs:surface>
        def Shader "Preview"
        {
            uniform token info:id = "UsdPreviewSurface"
            color3f inputs:diffuseColor = (0.04, 0.09, 0.11)
            float inputs:roughness = 0.2
            token outputs:surface
        }
    }

    def Mesh "Terrain"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(-10, 0, -10), (10, 0, -10), (0, 0, -2)]
        normal3f[] normals = [(0, 1, 0), (0, 1, 0), (0, 1, 0)] (
            interpolation = "vertex"
        )
    }

    def Mesh "Grass_01"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(2, 0, -6), (2.2, 0, -6), (2.1, 0.6, -6)]
    }

    def Mesh "Distant_Peak_01"
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(-20, 0, -60), (20, 0, -60), (0, 18, -60)]
    }

    def Mesh "Stream_Foam" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(-1, 0.05, -8), (1, 0.05, -8), (0, 0.05, -4)]
        texCoord2f[] primvars:st = [(0, 0), (1, 0), (0.5, 1)] (
            interpolation = "vertex"
        )
        rel material:binding = </Root/WaterFallbackMat>
    }

    def Mesh "Waterfall_Main" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        int[] faceVertexCounts = [3]
        int[] faceVertexIndices = [0, 1, 2]
        point3f[] points = [(-1, 4, -14), (1, 4, -14), (0, 0.1, -12)]
        normal3f[] normals = [(0, 0.3, 0.95), (0, 0.3, 0.95), (0, 0.3, 0.95)] (
            interpolation = "vertex"
        )
        texCoord2f[] primvars:st = [(0.0, 0.0), (2.0, 0.0), (1.0, 2.4)] (
            interpolation = "vertex"
        )
        color3f[] primvars:displayColor = [(0.1, 0.8, 0.0), (0.1, 0.8, 0.0), (0.7, 0.9, 1.0)] (
            interpolation = "vertex"
        )
        rel material:binding = </Root/WaterFallbackMat>
    }
}
"""
        editable = self._prepare_view_dir(
            "midground-flow",
            "destination.clean-room-midground",
            minimum_app="1.4.9",
            assets={"midground.usdz": _usdz_from_usda(usda)},
            destination_extra={
                "midground": {
                    "path": "midground.usdz",
                    "terrainEntities": ["Terrain"],
                    "windSway": {
                        "entities": ["Grass_"],
                        "amplitudeDegrees": 4.0,
                        "periodSeconds": 3.5,
                        "directionDegrees": 45.0,
                        "wavelengthMeters": 18.0,
                    },
                    "skyEntities": ["Distant_Peak_"],
                    "textureFlow": [{"entities": ["Stream_Foam"], "uvVelocity": [0.0, -0.35]}],
                    "flowingWater": [
                        {
                            "entities": ["Waterfall_Main"],
                            "whiteness": 1.0,
                            "speed": 1.0,
                            "brightness": 1.0,
                            "mist": 1.0,
                            "spray": 1.0,
                            "shells": 1,
                            "plunges": [
                                {"position": [0.0, 0.2, -12.0], "width": 2.4, "height": 1.8, "yawDegrees": 0}
                            ],
                        }
                    ],
                }
            },
        )
        self._pack_and_validate(editable, "midground-flow")

    def test_clean_room_celestial_rings_advection_and_near_orbit_proof(self):
        # 1. Celestial v2 with oblate polarRadiusRatio + 1-px RGBA rings profileTexture.
        rings_png = _rgba8_png(64, 1, (215, 200, 175, 180))
        celestial_rings = self._prepare_view_dir(
            "celestial-rings",
            "destination.clean-room-rings",
            minimum_app="1.3.4",
            assets={
                "day.png": EXAMPLES.rgb_png(32, 16),
                "rings.png": rings_png,
            },
            destination_extra={
                "celestial": {
                    "version": 2,
                    "backgroundPanorama": "panorama.png",
                    "dayTexture": "day.png",
                    "yawDegrees": 0.0,
                    "elevationDegrees": 15.0,
                    "distanceMeters": 600.0,
                    "radiusMeters": 120.0,
                    "rotationPeriodSeconds": 600.0,
                    "polarRadiusRatio": 0.91,
                    "rings": {
                        "version": 1,
                        "profileTexture": "rings.png",
                        "innerRadiusRatio": 1.25,
                        "outerRadiusRatio": 2.35,
                        "brightness": 1.1,
                        "unlitBrightness": 0.85,
                    },
                }
            },
        )
        self._pack_and_validate(celestial_rings, "celestial-rings")

        # 2. Celestial v2 with 16-bit RGB stacked advection flowTexture.
        flow_width = 64
        keyframes = 2
        tile_height = flow_width // 2
        flow_rows = [[(32768, 32768, 16384 if r < tile_height else 0) for _ in range(flow_width)]
                     for r in range((keyframes + 1) * tile_height)]
        celestial_advection = self._prepare_view_dir(
            "celestial-advection",
            "destination.clean-room-advection",
            minimum_app="1.3.2",
            assets={
                "day.png": EXAMPLES.rgb_png(32, 16),
                "flow.png": _rgb16_png(flow_width, (keyframes + 1) * tile_height, flow_rows),
            },
            destination_extra={
                "celestial": {
                    "version": 2,
                    "backgroundPanorama": "panorama.png",
                    "dayTexture": "day.png",
                    "yawDegrees": 0.0,
                    "elevationDegrees": 12.0,
                    "distanceMeters": 600.0,
                    "radiusMeters": 100.0,
                    "rotationPeriodSeconds": 900.0,
                    "advection": {
                        "version": 1,
                        "flowTexture": "flow.png",
                        "ageKeyframes": keyframes,
                        "maxAgeRotations": 1.0,
                        "displacementRangeDegrees": 18.0,
                        "regenerationRotations": 1.0,
                        "crossfade": 0.25,
                    },
                }
            },
        )
        self._pack_and_validate(celestial_advection, "celestial-advection")

        # 3. Near-orbit v2 with horizontal starCatalog and computed fallback proof.
        near_orbit_def = {
            "version": 2,
            "bodyRadiusKilometers": 6371.0,
            "latitudeDegrees": 28.5,
            "longitudeDegrees": -80.6,
            "altitudeKilometers": 420.0,
            "bearingDegrees": 45.0,
            "pitchFromNadirDegrees": 70.0,
            "sunLatitudeDegrees": 15.0,
            "sunLongitudeDegrees": -30.0,
            "rotationPeriodSeconds": 5400.0,
            "cloudDriftRatio": 1.1,
            "cloudHeightKilometers": 8.0,
            "atmosphereHeightKilometers": 60.0,
            "dayTexture": "orbit-day.png",
            "nightTexture": "orbit-night.png",
            "cloudTexture": "orbit-clouds.png",
            "fallbackPanorama": "panorama.png",
            "skyMask": "orbit-sky-mask.png",
            "galaxyTexture": "orbit-galaxy.png",
            "starCatalog": "orbit-stars.json",
        }
        orbit_assets = {
            "orbit-day.png": EXAMPLES.rgb_png(32, 16),
            "orbit-night.png": EXAMPLES.rgb_png(32, 16),
            "orbit-clouds.png": _gray8_png(32, 16, 128),
            "orbit-sky-mask.png": _gray8_png(32, 16, 255),
            "orbit-galaxy.png": EXAMPLES.rgb_png(32, 16),
            "orbit-stars.json": EXAMPLES.json_bytes({
                "format": "locus-star-catalog",
                "version": 1,
                "frame": "horizontal",
                "source": "Synthetic orbital star catalog",
                "stars": [[0.0, 20.0, 0.5, 0.2]],
            }),
        }
        editable_orbit = self._prepare_view_dir(
            "near-orbit-v2",
            "destination.clean-room-orbit",
            minimum_app="1.3.2",
            assets=orbit_assets,
            destination_extra={"nearOrbit": near_orbit_def},
        )
        dest_dir = editable_orbit / "catalog" / "destinations" / "destination.clean-room-orbit"
        read_asset = lambda rel: (dest_dir / rel).read_bytes()
        proof = {
            "materialRevision": near_orbit_profile.material_revision(near_orbit_def),
            "profileToken": near_orbit_profile.profile_token(near_orbit_def, read_asset),
            "fallbackSHA256": hashlib.sha256(read_asset(near_orbit_def["fallbackPanorama"])).hexdigest(),
        }
        (dest_dir / near_orbit_profile.proof_path(near_orbit_def)).write_bytes(
            EXAMPLES.json_bytes(proof)
        )
        self._pack_and_validate(editable_orbit, "near-orbit-v2")


if __name__ == "__main__":
    unittest.main()
