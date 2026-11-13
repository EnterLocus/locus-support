# SPDX-License-Identifier: Apache-2.0
"""Real CLI regression tests for the provider-neutral skybox helper."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "skybox" / "skybox.py"


def synthetic_sphere(width=256, height=128):
    """An RGB encoding of direction, so compass, wrap, and pole errors show up."""
    columns = (np.arange(width, dtype=np.float64) + 0.5) / width
    rows = (np.arange(height, dtype=np.float64) + 0.5) / height
    yaw = (columns[None, :] - 0.5) * (2.0 * np.pi)
    polar = rows[:, None] * np.pi
    sin_polar = np.sin(polar)
    directions = np.stack((sin_polar * np.sin(yaw),
                           np.broadcast_to(np.cos(polar), (height, width)),
                           -sin_polar * np.cos(yaw)), axis=-1)
    return np.rint((directions + 1.0) * 127.5).clip(0, 255).astype(np.uint8)


class SkyboxCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp(prefix="skybox-test-"))
        self.input = self.tempdir / "sphere.png"
        Image.fromarray(synthetic_sphere()).save(self.input)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def run_cli(self, *arguments, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str, arguments)],
                                cwd=ROOT, capture_output=True, text=True)
        if ok and result.returncode:
            self.fail("CLI failed:\n" + result.stderr)
        if not ok:
            self.assertNotEqual(result.returncode, 0)
        return result

    def split(self, core=128, overlap=6):
        faces = self.tempdir / "faces"
        self.run_cli("split", self.input, faces, "--core-size", core, "--overlap", overlap)
        return faces

    def test_roll_is_a_cyclic_half_turn(self):
        output = self.tempdir / "rolled.png"
        self.run_cli("roll", self.input, output, "--degrees", 180)
        original = np.asarray(Image.open(self.input))
        rolled = np.asarray(Image.open(output))
        self.assertTrue(np.array_equal(rolled, np.roll(original, original.shape[1] // 2, axis=1)))

    def test_split_merge_roundtrip_compass_wrap_and_poles(self):
        faces = self.split()
        metadata = json.loads((faces / "metadata.json").read_text())
        self.assertEqual(metadata["storedSize"], round(128 * np.tan(np.deg2rad(51))))
        self.assertEqual(metadata["bases"]["nz"]["forward"], [0, 0, -1])
        # Probe beyond the 90-degree core midpoint.  This catches an incorrect
        # half-scale grid that can look self-consistent in a roundtrip.
        px = np.asarray(Image.open(faces / "px.png"))
        side = px.shape[0]
        row, column = side // 2, int(side * 0.85)
        x = 2.0 * (column + 0.5 - side / 2.0) / 128.0
        direction = np.array([1.0, 0.0, x])
        direction /= np.linalg.norm(direction)
        expected = np.rint((direction + 1.0) * 127.5)
        self.assertLess(np.abs(px[row, column].astype(float) - expected).max(), 5.0)

        output = self.tempdir / "merged.png"
        self.run_cli("merge", faces, output, "--width", 256, "--blend", 0.25)
        original = np.asarray(Image.open(self.input)).astype(float)
        merged = np.asarray(Image.open(output)).astype(float)
        self.assertLess(np.abs(merged - original).mean(), 4.5)
        # u=0/1 is the +Z wrap seam; the top and bottom rows are the poles.
        self.assertLess(np.abs(merged[:, 0] - original[:, 0]).mean(), 5.0)
        self.assertLess(np.abs(merged[0] - original[0]).mean(), 5.0)
        self.assertLess(np.abs(merged[-1] - original[-1]).mean(), 5.0)

    def test_invalid_overlap_and_non_equirectangular_input_are_rejected(self):
        self.run_cli("split", self.input, self.tempdir / "bad-overlap", "--overlap", 45, ok=False)
        square = self.tempdir / "square.png"
        Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(square)
        self.run_cli("split", square, self.tempdir / "not-equirect", ok=False)

    def test_merge_requires_every_matching_square_face_unless_normalized(self):
        faces = self.split()
        (faces / "ny.png").unlink()
        self.run_cli("merge", faces, self.tempdir / "missing.png", "--width", 256, ok=False)
        self.run_cli("split", self.input, faces, "--core-size", 128, "--overlap", 6)
        Image.open(faces / "px.png").resize((80, 80)).save(faces / "px.png")
        self.run_cli("merge", faces, self.tempdir / "mismatch.png", "--width", 256, ok=False)
        output = self.tempdir / "normalized.png"
        self.run_cli("merge", faces, output, "--width", 256, "--normalize-faces")
        report = json.loads((Path(str(output) + ".merge.json")).read_text())
        self.assertTrue(report["dimensionProvenance"]["px"]["normalized"])
        self.assertEqual(report["dimensionProvenance"]["px"]["input"], {"width": 80, "height": 80})

    def test_audit_and_compare_write_limited_diagnostic_reports(self):
        audit = self.tempdir / "audit"
        self.run_cli("audit", self.input, audit, "--review-size", 64)
        report = json.loads((audit / "audit.json").read_text())
        self.assertTrue(report["wrapJumpRatioDiagnosticOnly"])
        self.assertEqual(report["seamDirections"]["u=0.25"], "-X")
        self.assertTrue((audit / "contact-sheet.png").is_file())
        self.assertEqual(len(report["nativeReview"]["faceViews"]), 6)
        self.assertEqual(len(report["nativeReview"]["edgeViews"]), 12)
        self.assertTrue((audit / report["nativeReview"]["edgeViews"][0]).is_file())
        compare = self.tempdir / "compare.json"
        self.run_cli("compare", self.input, self.input, "--report", compare)
        fidelity = json.loads(compare.read_text())
        self.assertAlmostEqual(fidelity["lowPassLayoutNCC"], 1.0, places=12)
        self.assertIn("does not establish", fidelity["detailClaim"])


if __name__ == "__main__":
    unittest.main()
