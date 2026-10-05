#!/usr/bin/python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Uniformly rescale a USDZ so one axis matches a measured real-world size.

    ./rescale_usdz model.usdz --height-mm 95
    ./rescale_usdz model.usdz --axis x --mm 112 -o model-fixed.usdz
    ./rescale_usdz model.usdz --scale 0.97

The model is measured with inspect_usdz, a uniform scale op is added at the outermost
position of every root Xformable prim (existing transforms, geometry, textures and
materials are left untouched), the archive is repacked 64-byte aligned, and the result is
re-inspected. Re-running on a rescaled file multiplies into the same op instead of
stacking new ones. Python 3.9 compatible.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import usdz  # noqa: E402

SCALE_ATTR = "xformOp:scale:locusRescale"
NOT_XFORMABLE = {"Scope", "Material", "Shader", "NodeGraph", "GeomSubset", "Skeleton",
                 "SkelAnimation", "BlendShape"}
VEC = r"\(\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*,\s*([-0-9.eE+]+)\s*\)"


def apply_root_scale(text, factor):
    """Insert/extend the scale op on each root Xformable prim of normalized usda text.

    Returns (new_text, [scaled prim names]). ``text`` must come from usdcat so that root
    prims start in column 0 and their direct attributes are indented four spaces.
    """
    lines = text.split("\n")
    out = []
    scaled = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r'^def\s+(\w+)\s+"([^"]+)"', line)
        if not match or match.group(1) in NOT_XFORMABLE:
            out.append(line)
            i += 1
            continue
        # Copy prim metadata up to the body-opening brace.
        j = i
        while lines[j] != "{":
            j += 1
        out.extend(lines[i:j + 1])
        k = j + 1
        end = k
        while lines[end] != "}":
            end += 1
        body = lines[k:end]
        new_body = []
        order_index = None
        scale_index = None
        for idx, b in enumerate(body):
            if re.match(r"^    (uniform )?token\[\] xformOpOrder = \[", b):
                order_index = idx
            if re.match(r"^    double3 " + re.escape(SCALE_ATTR) + r" = ", b):
                scale_index = idx
        if scale_index is not None:
            m = re.search(VEC, body[scale_index])
            if not m:
                raise usdz.ToolError("cannot parse existing %s on prim %s" % (SCALE_ATTR, match.group(2)))
            vals = [float(g) * factor for g in m.groups()]
            body[scale_index] = "    double3 %s = (%s)" % (SCALE_ATTR, ", ".join(repr(v) for v in vals))
            new_body = body
        else:
            scale_line = "    double3 %s = (%s)" % (SCALE_ATTR, ", ".join([repr(factor)] * 3))
            if order_index is None:
                new_body = [scale_line,
                            '    uniform token[] xformOpOrder = ["%s"]' % SCALE_ATTR] + body
            else:
                order_line = body[order_index]
                m = re.match(r"^(    (?:uniform )?token\[\] xformOpOrder = \[)(.*)(\].*)$", order_line)
                items = [s.strip() for s in m.group(2).split(",") if s.strip()]
                insert_at = 1 if items and items[0].strip('"') == "!resetXformStack!" else 0
                items.insert(insert_at, '"%s"' % SCALE_ATTR)
                body[order_index] = m.group(1) + ", ".join(items) + m.group(3)
                body.insert(order_index, scale_line)
                new_body = body
        out.extend(new_body)
        scaled.append(match.group(2))
        i = end  # the closing brace is appended by the next loop iteration
    if not scaled:
        raise usdz.ToolError("no root Xformable prim found to scale")
    return "\n".join(out), scaled


def rescale(src, dst, factor):
    entries = usdz.read_usdz(src)
    root_name, root_bytes = entries[0]
    with tempfile.TemporaryDirectory() as tmp:
        layer_in = os.path.join(tmp, "in" + os.path.splitext(root_name)[1])
        with open(layer_in, "wb") as fp:
            fp.write(root_bytes)
        text = usdz.usdcat_text(layer_in)
        new_text, scaled = apply_root_scale(text, factor)
        if root_name.lower().endswith(".usdc"):
            layer_text = os.path.join(tmp, "out.usda")
            with open(layer_text, "w", encoding="utf-8") as fp:
                fp.write(new_text)
            layer_out = os.path.join(tmp, "out.usdc")
            usdz.usdcat_convert(layer_text, layer_out)
            with open(layer_out, "rb") as fp:
                new_root = fp.read()
        else:
            new_root = new_text.encode("utf-8")
    usdz.write_usdz(dst, [(root_name, new_root)] + entries[1:])
    return scaled


def pick_axis(args):
    if args.height_mm is not None:
        return "height", args.height_mm
    if args.mm is None:
        raise usdz.ToolError("--axis needs --mm")
    return args.axis, args.mm


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="source .usdz")
    parser.add_argument("-o", "--output", help="output .usdz (default: <input>-rescaled.usdz)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--height-mm", type=float, help="real height along the model's up axis")
    group.add_argument("--axis", choices=["x", "y", "z", "height"], help="axis to match (with --mm)")
    group.add_argument("--scale", type=float, help="explicit uniform scale factor")
    parser.add_argument("--mm", type=float, help="real size in mm for --axis")
    parser.add_argument("--json", action="store_true", help="print a JSON summary instead of text")
    args = parser.parse_args(argv)

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        parser.error("no such file: %s" % src)
    dst = os.path.abspath(args.output) if args.output else os.path.splitext(src)[0] + "-rescaled.usdz"
    if os.path.realpath(dst) == os.path.realpath(src):
        parser.error("refusing to overwrite the input; choose a different --output")
    if not dst.lower().endswith(".usdz"):
        parser.error("--output must end in .usdz")

    try:
        before = usdz.run_inspect(src)
        if args.scale is not None:
            axis, target, factor = None, None, args.scale
        else:
            axis, target = pick_axis(args)
            actual = before["dimensionsMM"][axis]
            if actual <= 0:
                raise usdz.ToolError("cannot measure %s of %s" % (axis, src))
            factor = target / actual
        if not (factor > 0 and factor < 1000):
            raise usdz.ToolError("scale factor %r is not sensible" % factor)
        scaled = rescale(src, dst, factor)
        after = usdz.run_inspect(dst)
    except usdz.ToolError as exc:
        print("rescale_usdz: %s" % exc, file=sys.stderr)
        return 1

    summary = {"input": src, "output": dst, "scaleFactor": factor, "scaledPrims": scaled,
               "axis": axis, "targetMM": target,
               "beforeMM": before["dimensionsMM"], "afterMM": after["dimensionsMM"],
               "afterWarnings": after["warnings"]}
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        b, a = before["dimensionsMM"], after["dimensionsMM"]
        print("Scale factor %.6f applied to root prim(s): %s" % (factor, ", ".join(scaled)))
        print("Before: X %.1f  Y %.1f  Z %.1f mm (height %.1f)" % (b["x"], b["y"], b["z"], b["height"]))
        print("After:  X %.1f  Y %.1f  Z %.1f mm (height %.1f)" % (a["x"], a["y"], a["z"], a["height"]))
        print("Wrote %s\n" % dst)
        print("Re-inspection:")
        sys.stdout.flush()
        subprocess.call([usdz.swift_binary("inspect_usdz"), dst])
    return 0


if __name__ == "__main__":
    sys.exit(main())
