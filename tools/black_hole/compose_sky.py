#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Compose the unlensed sky for a Locus black-hole View.

A dense procedural starfield (uniform on the sphere, power-law brightness,
blackbody tints) with optional flat photographs, such as nebulae, each placed
as a feathered patch on the plane facing a chosen direction and dimmed so it
stays far below the brightness of the accretion disc. The output is the
`--sky` input of bake_view.py, which bends it through the lens.

    python3 compose_sky.py sky.png \\
        --photo nebula-behind.png,0,12,133.6,0.522,0.1,fade \\
        --photo nebula-opposite.jpg,180,-12,50,0.5,0.2,add

Each --photo is PATH,YAW,ELEVATION,WIDTH,ROW,GAIN[,MODE]:

- YAW, ELEVATION: where the photo's centre sits, in degrees, using the
  panorama convention (yaw 0 is straight ahead, positive yaw turns right).
  Put the photo you want behind the hole at the hole's yaw and elevation.
- WIDTH: how many degrees wide the photo appears.
- ROW: which image row (0 top, 1 bottom) sits at that centre; 0.5 centres it.
- GAIN: linear brightness. Real nebulae are far fainter than a disc; 0.1 is
  about three stops down.
- MODE: `over` replaces the stars inside a feathered frame (only for a photo
  filled edge to edge); `add` adds the photo's light above its own black level,
  so a nebula photographed on black space has no visible frame; `fade` is
  `add` with an elliptical fall-off from 70 % of the way out, for a nebula that
  still glows at the edge of the photo.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import black_hole_lens as L  # noqa: E402
from imaging import bilinear, blackbody_rgb, linear_to_srgb, srgb_to_linear  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
MODES = ("over", "add", "fade")


def starfield(width, height, count, seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), np.float32)
    z = rng.uniform(-1, 1, count)
    lon = rng.uniform(0, 2 * math.pi, count)
    x, y = lon / (2 * math.pi) * width, np.arccos(z) / math.pi * height
    flux = (rng.pareto(1.6, count) + 1) * 0.004
    colour = blackbody_rgb(np.clip(rng.normal(6000, 2500, count), 2800, 20000)) * flux[:, None]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            xi = np.floor(x).astype(int) + dx
            yi = np.clip(np.floor(y).astype(int) + dy, 0, height - 1)
            weight = np.exp(-((xi + 0.5 - x) ** 2 + (yi + 0.5 - y) ** 2) / (2 * 0.55 ** 2))
            np.add.at(img, (yi, np.mod(xi, width)), colour * weight[:, None])
    return img


def add_photo(sky, photo, centre, width_degrees, centre_row, gain, feather=0.12, mode="over"):
    """Blend `photo` (linear) onto `sky` (linear) on the plane facing `centre`."""
    if mode not in MODES:
        raise ValueError("mode must be over, add or fade")
    height, width = sky.shape[:2]
    ph, pw = photo.shape[:2]
    right, up = L.tangent_basis(centre)
    ext_x = math.tan(math.radians(width_degrees) / 2)
    ext_y = ext_x * ph / pw
    for y0 in range(0, height, 256):
        d = L.equirect_directions(width, height, y0, min(height, y0 + 256))
        depth = L.dot(d, centre)
        with np.errstate(divide="ignore", invalid="ignore"):
            u = (L.dot(d, right) / depth / ext_x + 1) / 2
            v = (1 - L.dot(d, up) / depth / ext_y) / 2 + (centre_row - 0.5)
        inside = (depth > 0) & (u > 0) & (u < 1) & (v > 0) & (v < 1)
        if not inside.any():
            continue
        edge = np.minimum(np.minimum(u, 1 - u) * pw / ph, np.minimum(v, 1 - v))
        w = np.clip(edge[inside] / feather, 0, 1)
        w = (w * w * (3 - 2 * w))[:, None]
        rows = sky[y0:y0 + 256]
        sample = bilinear(photo, u[inside], v[inside])
        if mode in ("add", "fade"):
            if mode == "fade":
                # Elliptical, so an outpainted margin fades and the photo's core does not.
                radius = np.hypot(u[inside] - 0.5, v[inside] - 0.5) * 2
                t = np.clip((radius - 0.7) / 0.3, 0, 1)
                w = w * (1 - t * t * (3 - 2 * t))[:, None]
            rows[inside] = rows[inside] + np.maximum(sample - black_level(photo), 0) * gain * w
        else:
            rows[inside] = rows[inside] * (1 - w) + sample * gain * w


def black_level(photo):
    """Per-channel sky background of a photo: the median of its outer border."""
    h, w = photo.shape[:2]
    band = max(1, min(h, w) // 50)
    border = np.concatenate([photo[:band].reshape(-1, 3), photo[-band:].reshape(-1, 3),
                             photo[:, :band].reshape(-1, 3), photo[:, -band:].reshape(-1, 3)])
    return np.median(border, axis=0)


def parse_photo(spec):
    """PATH,YAW,ELEVATION,WIDTH,ROW,GAIN[,MODE] -> (path, yaw, elevation, width, row, gain, mode)."""
    fields = spec.split(",")
    mode = fields.pop() if fields[-1] in MODES else "over"
    if len(fields) < 6:
        raise ValueError("--photo needs PATH,YAW,ELEVATION,WIDTH,ROW,GAIN[,MODE]: %s" % spec)
    path = ",".join(fields[:-5])
    yaw, elevation, width, row, gain = (float(x) for x in fields[-5:])
    return path, yaw, elevation, width, row, gain, mode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("output", help="PNG (recommended) or JPEG to write")
    ap.add_argument("--width", type=int, default=8192, help="sky width in pixels (2:1; default 8192)")
    ap.add_argument("--stars", type=int, default=260000, help="number of procedural stars")
    ap.add_argument("--seed", type=int, default=11, help="starfield random seed")
    ap.add_argument("--photo", action="append", default=[], metavar="PATH,YAW,ELEVATION,WIDTH,ROW,GAIN[,MODE]",
                    help="place a photo; repeatable (see above)")
    args = ap.parse_args(argv)
    if args.width % 2:
        ap.error("--width must be even")
    sky = starfield(args.width, args.width // 2, args.stars, args.seed)
    for spec in args.photo:
        path, yaw, elevation, width, row, gain, mode = parse_photo(spec)
        photo = srgb_to_linear(np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255)
        add_photo(sky, photo, L.view_direction(yaw, elevation), width, row, gain, mode=mode)
    Image.fromarray((linear_to_srgb(sky) * 255 + 0.5).astype(np.uint8)).save(args.output)
    print("sky", args.output)


if __name__ == "__main__":
    main()
