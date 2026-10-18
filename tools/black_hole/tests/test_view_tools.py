# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Profile, bake, pack and validate checks for the black-hole View tools.

A tiny View is baked with the real baker (a 512-pixel sky, a 256-texel lens
table, a 512 x 256 disc map), packed and validated, so the whole pipeline runs
in a few seconds without any downloaded image.
"""
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import bake_view as B  # noqa: E402
import black_hole_lens as L  # noqa: E402
import black_hole_profile as V  # noqa: E402
import imaging  # noqa: E402
import pack_view  # noqa: E402
from validate_view import ValidationError, calculate_content_hash, validate  # noqa: E402

DESTINATION = "destination.black-hole-test"


def profile():
    return {
        "version": 1, "skyTexture": "black-hole/sky.jpg", "lensTable": "black-hole/lens.png",
        "discMap": "black-hole/disc-map.png", "discTexture": "black-hole/disc-texture.png",
        "glowTexture": "black-hole/glow.png", "yawDegrees": 0, "elevationDegrees": 12, "observerRadius": 30,
        "discMapMaxAngleDegrees": 35,
        "disc": {"inner": 6, "outer": 16, "spin": 1, "iscoPeriodSeconds": 10, "regenerationSeconds": 12,
                 "profileExponent": 3, "peakTemperatureKelvin": 5200, "exposure": 1.1, "textureLogSpan": 0.5,
                 "contrast": 0.75},
        "doppler": 0, "glow": 0.3, "drift": {"degreesPerSecond": 0.75, "axis": "up"},
        "flares": {"intervalSeconds": 5, "lifeSeconds": 8, "brightness": 3, "radiusRange": [1.1, 2.2],
                   "width": 0.7, "arcLength": 2.5},
    }


def problems(value):
    found = []
    V.validate_definition(value, lambda ok, message: ok or found.append(message))
    return found


class ProfileTests(unittest.TestCase):
    def test_valid_profile_and_paths(self):
        self.assertEqual(problems(profile()), [])
        paths = V.validate_definition(profile(), lambda ok, message: None)
        self.assertEqual(set(paths), {"skyTexture", "lensTable", "discMap", "discTexture", "glowTexture"})

    def test_optional_fields_may_be_absent(self):
        value = profile()
        del value["flares"], value["glowTexture"]
        self.assertEqual(problems(value), [])

    def test_rejections(self):
        cases = {
            "unknown key": lambda v: v.update(extra=1),
            "null": lambda v: v.update(glow=None),
            "version": lambda v: v.update(version=2),
            "doppler range": lambda v: v.update(doppler=1.5),
            "outer too close": lambda v: v["disc"].update(outer=6.5),
            "spin": lambda v: v["disc"].update(spin=0),
            "bool spin": lambda v: v["disc"].update(spin=True),
            "disc unknown": lambda v: v["disc"].update(thickness=1),
            "drift axis": lambda v: v["drift"].update(axis="down"),
            "drift speed": lambda v: v["drift"].update(degreesPerSecond=3),
            "radius order": lambda v: v["flares"].update(radiusRange=[2.0, 1.5]),
            "absolute path": lambda v: v.update(skyTexture="/tmp/sky.jpg"),
            "shared file": lambda v: v.update(glowTexture="black-hole/lens.png"),
        }
        for name, mutate in cases.items():
            value = profile()
            mutate(value)
            self.assertTrue(problems(value), name)

    def test_schema_documents_the_profile(self):
        schema = json.loads((TOOLS / "view-black-hole-v1.schema.json").read_text())
        self.assertEqual(set(schema["required"]), V.REQUIRED)
        self.assertEqual(set(schema["properties"]), V.REQUIRED | V.OPTIONAL)
        self.assertEqual(set(schema["properties"]["disc"]["required"]), V.DISC_FIELDS)
        self.assertEqual(set(schema["properties"]["flares"]["required"]), V.FLARE_FIELDS)
        self.assertFalse(schema["additionalProperties"])

    def test_lens_code_round_trip(self):
        for phi in (0.0, 1e-3, math.pi, 7.5, 8 * math.pi):
            self.assertAlmostEqual(V.decode_lens(*V.encode_lens(phi)), phi, delta=1e-8)

    def test_example_recipe_matches_the_profile(self):
        recipe = json.loads((TOOLS / "recipes" / "ring.view.json").read_text())
        value = dict(recipe["blackHole"], version=1, discMapMaxAngleDegrees=35, **{
            field: "black-hole/%s.png" % field for field in ("skyTexture", "lensTable", "discMap", "discTexture")})
        value["disc"] = dict(value["disc"], exposure=1.0)
        self.assertEqual(problems(value), [])
        self.assertIn(B.PLACEHOLDER, recipe["provenance"]["creatorOrAgency"])
        self.assertFalse(recipe["destinationID"] in ("destination.black-hole-ring", "destination.black-hole-hover"),
                         "the example must not reuse a Locus Library View ID")


class BakeTests(unittest.TestCase):
    def test_png16_round_trip(self):
        rng = np.random.default_rng(3)
        with tempfile.TemporaryDirectory() as tmp:
            for shape in ((5, 7), (5, 7, 3), (5, 7, 4)):
                codes = rng.integers(0, 65536, shape, dtype=np.uint16)
                path = Path(tmp) / "x.png"
                imaging.write_png16(path, codes)
                np.testing.assert_array_equal(imaging.read_png16(path), codes)

    def test_lens_table_matches_direct_integration(self):
        value = profile()
        frame = B.Frame(value)
        codes, unresolved = B.bake_lens_table(value, frame, 256)
        self.assertEqual(unresolved, 0)
        phi = np.array([V.decode_lens(int(r), int(g)) for r, g in codes[0, :, :2]])
        alpha = B.lens_alpha(frame, 256)
        lens = L.Lens(value["observerRadius"], frame.c, rows=3000)
        right = frame.right
        for i in (40, 128, 200, 255):
            d = math.cos(alpha[i]) * frame.c + math.sin(alpha[i]) * right
            escape = lens.trace(d[None])["escape"][0]
            want = math.atan2(L.dot(escape, right), L.dot(escape, frame.e1))
            self.assertAlmostEqual(phi[i] % (2 * math.pi), want % (2 * math.pi), delta=1e-4)

    def test_flares_are_deterministic_and_start_empty(self):
        value = profile()
        self.assertEqual(B.flare_states(value, 0.0), [])
        first = B.flare_states(value, 6.0)
        self.assertEqual(first, B.flare_states(value, 6.0))
        self.assertTrue(all(6 * 1.1 <= r <= 6 * 2.2 for r, _, _ in first))
        self.assertLessEqual(len(B.flare_states(value, 500.0)), 3)


class ContentHashTests(unittest.TestCase):
    """The packer must write `files` and `contentHash` exactly as Locus expects.

    The golden values were produced by the Locus reference packer for the same
    fixture bytes; any change in record order, JSON formatting or hashing
    breaks them.
    """

    FILES = {
        "catalog/destinations/destination.golden/destination.json": b'{"formatVersion": 2}\n',
        "catalog/destinations/destination.golden/panorama.jpg": bytes(range(256)) * 3,
        "catalog/destinations/destination.golden/black-hole/lens.png": b"\x00\x01" * 500,
        "catalog/destinations/destination.golden/provenance.json": "{\"note\": \"café\"}\n".encode(),
    }
    CONTENT_HASH = "0be54d600c5c83cd79a5887a57fc74095671b1fe406ce80daa28ad69f21e2feb"
    MANIFEST_SHA256 = "ed9e5a2d603208f9b05c2bd7ace4fde287d4482b1e91978efeac5899b7ba7aac"

    def test_manifest_matches_the_reference_packer(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            for name, data in self.FILES.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (source / ".DS_Store").write_bytes(b"Finder junk is ignored")
            (source / "locusplace.json").write_text(json.dumps({
                "formatVersion": 1, "packageID": "destination.golden", "contentVersion": "1.0.0",
                "minimumAppVersion": "1.3.4",
                "contents": {"destinationIDs": ["destination.golden"], "spaceIDs": [], "experienceIDs": []}}))
            manifest, data, _ = pack_view.build_manifest(source)
        self.assertEqual(manifest["contentHash"], self.CONTENT_HASH)
        self.assertEqual(hashlib.sha256(data).hexdigest(), self.MANIFEST_SHA256)
        self.assertEqual([record["path"] for record in manifest["files"]], sorted(self.FILES))

    def test_content_hash_is_order_independent_and_byte_exact(self):
        records = [{"path": "catalog/b", "byteCount": 2, "sha256": "b" * 64},
                   {"path": "catalog/a", "byteCount": 10, "sha256": "a" * 64}]
        expected = hashlib.sha256(b"catalog/a\x0010\x00" + b"a" * 64 + b"\x00catalog/b\x002\x00" + b"b" * 64
                                  + b"\x00").hexdigest()
        self.assertEqual(calculate_content_hash(records), expected)
        self.assertEqual(calculate_content_hash(list(reversed(records))), expected)


class PackageTests(unittest.TestCase):
    """Bake a tiny View with the real baker, pack it and run the archive validator."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        yy, xx = np.mgrid[0:256, 0:512]
        sky = np.stack([40 + 30 * np.sin(xx / 40.0), 30 + 20 * np.cos(yy / 30.0), 60 + 0 * xx], -1).astype(np.uint8)
        Image.fromarray(sky).save(cls.tmp / "sky.png")
        cls.recipe = {
            "destinationID": DESTINATION, "contentVersion": "1.0.0", "title": "Test",
            "caption": "A test black hole.",
            "blackHole": {k: v for k, v in profile().items() if k not in (
                "version", "skyTexture", "lensTable", "discMap", "discTexture", "glowTexture",
                "discMapMaxAngleDegrees")},
            "bake": {"inclinationDegrees": 84, "rollDegrees": 6, "lensWidth": 256, "discMapWidth": 512,
                     "supersample": 1, "glowWidth": 256, "thumbnailHfovDegrees": 70, "glowSigmasDegrees": [1.0],
                     "exposureScale": 0.5,
                     "texture": {"width": 256, "height": 256, "azimuthCells": 4, "radialCells": 4, "octaves": 2,
                                 "gain": 0.5, "style": "ridged"}},
            "provenance": dict(json.loads((TOOLS / "recipes/ring.view.json").read_text())["provenance"],
                               creatorOrAgency="Test Author; NASA, ESA, CSA, and STScI",
                               requestedCredit="Test credit."),
        }
        del cls.recipe["blackHole"]["disc"]["exposure"]
        (cls.tmp / "recipe.json").write_text(json.dumps(cls.recipe))
        subprocess.run([sys.executable, str(TOOLS / "bake_view.py"), str(cls.tmp / "recipe.json"),
                        "--sky", str(cls.tmp / "sky.png"), "--out", str(cls.tmp / "src"),
                        "--panorama-width", "512", "--stills", "0,6", "--size", "64x36"],
                       check=True, capture_output=True)
        cls.view = cls.tmp / "src/catalog/destinations" / DESTINATION

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def archive(self, name, mutate=None):
        source = self.tmp / name
        shutil.copytree(self.tmp / "src", source)
        if mutate:
            path = source / "catalog/destinations" / DESTINATION / "destination.json"
            destination = json.loads(path.read_text())
            mutate(destination)
            path.write_text(json.dumps(destination))
        return source

    def test_baked_package_validates_and_matches_its_manifest(self):
        out = self.tmp / "ok.locusplace"
        summary = pack_view.pack(self.archive("ok"), out)
        self.assertEqual(summary["views"], 1)
        validate(out, "1.3.4")
        written = json.loads((self.view / "destination.json").read_text())["blackHole"]
        self.assertGreater(written["disc"]["exposure"], 0)
        with zipfile.ZipFile(out) as archive:
            manifest = json.loads(archive.read("locusplace.json"))
            self.assertEqual(manifest["minimumAppVersion"], "1.3.4")
            for record in manifest["files"]:
                data = archive.read(record["path"])
                self.assertEqual(len(data), record["byteCount"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            self.assertEqual(archive.getinfo("catalog/destinations/%s/panorama.jpg" % DESTINATION).compress_type,
                             zipfile.ZIP_STORED)
        self.assertEqual(calculate_content_hash(manifest["files"]), manifest["contentHash"])
        self.assertEqual(sorted(p.name for p in (self.tmp / "src-stills").iterdir()),
                         ["still-000.00s.png", "still-006.00s.png"])

    def test_archive_rejections(self):
        cases = {
            "fireflies": (lambda d: d.update(fireflies={}), "cannot coexist with other dynamic View profiles"),
            "sun path": (lambda d: d["environment"].update(sunPath={}), "cannot coexist with environment.sunPath"),
            "formats": (lambda d: d["blackHole"].update(discMap="black-hole/glow.png",
                                                       glowTexture="black-hole/disc-map.png"),
                        "discMap must be a 2:1 16-bit RGBA PNG"),
            "range": (lambda d: d["blackHole"]["disc"].update(contrast=9), "disc.contrast must be"),
            "panorama size": (lambda d: d["panorama"].update(width=1024, height=512), "dimensions do not match"),
        }
        for index, (name, (mutate, message)) in enumerate(cases.items()):
            with self.assertRaisesRegex(ValidationError, message, msg=name):
                pack_view.pack(self.archive("bad%d" % index, mutate), self.tmp / ("bad%d.locusplace" % index))
            self.assertFalse((self.tmp / ("bad%d.locusplace" % index)).exists(), name)

    def test_unreferenced_file_and_tampered_archive_are_rejected(self):
        source = self.archive("extra")
        (source / "catalog/destinations" / DESTINATION / "notes.txt").write_text("not referenced")
        with self.assertRaisesRegex(ValidationError, "not referenced"):
            pack_view.pack(source, self.tmp / "extra.locusplace")
        good = self.tmp / "tamper-src.locusplace"
        pack_view.pack(self.archive("tamper"), good)
        bad = self.tmp / "tampered.locusplace"
        with zipfile.ZipFile(good) as src, zipfile.ZipFile(bad, "w") as dst:
            for info in src.infolist():
                data = src.read(info)
                if info.filename.endswith("provenance.json"):
                    data = data.replace(b"Test credit.", b"Test credlt.")
                dst.writestr(info, data)
        with self.assertRaisesRegex(ValidationError, "SHA-256 mismatch"):
            validate(bad)

    def test_minimum_app_version(self):
        source = self.archive("old")
        manifest = json.loads((source / "locusplace.json").read_text())
        manifest["minimumAppVersion"] = "1.3.3"
        (source / "locusplace.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValidationError, "1.3.4"):
            pack_view.pack(source, self.tmp / "old.locusplace")
        with self.assertRaisesRegex(ValidationError, "requires Locus 1.3.4"):
            pack_view.pack(self.archive("new"), self.tmp / "new.locusplace", current_app_version="1.3.1")

    def test_first_frame_equals_panorama(self):
        prof = json.loads((self.view / "destination.json").read_text())["blackHole"]
        ref = B.Reference(self.view, prof)
        frame = B.render_equirect(ref, 512, 2)
        panorama = np.asarray(Image.open(self.view / "panorama.jpg"), dtype=np.float64)
        rendered = imaging.linear_to_srgb(frame) * 255
        self.assertLess(np.abs(panorama - rendered).mean(), 2.0)  # JPEG only

    def test_baker_refuses_the_example_placeholder(self):
        recipe = dict(self.recipe, provenance=json.loads((TOOLS / "recipes/ring.view.json").read_text())["provenance"])
        with self.assertRaisesRegex(SystemExit, "Your Name"):
            B.bake(recipe, self.tmp / "sky.png", self.tmp / "placeholder", log=lambda message: None)
        self.assertFalse((self.tmp / "placeholder").exists())


class OutpaintHelperTests(unittest.TestCase):
    """The optional fal.ai helper is never called over the network here."""

    def test_request_keeps_the_photo_centred_and_requires_consent(self):
        import outpaint_fal
        body = outpaint_fal.build_body(Image.new("RGB", (400, 200)), 100, (300, 300), "fade to black", 3)
        self.assertEqual(body["original_image_size"], [100, 50])
        self.assertEqual(body["original_image_location"], [100, 125])
        self.assertTrue(body["image_url"].startswith("data:image/jpeg;base64,"))
        with self.assertRaises(SystemExit):
            outpaint_fal.main(["in.jpg", "out.png", "--prompt", "x"])


if __name__ == "__main__":
    unittest.main()
