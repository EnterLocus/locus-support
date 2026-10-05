# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""USDZ packing helpers and Swift tool discovery (Python 3.9 compatible).

A USDZ is an uncompressed zip whose entries start on 64-byte boundaries and whose
first entry is the root layer. ``zipfile`` alone does not align, so the writer here
pads each local header's extra field the way Pixar's usdzip does.
"""
import hashlib
import os
import struct
import subprocess
import sys
import zipfile

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWIFT_DIR = os.path.join(TOOL_ROOT, "swift")
BUILD_DIR = os.path.join(TOOL_ROOT, ".build")
LAYER_EXTENSIONS = (".usd", ".usda", ".usdc")


class ToolError(RuntimeError):
    pass


def read_usdz(path):
    """Return [(name, bytes)] in archive order, skipping directory entries."""
    with zipfile.ZipFile(path) as zf:
        return [(i.filename, zf.read(i)) for i in zf.infolist() if not i.filename.endswith("/")]


def write_usdz(path, entries):
    """Write [(name, bytes)] as a 64-byte aligned, stored USDZ. First entry = root layer."""
    if not entries:
        raise ToolError("a USDZ needs at least one entry")
    if not entries[0][0].lower().endswith(LAYER_EXTENSIONS):
        raise ToolError("the first USDZ entry must be the root layer, got %r" % entries[0][0])
    with open(path, "wb") as fp:
        with zipfile.ZipFile(fp, "w", zipfile.ZIP_STORED) as zf:
            for name, data in entries:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                header_end = fp.tell() + 30 + len(name.encode("utf-8"))
                pad = (-header_end) % 64
                if 0 < pad < 4:
                    pad += 64
                if pad:
                    info.extra = struct.pack("<HH", 0x1986, pad - 4) + b"\0" * (pad - 4)
                zf.writestr(info, data)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def usdcat_text(path):
    """Layer text of a USD/USDA/USDC/USDZ via Xcode's usdcat."""
    try:
        proc = subprocess.run(["/usr/bin/usdcat", path], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
    except OSError as exc:
        raise ToolError("usdcat is not available: %s" % exc)
    if proc.returncode != 0:
        raise ToolError("usdcat failed for %s: %s" % (path, proc.stderr.strip()))
    return proc.stdout


def usdcat_convert(src, dst):
    proc = subprocess.run(["/usr/bin/usdcat", src, "-o", dst], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        raise ToolError("usdcat failed converting %s: %s" % (src, proc.stderr.strip()))


def swift_binary(name):
    """Path of a compiled Swift tool, building it with swiftc on first use.

    ``ROS_BIN_DIR`` overrides the output directory. Rebuilds when the source is newer.
    """
    out_dir = os.environ.get("ROS_BIN_DIR") or BUILD_DIR
    source = os.path.join(SWIFT_DIR, name + ".swift")
    binary = os.path.join(out_dir, name)
    if not os.path.exists(source):
        raise ToolError("missing Swift source %s" % source)
    if os.path.exists(binary) and os.path.getmtime(binary) >= os.path.getmtime(source):
        return binary
    os.makedirs(out_dir, exist_ok=True)
    cmd = ["xcrun", "swiftc", "-O", source, "-o", binary]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    if proc.returncode != 0:
        raise ToolError("swiftc failed for %s:\n%s" % (name, proc.stdout))
    return binary


def run_inspect(path, extra_args=None):
    """Run the Swift inspector with --json and return the parsed report."""
    import json
    cmd = [swift_binary("inspect_usdz"), "--json", path] + list(extra_args or [])
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)
    if proc.returncode != 0:
        raise ToolError("inspect_usdz failed (exit %d): %s" % (proc.returncode, proc.stderr.strip() or proc.stdout.strip()))
    return json.loads(proc.stdout)


def eprint(*args):
    print(*args, file=sys.stderr)
