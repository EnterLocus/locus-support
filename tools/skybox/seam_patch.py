#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract a seam-centered perspective edit and reproject it with a local feather.

No API calls. The source panorama determines the final canvas; returned patch
size changes local samples only. Metadata binds the exact source and camera.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
import skybox


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(args):
    if not 0 < args.fov < 150 or args.size < 2:
        raise ValueError("use 0 < FOV < 150 and size >= 2")
    if not -89 < args.pitch < 89:
        raise ValueError("pitch must be between -89 and 89 degrees")
    source = skybox.image_array(args.source)
    if source.shape[1] != 2 * source.shape[0]:
        raise ValueError("source must be 2:1 ERP")
    yaw, pitch = map(math.radians, (args.yaw, args.pitch))
    forward = np.array([math.cos(pitch) * math.sin(yaw), math.sin(pitch),
                        -math.cos(pitch) * math.cos(yaw)])
    up = np.array([0., 1., 0.])
    if abs(np.dot(forward, up)) > .98:
        up = np.array([0., 0., 1.])
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    directions = skybox.perspective_directions(forward, args.size, args.fov)
    u, v = skybox.uv_from_direction(directions)
    skybox.save_array(args.output, np.rint(skybox.bilinear_equirect(source, u, v)))
    metadata = {
        "format": "skybox-local-patch-v1", "sourceSHA256": digest(args.source),
        "sourceSize": [source.shape[1], source.shape[0]],
        "inputPatchSHA256": digest(args.output), "inputPatchSize": args.size,
        "yaw": args.yaw, "pitch": args.pitch, "fov": args.fov,
        "forward": forward.tolist(), "right": right.tolist(), "down": down.tolist()
    }
    Path(args.metadata).write_text(json.dumps(metadata, indent=2) + "\n")


def insert(args):
    meta = json.loads(Path(args.metadata).read_text())
    if meta.get("format") != "skybox-local-patch-v1":
        raise ValueError("unsupported patch metadata")
    if digest(args.source) != meta["sourceSHA256"]:
        raise ValueError("source hash changed after extraction")
    for inner, outer in [(args.inner_x, args.outer_x), (args.inner_y, args.outer_y)]:
        if not 0 <= inner < outer <= 1:
            raise ValueError("feather bounds must satisfy 0 <= inner < outer <= 1")
    source = skybox.image_array(args.source)
    patch = skybox.image_array(args.patch)
    if patch.shape[0] != patch.shape[1]:
        raise ValueError("returned patch must be square and retain full camera FOV")
    height, width = source.shape[:2]
    if [width, height] != meta["sourceSize"]:
        raise ValueError("source dimensions changed")
    output = source.copy()
    mask = np.zeros((height, width), dtype=np.uint8)
    scale = math.tan(math.radians(meta["fov"]) / 2)
    changed = 0
    for row in range(0, height, 96):
        stop = min(row + 96, height)
        u = (np.arange(width)[None, :] + .5) / width
        v = (np.arange(row, stop)[:, None] + .5) / height
        direction = skybox.direction_from_uv(u, v)
        den = np.einsum("...i,i->...", direction, np.array(meta["forward"]))
        x = (np.einsum("...i,i->...", direction, np.array(meta["right"]))) / np.maximum(den, 1e-9) / scale
        y = (np.einsum("...i,i->...", direction, np.array(meta["down"]))) / np.maximum(den, 1e-9) / scale
        alpha = ((1 - skybox.smoothstep((np.abs(x)-args.inner_x)/(args.outer_x-args.inner_x)))
                 * (1 - skybox.smoothstep((np.abs(y)-args.inner_y)/(args.outer_y-args.inner_y)))
                 * (den > 0))
        alpha = np.rint(alpha * 255) / 255
        pixels = skybox.bilinear_square(patch, (x+1)*patch.shape[1]/2-.5,
                                       (y+1)*patch.shape[0]/2-.5)
        result = np.rint(source[row:stop]*(1-alpha[..., None]) +
                        pixels*alpha[..., None]).clip(0,255).astype(np.uint8)
        changed += int(np.any(result != source[row:stop], axis=2).sum())
        output[row:stop] = result
        mask[row:stop] = np.rint(alpha*255).astype(np.uint8)
    # PNG preserves exact outside-mask pixels. Encode a separate JPEG delivery derivative.
    if Path(args.output).suffix.lower() != ".png":
        raise ValueError("authoring output must be PNG to preserve untouched pixels")
    skybox.save_array(args.output, output)
    Image.fromarray(mask, "L").save(args.mask)
    data = {"format":"skybox-local-patch-result-v1", "sourceSHA256":digest(args.source),
            "patchSHA256":digest(args.patch), "outputSHA256":digest(args.output),
            "outputSize":[width,height], "returnedPatchSize":[patch.shape[1],patch.shape[0]],
            "fov":meta["fov"], "featherTangentBounds":[args.inner_x,args.outer_x,args.inner_y,args.outer_y],
            "changedPixels":changed, "outsideZeroAlphaUnchanged":bool(np.array_equal(output[mask==0],source[mask==0])),
            "note":"Camera fidelity requires visual review; native patch size does not prove alignment or detail."}
    Path(str(args.output)+".patch.json").write_text(json.dumps(data,indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("source"); ex.add_argument("output"); ex.add_argument("metadata")
    ex.add_argument("--yaw", type=float, required=True)
    ex.add_argument("--pitch", type=float, default=0)
    ex.add_argument("--fov", type=float, default=60)
    ex.add_argument("--size", type=int, default=1536)
    ins = sub.add_parser("insert")
    for name in ["source","patch","metadata","output","mask"]:
        ins.add_argument(name)
    ins.add_argument("--inner-x", type=float, default=.18)
    ins.add_argument("--outer-x", type=float, default=.65)
    ins.add_argument("--inner-y", type=float, default=.65)
    ins.add_argument("--outer-y", type=float, default=.95)
    args = parser.parse_args()
    (extract if args.command == "extract" else insert)(args)


if __name__ == "__main__":
    main()
