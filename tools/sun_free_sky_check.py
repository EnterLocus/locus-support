#!/usr/bin/env python3
"""Heuristic sun-disc scan for authoring/publishing.

`check(path)` returns a list of `Finding`; it never mutates the image and is
deliberately only evidence for the caller's attestation policy.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from pathlib import Path
import math
from typing import Union
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Finding:
    x: int
    y: int
    diameter_degrees: float
    peak_luminance: float


def check(path: Union[str, Path], horizon_pitch_degrees: float = 0) -> list[Finding]:
    """Scan a bounded 2:1 image above its authored horizon (positive lowers it).

    This is a warning heuristic, not proof that the sky is sun-free. Bright
    cores must have a surrounding radial glare decline; flat cloud patches do
    not suffice. Finding coordinates refer to the bounded scan image.
    """
    if (
        not math.isfinite(horizon_pitch_degrees)
        or not -90 <= horizon_pitch_degrees <= 90
    ):
        raise ValueError("horizon pitch must be finite and within -90...90")
    with Image.open(path) as source:
        if source.width != source.height * 2:
            raise ValueError("sun heuristic requires a 2:1 equirectangular image")
        source.draft("RGB", (2048, 1024))
        image = source.convert("RGB")
        image.thumbnail((2048, 1024), Image.Resampling.LANCZOS)
        pixels = np.asarray(image, dtype=np.float32) / 255.0
        image.close()
    height, width = pixels.shape[:2]
    horizon = max(
        0, min(height, int(round(height * (0.5 + horizon_pitch_degrees / 180))))
    )
    if not horizon:
        return []
    upper = pixels[:horizon]
    luminance = upper @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    bright = (luminance >= 0.97) & ((upper.max(axis=2) - upper.min(axis=2)) <= 0.08)
    seen = np.zeros_like(bright, dtype=bool)
    findings = []
    pixel_angle = 2 * math.pi / width
    for y, x in zip(*np.where(bright)):
        if seen[y, x]:
            continue
        stack = [(y, x)]
        seen[y, x] = True
        points = []
        while stack:
            py, px = stack.pop()
            points.append((py, px))
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                ny, nx = py + dy, (px + dx) % width
                if 0 <= ny < horizon and bright[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        ys = np.array([point[0] for point in points])
        xs = np.array([point[1] for point in points])
        weights = np.cos(math.pi / 2 - (ys + 0.5) * math.pi / height)
        area = float(weights.sum()) * pixel_angle * math.pi / height
        diameter = math.degrees(2 * math.acos(max(-1, 1 - area / (2 * math.pi))))
        if not 0.25 <= diameter <= 8:
            continue
        cy = float(np.average(ys, weights=weights))
        angles = xs * pixel_angle
        cx = (
            math.atan2(
                float(np.average(np.sin(angles), weights=weights)),
                float(np.average(np.cos(angles), weights=weights)),
            )
            % (2 * math.pi)
        ) / pixel_angle
        latitude_scale = max(
            0.01, math.cos(math.pi / 2 - (cy + 0.5) * math.pi / height)
        )
        radius = max(1, math.sqrt(area / math.pi) / pixel_angle)
        # Longitude stretches near the pole; sample radial bands in the local
        # spherical frame, with wrapped x and no duplicate panorama pixels.
        reach_x = min(width // 2, int(math.ceil(4 * radius / latitude_scale)))
        reach_y = int(math.ceil(4 * radius))
        xx = np.arange(int(cx) - reach_x, int(cx) + reach_x + 1) % width
        yy = np.arange(max(0, int(cy) - reach_y), min(horizon, int(cy) + reach_y + 1))
        dx = ((xx - cx + width / 2) % width - width / 2) * latitude_scale
        distances = np.sqrt((yy[:, None] - cy) ** 2 + dx[None, :] ** 2)
        samples = luminance[np.ix_(yy, xx)]
        bands = []
        for low, high in ((1.2, 2), (2, 3), (3, 4)):
            values = samples[(distances >= radius * low) & (distances < radius * high)]
            bands.append(float(values.mean()) if values.size else None)
        if (
            all(value is not None for value in bands)
            and bands[0] > bands[1] + 0.03
            and bands[1] > bands[2] + 0.03
        ):
            peak = max(float(luminance[py, px]) for py, px in points)
            findings.append(Finding(round(cx) % width, round(cy), diameter, peak))
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--allow-sun-heuristic", metavar="REASON")
    parser.add_argument("--horizon-pitch-degrees", type=float, default=0)
    args = parser.parse_args()
    findings = check(args.path, args.horizon_pitch_degrees)
    if findings:
        print("sun heuristic: " + str(len(findings)) + " likely disc(s)")
        if not args.allow_sun_heuristic or not args.allow_sun_heuristic.strip():
            raise SystemExit(1)
        print("allowed: " + args.allow_sun_heuristic)


if __name__ == "__main__":
    main()
