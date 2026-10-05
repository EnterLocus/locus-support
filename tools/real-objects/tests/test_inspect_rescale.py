# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""inspect_usdz and rescale_usdz against tiny generated fixtures (no network, seconds).

Run from the repo root:
    /usr/bin/python3 -m unittest discover -s tools/real-objects/tests -p 'test_*.py'
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import fixtures  # noqa: E402
import rescale_usdz  # noqa: E402
from lib import usdz  # noqa: E402


def codes(report):
    return {w["code"] for w in report["warnings"]}


class InspectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        usdz.swift_binary("inspect_usdz")  # compile once
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make(self, name, **kwargs):
        return fixtures.make_mug_usdz(os.path.join(self.tmp.name, name + ".usdz"), **kwargs)

    def test_metric_dimensions_and_mesh_stats(self):
        report = usdz.run_inspect(self.make("metres", height=0.095, r_bottom=0.032, r_top=0.040))
        dims = report["dimensionsMM"]
        self.assertAlmostEqual(dims["height"], 95.0, places=1)
        self.assertAlmostEqual(dims["x"], 80.0, places=1)
        self.assertAlmostEqual(dims["z"], 80.0, places=1)
        self.assertEqual(report["mesh"]["triangles"], 64)
        self.assertEqual(report["mesh"]["vertices"], 34)
        self.assertEqual(report["units"]["upAxis"], "Y")
        self.assertTrue(report["rigid"]["singleRigidModel"])
        self.assertEqual(report["textures"][0]["width"], 64)

    def test_meters_per_unit_is_applied(self):
        report = usdz.run_inspect(self.make("cm", height=9.5, r_bottom=3.2, r_top=4.0, meters_per_unit=0.01))
        self.assertAlmostEqual(report["dimensionsMM"]["height"], 95.0, places=1)
        self.assertAlmostEqual(report["units"]["metersPerUnit"], 0.01)

    def test_z_up_height_follows_up_axis(self):
        report = usdz.run_inspect(self.make("zup", up_axis="Z", extra_mesh=True))
        dims = report["dimensionsMM"]
        self.assertEqual(dims["upAxis"], "Z")
        self.assertAlmostEqual(dims["height"], 95.0, places=1)
        self.assertAlmostEqual(dims["z"], 95.0, places=1)
        self.assertAlmostEqual(dims["x"], 130.0, places=1)  # body plus offset handle mesh
        self.assertEqual(report["mesh"]["meshCount"], 2)
        self.assertIn("up-axis", codes(report))

    def test_implausible_scale_is_an_error(self):
        report = usdz.run_inspect(self.make("huge", height=0.5))
        warning = [w for w in report["warnings"] if w["code"] == "implausible-scale"]
        self.assertEqual(len(warning), 1)
        self.assertEqual(warning[0]["severity"], "error")
        tiny = usdz.run_inspect(self.make("tiny", height=0.0095, r_bottom=0.003, r_top=0.004))
        self.assertIn("implausible-scale", codes(tiny))

    def test_height_range_is_configurable(self):
        path = self.make("range", height=0.095)
        report = usdz.run_inspect(path, ["--min-height-mm", "100", "--max-height-mm", "300"])
        self.assertIn("implausible-scale", codes(report))

    def test_texture_warnings(self):
        self.assertIn("low-texture-resolution", codes(usdz.run_inspect(self.make("lowres", texture="tiny"))))
        flat = usdz.run_inspect(self.make("flat", texture="flat"))
        self.assertIn("uniform-texture", codes(flat))
        none = usdz.run_inspect(self.make("none", texture="none"))
        self.assertIn("no-texture", codes(none))
        missing = usdz.run_inspect(self.make("missing", texture_path="textures/absent.png"))
        self.assertIn("missing-texture", codes(missing))
        good = usdz.run_inspect(self.make("good", texture="checker"), ["--min-texture-px", "32"])
        self.assertNotIn("uniform-texture", codes(good))
        self.assertNotIn("low-texture-resolution", codes(good))
        self.assertNotIn("transparency", codes(good))

    def test_flat_normal_map_is_not_a_colour_texture(self):
        report = usdz.run_inspect(self.make("normal", normal_map=True), ["--min-texture-px", "32"])
        roles = dict((t["path"], t["role"]) for t in report["textures"])
        self.assertEqual(roles, {"textures/mug.png": "color", "textures/normal.png": "data"})
        self.assertNotIn("uniform-texture", codes(report))

    def test_transparency_warnings(self):
        self.assertIn("transparency", codes(usdz.run_inspect(self.make("opacity", opacity=0.5))))
        self.assertIn("transparency", codes(usdz.run_inspect(self.make("alpha", texture="alpha"))))

    def test_not_rigid_when_skinned(self):
        report = usdz.run_inspect(self.make("skel", skeleton=True))
        self.assertFalse(report["rigid"]["singleRigidModel"])
        self.assertIn("not-rigid", codes(report))

    def test_expectation_comparison(self):
        path = self.make("expect")
        report = usdz.run_inspect(path, ["--expect", "height=100"])
        comparison = report["comparisons"][0]
        self.assertAlmostEqual(comparison["scaleToMatch"], 100 / 95.0, places=4)
        self.assertFalse(comparison["within1Percent"])
        report = usdz.run_inspect(path, ["--expect", "height=95.5"])
        self.assertTrue(report["comparisons"][0]["within1Percent"])

    def test_text_output_and_bad_input(self):
        path = self.make("text")
        out = subprocess.run([usdz.swift_binary("inspect_usdz"), path], stdout=subprocess.PIPE,
                             universal_newlines=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("height along Y: 95.0 mm", out.stdout)
        bad = subprocess.run([usdz.swift_binary("inspect_usdz"), os.path.join(self.tmp.name, "nope.usdz")],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("no such file", bad.stderr)
        usage = subprocess.run([usdz.swift_binary("inspect_usdz")], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(usage.returncode, 2)


class RescaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        usdz.swift_binary("inspect_usdz")
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def run_rescale(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return rescale_usdz.main(list(args) + ["--json"])

    def test_height_rescale_matches_target_and_preserves_package(self):
        src = fixtures.make_mug_usdz(self.path("src.usdz"))
        dst = self.path("fixed.usdz")
        self.assertEqual(self.run_rescale(src, "--height-mm", "100", "-o", dst), 0)
        report = usdz.run_inspect(dst)
        self.assertAlmostEqual(report["dimensionsMM"]["height"], 100.0, places=1)
        self.assertAlmostEqual(report["dimensionsMM"]["x"], 80.0 * 100 / 95, places=1)  # uniform
        original = dict(usdz.read_usdz(src))
        rescaled = dict(usdz.read_usdz(dst))
        self.assertEqual(rescaled["textures/mug.png"], original["textures/mug.png"])
        self.assertEqual(report["mesh"]["triangles"], 64)
        self.assertEqual(report["textures"][0]["width"], 64)
        self.assertEqual(usdz.read_usdz(dst)[0][0], "mug.usda")

    def test_output_is_a_valid_aligned_usdz(self):
        src = fixtures.make_mug_usdz(self.path("src2.usdz"))
        dst = self.path("valid.usdz")
        self.run_rescale(src, "--scale", "0.9", "-o", dst)
        check = subprocess.run(["/usr/bin/usdchecker", dst], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_axis_option_and_cumulative_rescale(self):
        src = fixtures.make_mug_usdz(self.path("src3.usdz"))
        first = self.path("first.usdz")
        second = self.path("second.usdz")
        self.run_rescale(src, "--axis", "x", "--mm", "160", "-o", first)  # x 80 -> 160
        self.assertAlmostEqual(usdz.run_inspect(first)["dimensionsMM"]["height"], 190.0, places=1)
        self.run_rescale(first, "--height-mm", "95", "-o", second)
        text = usdz.usdcat_text(self.path("second.usdz"))
        self.assertEqual(text.count("xformOp:scale:locusRescale ="), 1)  # multiplied, not stacked
        self.assertAlmostEqual(usdz.run_inspect(second)["dimensionsMM"]["x"], 80.0, places=1)

    def test_binary_usdc_root_layer_is_kept_binary(self):
        usda = self.path("mug.usda")
        usdc = self.path("mug.usdc")
        with open(usda, "wb") as fp:
            fp.write(dict(usdz.read_usdz(fixtures.make_mug_usdz(self.path("base.usdz"))))["mug.usda"])
        usdz.usdcat_convert(usda, usdc)
        entries = usdz.read_usdz(self.path("base.usdz"))
        with open(usdc, "rb") as fp:
            usdz.write_usdz(self.path("crate.usdz"), [("mug.usdc", fp.read())] + entries[1:])
        dst = self.path("crate-fixed.usdz")
        self.assertEqual(self.run_rescale(self.path("crate.usdz"), "--height-mm", "90", "-o", dst), 0)
        root_name, root_bytes = usdz.read_usdz(dst)[0]
        self.assertEqual(root_name, "mug.usdc")
        self.assertTrue(root_bytes.startswith(b"PXR-USDC"))
        self.assertAlmostEqual(usdz.run_inspect(dst)["dimensionsMM"]["height"], 90.0, places=1)

    def test_refuses_to_overwrite_input_and_bad_scale(self):
        src = fixtures.make_mug_usdz(self.path("src4.usdz"))
        with self.assertRaises(SystemExit):
            rescale_usdz.main([src, "--scale", "1.1", "-o", src])
        self.assertEqual(self.run_rescale(src, "--scale", "-2", "-o", self.path("neg.usdz")), 1)
        self.assertFalse(os.path.exists(self.path("neg.usdz")))

    def test_apply_root_scale_text_rules(self):
        text = ('#usda 1.0\n(\n    defaultPrim = "r"\n)\n\n'
                'def Xform "r"\n{\n    float3 xformOp:translate = (0, 1, 0)\n'
                '    uniform token[] xformOpOrder = ["!resetXformStack!", "xformOp:translate"]\n\n'
                '    def Mesh "m"\n    {\n    }\n}\n\n'
                'def Scope "Looks"\n{\n}\n')
        new, scaled = rescale_usdz.apply_root_scale(text, 2.0)
        self.assertEqual(scaled, ["r"])  # Scope is not xformable
        self.assertIn('["!resetXformStack!", "xformOp:scale:locusRescale", "xformOp:translate"]', new)
        self.assertEqual(new.count("xformOp:scale:locusRescale\""), 1)
        with self.assertRaises(usdz.ToolError):
            rescale_usdz.apply_root_scale('def Scope "S"\n{\n}\n', 2.0)


if __name__ == "__main__":
    unittest.main()
