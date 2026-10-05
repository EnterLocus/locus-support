#!/usr/bin/python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Wrapper around `xcrun createml objecttracker` for a USDZ -> .referenceobject run.

    ./train.py --source mug.usdz --output mug.referenceobject
    ./train.py --source mug.usdz --output mug.referenceobject --avoid white-mug.usdz --dry-run

What it adds over the bare command:
  * runs inspect_usdz first and refuses an implausible scale (or unreadable geometry)
    unless --force;
  * a checkpoint directory (default <output>.checkpoint) so an interrupted run resumes;
  * progress CSV and the training summary written next to the output;
  * a run manifest (<output>.run.json): Xcode/macOS versions, start/end time, SHA-256 of
    the source and every --avoid model, the exact command, exit status, output hash;
  * --dry-run prints the exact command and writes nothing.

Training takes many hours in extended mode. It is an ordinary foreground process; run it
under `nohup caffeinate -i ...` (see the README) or pass --caffeinate. Objects trained
with Xcode 27 need visionOS 27. Python 3.9 compatible.
"""
import argparse
import datetime
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import usdz  # noqa: E402

MANIFEST_VERSION = 1
ANGLE_FLAGS = {"upright": "--upright", "front": "--front", "all": "--all-angles"}
CSV_FD = 4
SUMMARY_FD = 5


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sidecar_paths(output):
    base = output[:-len(".referenceobject")] if output.endswith(".referenceobject") else output
    return {
        "progress": base + ".progress.csv",
        "summary": base + ".summary.txt",
        "manifest": base + ".run.json",
        "checkpoint": base + ".checkpoint",
    }


def build_command(args, paths):
    """Return (argv, shell_line). The shell line adds the two fd redirections."""
    argv = []
    if args.caffeinate:
        argv += ["caffeinate", "-i"]
    argv += shlex.split(args.createml) + [
        "objecttracker",
        "--source", args.source,
        "--output", args.output,
        "--training-mode", args.mode,
        ANGLE_FLAGS[args.angles],
        "--checkpoint", paths["checkpoint"],
        "--csv-progress", "--csv-fd", str(CSV_FD),
        "--summary-fd", str(SUMMARY_FD),
    ]
    for avoid in args.avoid:
        argv += ["--objects-to-avoid", avoid]
    shell_line = "exec %s %d>>%s %d>%s" % (
        " ".join(shlex.quote(a) for a in argv),
        CSV_FD, shlex.quote(paths["progress"]),
        SUMMARY_FD, shlex.quote(paths["summary"]))
    return argv, shell_line


def capture(cmd):
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True, timeout=30)
        return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def environment_info():
    return {
        "xcodebuild": capture(["xcodebuild", "-version"]),
        "developerDir": capture(["xcode-select", "-p"]),
        "macOS": capture(["sw_vers", "-productVersion"]) or platform.mac_ver()[0],
        "macOSBuild": capture(["sw_vers", "-buildVersion"]),
        "machine": platform.machine(),
        "cpu": capture(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "python": platform.python_version(),
        "note": "A reference object trained with Xcode 27 requires visionOS 27 or later.",
    }


def file_record(path):
    return {"path": os.path.abspath(path), "sha256": usdz.sha256_file(path),
            "bytes": os.path.getsize(path)}


def load_manifest(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except (OSError, ValueError):
            return None
    return None


def save_manifest(path, manifest):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)
        fp.write("\n")
    os.replace(tmp, path)


def check_inputs(args):
    """Return the inspect report for the source, or raise ToolError to refuse."""
    for path in [args.source] + list(args.avoid):
        if not os.path.isfile(path):
            raise usdz.ToolError("no such file: %s" % path)
        if not path.lower().endswith(".usdz"):
            raise usdz.ToolError("expected a .usdz file: %s" % path)
    if not args.output.endswith(".referenceobject"):
        raise usdz.ToolError("--output must end in .referenceobject")
    try:
        report = usdz.run_inspect(args.source, ["--min-height-mm", str(args.min_height_mm),
                                                "--max-height-mm", str(args.max_height_mm)])
    except usdz.ToolError as exc:
        if args.force:
            sys.stderr.write("warning: inspection failed but --force given: %s\n" % exc)
            return None
        raise usdz.ToolError("inspection failed (use --force to train anyway): %s" % exc)
    blocking = [w for w in report["warnings"] if w["severity"] == "error"]
    for w in report["warnings"]:
        sys.stderr.write("[%s] %s: %s\n" % (w["severity"], w["code"], w["message"]))
    if blocking and not args.force:
        raise usdz.ToolError(
            "refusing to train: %s. Fix the model (rescale_usdz) or pass --force."
            % ", ".join(w["code"] for w in blocking))
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", "-s", required=True, help="USDZ of the object to track")
    parser.add_argument("--output", "-o", required=True, help="output .referenceobject")
    parser.add_argument("--mode", choices=["extended", "standard"], default="extended")
    parser.add_argument("--angles", choices=sorted(ANGLE_FLAGS), default="upright",
                        help="viewing angles: upright (default), front or all")
    parser.add_argument("--avoid", action="append", default=[], metavar="USDZ",
                        help="USDZ of a look-alike object to ignore (repeatable)")
    parser.add_argument("--checkpoint", help="checkpoint directory (default: <output>.checkpoint)")
    parser.add_argument("--force", action="store_true", help="train even if inspection refuses the model")
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing output")
    parser.add_argument("--dry-run", action="store_true", help="print the command and exit; writes nothing")
    parser.add_argument("--caffeinate", action="store_true", help="prefix the command with `caffeinate -i`")
    parser.add_argument("--min-height-mm", type=float, default=60.0)
    parser.add_argument("--max-height-mm", type=float, default=200.0)
    parser.add_argument("--createml", default="xcrun createml", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.source = os.path.abspath(args.source)
    args.output = os.path.abspath(args.output)
    args.avoid = [os.path.abspath(a) for a in args.avoid]
    return args


def main(argv=None):
    args = parse_args(argv)
    paths = sidecar_paths(args.output)
    if args.checkpoint:
        paths["checkpoint"] = os.path.abspath(args.checkpoint)

    try:
        report = check_inputs(args)
    except usdz.ToolError as exc:
        print("train: %s" % exc, file=sys.stderr)
        return 2

    if os.path.exists(args.output) and not args.overwrite:
        print("train: %s already exists (use --overwrite to replace it)" % args.output, file=sys.stderr)
        return 2

    argv_cmd, shell_line = build_command(args, paths)
    if args.dry_run:
        print("Dry run. Nothing is written; this is what would run:\n")
        print("  " + shell_line.replace("exec ", "", 1))
        print("\nProgress CSV : %s\nSummary      : %s\nManifest     : %s\nCheckpoint   : %s"
              % (paths["progress"], paths["summary"], paths["manifest"], paths["checkpoint"]))
        if report:
            dims = report["dimensionsMM"]
            print("Model        : %.1f x %.1f x %.1f mm (height %.1f), %d warning(s)"
                  % (dims["x"], dims["y"], dims["z"], dims["height"], len(report["warnings"])))
        return 0

    exe = shlex.split(args.createml)[0]
    if shutil.which(exe) is None:
        print("train: %s not found on PATH" % exe, file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(paths["checkpoint"], exist_ok=True)

    manifest = load_manifest(paths["manifest"]) or {}
    resumed = bool(manifest) and manifest.get("status") != "completed"
    manifest.update({
        "manifestVersion": MANIFEST_VERSION,
        "tool": "tools/real-objects/train.py",
        "source": file_record(args.source),
        "avoid": [file_record(a) for a in args.avoid],
        "mode": args.mode,
        "angles": args.angles,
        "checkpoint": paths["checkpoint"],
        "environment": environment_info(),
        "inspect": None if report is None else {
            "dimensionsMM": report["dimensionsMM"], "mesh": report["mesh"],
            "warnings": report["warnings"], "forced": bool(args.force)},
        "status": "running",
    })
    attempt = {"started": utc_now(), "command": shell_line, "resumed": resumed}
    manifest.setdefault("attempts", []).append(attempt)
    save_manifest(paths["manifest"], manifest)

    print("Starting at %s%s" % (attempt["started"], " (resuming from checkpoint)" if resumed else ""))
    print("Command: %s" % shell_line.replace("exec ", "", 1))
    sys.stdout.flush()
    status = "failed"
    code = None
    try:
        proc = subprocess.Popen(["/bin/sh", "-c", shell_line])
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            try:
                code = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait()
            status = "interrupted"
        if code == 0 and os.path.exists(args.output):
            status = "completed"
        elif code == 0:
            status = "failed"
            attempt["error"] = "command exited 0 but wrote no output"
    finally:
        attempt["ended"] = utc_now()
        attempt["exitCode"] = code
        manifest["status"] = status
        if status == "completed":
            manifest["output"] = file_record(args.output)
            manifest["completed"] = attempt["ended"]
        save_manifest(paths["manifest"], manifest)
    print("Finished: %s (exit %s). Manifest: %s" % (status, code, paths["manifest"]))
    if status == "interrupted":
        print("Re-run the same command to resume from %s" % paths["checkpoint"])
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
