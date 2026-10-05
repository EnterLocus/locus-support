# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""train.py (against a fake `createml` executable) and reconstruct (input validation, dry run).

No training or photogrammetry job is started: the fake createml writes a few CSV lines and a
stub output, and reconstruct is only exercised up to input validation and --dry-run.
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import fixtures  # noqa: E402
import train  # noqa: E402
from lib import usdz  # noqa: E402

FAKE_CREATEML = """#!/bin/sh
# Stand-in for `xcrun createml`: records argv, writes the two fd streams and the output.
printf '%s\\n' "$@" > "$FAKE_ARGS"
echo "epoch,loss" >&4
echo "1,0.5" >&4
echo "training summary" >&5
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "--output" ]; then out="$2"; fi
  shift
done
if [ "$FAKE_FAIL" = "1" ]; then exit 3; fi
echo "fake reference object" > "$out"
"""


class TrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        usdz.swift_binary("inspect_usdz")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.fake = os.path.join(self.dir, "fake-createml")
        with open(self.fake, "w") as fp:
            fp.write(FAKE_CREATEML)
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IXUSR)
        self.args_file = os.path.join(self.dir, "argv.txt")
        os.environ["FAKE_ARGS"] = self.args_file
        os.environ["FAKE_FAIL"] = "0"
        self.addCleanup(lambda: os.environ.pop("FAKE_ARGS", None))
        self.addCleanup(lambda: os.environ.pop("FAKE_FAIL", None))
        self.source = fixtures.make_mug_usdz(os.path.join(self.dir, "mug.usdz"))
        self.out_dir = os.path.join(self.dir, "out")
        self.output = os.path.join(self.out_dir, "mug.referenceobject")

    def run_train(self, *extra, **kw):
        argv = ["--source", kw.get("source", self.source), "--output", kw.get("output", self.output)] + list(extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = train.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_dry_run_prints_exact_command_and_writes_nothing(self):
        avoid = fixtures.make_mug_usdz(os.path.join(self.dir, "white.usdz"))
        code, out, _ = self.run_train("--dry-run", "--avoid", avoid, "--avoid", self.source)
        self.assertEqual(code, 0)
        self.assertIn("xcrun createml objecttracker --source %s --output %s" % (self.source, self.output), out)
        self.assertIn("--training-mode extended", out)
        self.assertIn("--upright", out)
        self.assertIn("--objects-to-avoid %s --objects-to-avoid %s" % (avoid, self.source), out)
        self.assertIn("--csv-progress --csv-fd 4", out)
        self.assertIn("--summary-fd 5", out)
        self.assertIn("4>>%s" % self.output.replace(".referenceobject", ".progress.csv"), out)
        self.assertFalse(os.path.exists(self.out_dir))

    def test_mode_and_angle_flags(self):
        code, out, _ = self.run_train("--dry-run", "--mode", "standard", "--angles", "all", "--caffeinate")
        self.assertEqual(code, 0)
        self.assertIn("caffeinate -i xcrun createml", out)
        self.assertIn("--training-mode standard --all-angles", out)
        code, out, _ = self.run_train("--dry-run", "--angles", "front")
        self.assertIn("--front", out)

    def test_refuses_implausible_scale_unless_forced(self):
        huge = fixtures.make_mug_usdz(os.path.join(self.dir, "huge.usdz"), height=0.5)
        code, _, err = self.run_train("--createml", self.fake, source=huge)
        self.assertEqual(code, 2)
        self.assertIn("implausible-scale", err)
        self.assertFalse(os.path.exists(self.output))
        code, _, _ = self.run_train("--createml", self.fake, "--force", source=huge)
        self.assertEqual(code, 0)

    def test_refuses_bad_paths_and_existing_output(self):
        code, _, err = self.run_train("--dry-run", source=os.path.join(self.dir, "missing.usdz"))
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)
        code, _, err = self.run_train("--dry-run", output=os.path.join(self.dir, "x.bin"))
        self.assertEqual(code, 2)
        os.makedirs(self.out_dir)
        with open(self.output, "w") as fp:
            fp.write("old")
        code, _, err = self.run_train("--createml", self.fake)
        self.assertEqual(code, 2)
        self.assertIn("already exists", err)

    def test_full_run_writes_logs_and_manifest(self):
        avoid = fixtures.make_mug_usdz(os.path.join(self.dir, "white.usdz"))
        code, out, _ = self.run_train("--createml", self.fake, "--avoid", avoid, "--mode", "standard")
        self.assertEqual(code, 0, out)
        base = self.output[:-len(".referenceobject")]
        with open(base + ".progress.csv") as fp:
            self.assertEqual(fp.read(), "epoch,loss\n1,0.5\n")
        with open(base + ".summary.txt") as fp:
            self.assertEqual(fp.read(), "training summary\n")
        self.assertTrue(os.path.isdir(base + ".checkpoint"))
        with open(self.args_file) as fp:
            argv = fp.read().split("\n")
        self.assertIn("--checkpoint", argv)
        self.assertEqual(argv[argv.index("--objects-to-avoid") + 1], avoid)
        self.assertEqual(argv[argv.index("--training-mode") + 1], "standard")
        with open(base + ".run.json") as fp:
            manifest = json.load(fp)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["source"]["sha256"], usdz.sha256_file(self.source))
        self.assertEqual(manifest["avoid"][0]["sha256"], usdz.sha256_file(avoid))
        self.assertEqual(manifest["output"]["sha256"], usdz.sha256_file(self.output))
        self.assertEqual(manifest["attempts"][0]["exitCode"], 0)
        self.assertIn("started", manifest["attempts"][0])
        self.assertIn("ended", manifest["attempts"][0])
        self.assertIn("macOS", manifest["environment"])
        self.assertIn("xcodebuild", manifest["environment"])
        self.assertAlmostEqual(manifest["inspect"]["dimensionsMM"]["height"], 95.0, places=1)

    def test_failed_run_then_resume_keeps_attempt_history(self):
        os.environ["FAKE_FAIL"] = "1"
        code, _, _ = self.run_train("--createml", self.fake)
        self.assertEqual(code, 1)
        base = self.output[:-len(".referenceobject")]
        with open(base + ".run.json") as fp:
            manifest = json.load(fp)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["attempts"][0]["exitCode"], 3)
        self.assertNotIn("output", manifest)
        os.environ["FAKE_FAIL"] = "0"
        code, _, _ = self.run_train("--createml", self.fake)
        self.assertEqual(code, 0)
        with open(base + ".run.json") as fp:
            manifest = json.load(fp)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(len(manifest["attempts"]), 2)
        self.assertTrue(manifest["attempts"][1]["resumed"])
        self.assertTrue(manifest["attempts"][1]["command"].startswith("exec "))

    def test_custom_checkpoint_directory(self):
        checkpoint = os.path.join(self.dir, "ckpt")
        code, out, _ = self.run_train("--dry-run", "--checkpoint", checkpoint)
        self.assertIn("--checkpoint %s" % checkpoint, out)


class ReconstructTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = usdz.swift_binary("reconstruct")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_reconstruct(self, *args):
        proc = subprocess.run([self.binary] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    def test_missing_folder_is_a_clean_error(self):
        code, _, err = self.run_reconstruct("--input", os.path.join(self.tmp.name, "nope"),
                                            "--output", os.path.join(self.tmp.name, "o.usdz"))
        self.assertEqual(code, 2)
        self.assertIn("does not exist", err)

    def test_empty_folder_is_a_clean_error(self):
        images = os.path.join(self.tmp.name, "images")
        os.makedirs(images)
        with open(os.path.join(images, "notes.txt"), "w") as fp:
            fp.write("not an image")
        code, _, err = self.run_reconstruct("--input", images, "--output", os.path.join(self.tmp.name, "o.usdz"))
        self.assertEqual(code, 2)
        self.assertIn("no images", err)

    def test_argument_validation(self):
        out = os.path.join(self.tmp.name, "o.usdz")
        self.assertEqual(self.run_reconstruct("--output", out)[0], 2)
        self.assertEqual(self.run_reconstruct("--input", self.tmp.name, "--output", out, "--detail", "ultra")[0], 2)
        self.assertEqual(self.run_reconstruct("--input", self.tmp.name, "--output", out, "--ordering", "x")[0], 2)
        self.assertEqual(self.run_reconstruct("--input", self.tmp.name, "--output", out + ".obj")[0], 2)

    def test_dry_run_accepts_a_folder_of_images_without_reconstructing(self):
        images = os.path.join(self.tmp.name, "images")
        os.makedirs(images)
        for i in range(3):
            with open(os.path.join(images, "IMG_%04d.HEIC" % i), "wb") as fp:
                fp.write(b"stub")
        out = os.path.join(self.tmp.name, "o.usdz")
        code, stdout, _ = self.run_reconstruct("--input", images, "--output", out, "--detail", "reduced",
                                               "--ordering", "sequential", "--feature-sensitivity", "high",
                                               "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("3 images, 3 HEIC", stdout)
        self.assertIn("Detail:      reduced, ordering sequential, feature sensitivity high, object masking on", stdout)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
