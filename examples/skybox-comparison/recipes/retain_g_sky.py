#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-License-Identifier: Apache-2.0
"""Retain coherent reference sky with explicit foreground and wrap guards.

Local authoring only. The retained sky keeps the reference's original sample
resolution; this operation never creates or certifies additional image detail.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def blue_weight(pixels):
    red, green, blue = [pixels[:, :, channel] for channel in range(3)]
    return smooth((blue - green - 1) / 8) * smooth((blue - red - 4) / 14)


def candidate_sky_guard(pixels):
    red, green, blue = [pixels[:, :, channel] for channel in range(3)]
    white = (smooth((np.minimum(np.minimum(red, green), blue) - 215) / 20)
             * smooth((blue - red + 8) / 12) * smooth((blue - green + 8) / 12))
    return np.maximum(blue_weight(pixels), white)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skybox-tool', type=Path, required=True,
                        help='Public tools/skybox/skybox.py path')
    parser.add_argument('--reference', type=Path, required=True,
                        help='Coherent G equirectangular source')
    parser.add_argument('--candidate', type=Path, required=True,
                        help='Native merged, tone-corrected F equirectangular input')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--foreground-guard-pixels', type=int, default=8)
    parser.add_argument('--foreground-soften', type=float, default=2)
    parser.add_argument('--sky-full-v', type=float, default=.34)
    parser.add_argument('--sky-end-v', type=float, default=.41)
    parser.add_argument('--wrap-guard', action='store_true')
    parser.add_argument('--wrap-keep-degrees', type=float, default=2)
    parser.add_argument('--wrap-end-degrees', type=float, default=8)
    args = parser.parse_args()
    if not 0 <= args.sky_full_v < args.sky_end_v <= .5:
        parser.error('Sky fade must end above the horizon, with full-v < end-v')
    if args.foreground_guard_pixels < 0 or args.foreground_soften < 0:
        parser.error('Foreground guards must be nonnegative')
    if not 0 <= args.wrap_keep_degrees < args.wrap_end_degrees <= 180:
        parser.error('Wrap guard requires keep < end <= 180 degrees')
    module_spec = importlib.util.spec_from_file_location('public_skybox', args.skybox_tool)
    public = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(public)
    reference = public.image_array(args.reference)
    candidate = public.image_array(args.candidate)
    height, width = candidate.shape[:2]
    if width != 2 * height or reference.shape[1] != 2 * reference.shape[0]:
        parser.error('Both inputs must be exact 2:1 equirectangular images')
    output = candidate.copy()
    mask = np.zeros((height, width), dtype=np.uint8)
    columns = (np.arange(width, dtype=np.float64) + .5)[None, :] / width
    distance = np.minimum(columns, 1 - columns) * 360
    wrap_weight = (smooth((distance - args.wrap_keep_degrees)
                          / (args.wrap_end_degrees - args.wrap_keep_degrees))
                   if args.wrap_guard else 1)
    for start in range(0, height, 64):
        stop = min(height, start + 64)
        rows = (np.arange(start, stop, dtype=np.float64) + .5)[:, None] / height
        sampled = public.bilinear_equirect(reference, columns, rows).astype(np.float32)
        raw = candidate[start:stop].astype(np.float32)
        alpha = (np.minimum(blue_weight(sampled), candidate_sky_guard(raw))
                 * (1 - smooth((rows - args.sky_full_v) / (args.sky_end_v - args.sky_full_v)))
                 * wrap_weight)
        mask[start:stop] = np.rint(alpha * 255).astype(np.uint8)
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, 'L').save(args.audit_dir / 'unprotected-mask.png')
    if args.foreground_guard_pixels:
        guarded = Image.fromarray(mask, 'L').filter(
            ImageFilter.MinFilter(2 * args.foreground_guard_pixels + 1))
        softened = guarded.filter(ImageFilter.GaussianBlur(args.foreground_soften))
        # Do not let softening leak into the excluded foreground.
        mask = np.minimum(np.asarray(guarded), np.asarray(softened))
    for start in range(0, height, 64):
        stop = min(height, start + 64)
        rows = (np.arange(start, stop, dtype=np.float64) + .5)[:, None] / height
        sampled = public.bilinear_equirect(reference, columns, rows).astype(np.float32)
        raw = candidate[start:stop].astype(np.float32)
        alpha = mask[start:stop].astype(np.float32) / 255
        output[start:stop] = np.rint(raw * (1 - alpha[:, :, None])
                                   + sampled * alpha[:, :, None]).clip(0, 255).astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output).save(args.output)
    Image.fromarray(mask, 'L').save(args.audit_dir / 'source-sky-mask.png')
    difference = np.abs(output.astype(np.int16) - candidate.astype(np.int16))
    Image.fromarray(np.clip(difference * 4, 0, 255).astype(np.uint8)).save(
        args.audit_dir / 'difference-x4.png')
    report = {
        'method': 'Retain coherent reference upper sky with foreground exclusion and optional wrap exclusion',
        'parameters': {key: str(value) if isinstance(value, Path) else value
                       for key, value in vars(args).items()},
        'source': str(args.reference), 'source_native_dimensions': [reference.shape[1], reference.shape[0]],
        'input': str(args.candidate), 'output': str(args.output), 'output_dimensions': [width, height],
        'source_sha256': digest(args.reference), 'candidate_sha256': digest(args.candidate),
        'output_sha256': digest(args.output),
        'mask': str(args.audit_dir / 'source-sky-mask.png'),
        'source_blue_formula': 'smoothstep((B-G-1)/8)*smoothstep((B-R-4)/14)',
        'candidate_guard': 'max(source_blue_formula, bright neutral white guard)',
        'foreground_guard': 'minimum filter then min(guarded, GaussianBlur(guarded))',
        'wrap_guard': 'Keep F sky near original ERP wrap; smoothly admit reference sky farther away'
                      if args.wrap_guard else 'none',
        'raw_sources_unchanged': True, 'retained_sky_new_native_F_detail': False,
        'detail_claim': 'F foliage, ground and water remain; retained sky has reference sample density only',
        'nonzero_mask_fraction': float(np.mean(mask > 0)),
        'actual_changed_pixel_fraction': float(np.mean(np.max(difference, axis=2) > 0)),
        'ground_below_horizon_changed_pixels': int(np.count_nonzero(difference[(height + 1) // 2:])),
        'max_abs_RGB_change': difference.max(axis=(0, 1)).tolist(), 'paid_calls': 0,
    }
    (args.audit_dir / 'method.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
