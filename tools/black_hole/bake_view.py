#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Bake a Locus black-hole View (`locus.view.black-hole.v1`) into a Package v2 source folder.

From a recipe and an unlensed sky (compose_sky.py) this writes an editable
Package v2 directory that pack_view.py turns into an importable archive:

- `black-hole/lens.png`, `disc-map.png`, `disc-texture.png`, `glow.png` and a
  copy of the sky, plus the `blackHole` profile in `destination.json`;
- `panorama.jpg`, the View at time zero rendered by `Reference` from the
  packaged files (what Locus shows when Motion is off, and its first live
  frame), `lighting.jpg` and `thumbnail.jpg` (the Library cover, centred on
  the hole).

`Reference` implements the per-pixel mathematics of the profile on the
packaged files, so `--frames` and `--stills` preview what Locus shows.

    python3 bake_view.py recipes/ring.view.json --sky sky.png --out ring-source \
        [--stills 0,5,10] [--frames ring-frames --seconds 20] [--control doppler=1]
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import black_hole_lens as L  # noqa: E402
import black_hole_profile as V  # noqa: E402
from imaging import (bilinear, blackbody_rgb, camera_directions, jitters, linear_to_srgb,  # noqa: E402
                     read_png16, srgb_to_linear, tonemap, write_png16)

Image.MAX_IMAGE_PIXELS = None
GOLDEN, PLASTIC, ROOT2 = 0.6180339887, 0.7548776662, 0.4142135624
FLARE_BIRTH = 0.5698402910
PLACEHOLDER = "Your Name"  # in the example recipe; the baker refuses to ship it


# ---------------------------------------------------------------- geometry helpers

class Frame:
    """The contract's hole frame: c, right, up, e1, shadow edge and lens K."""

    def __init__(self, profile):
        self.c = L.view_direction(profile["yawDegrees"], profile["elevationDegrees"])
        self.right, self.up = L.tangent_basis(self.c)
        self.e1 = -self.c
        r_o = profile["observerRadius"]
        self.alpha_c = V.critical_alpha(r_o)
        self.k = V.lens_k(r_o)
        self.max_angle = math.radians(profile["discMapMaxAngleDegrees"])

    def polar_directions(self, width, height, jitter=(0.5, 0.5), rows=None):
        u = (np.arange(width) + jitter[0]) / width
        v = (np.arange(*(rows or (0, height))) + jitter[1]) / height
        psi = (u - 0.5) * 2 * math.pi
        theta = self.max_angle * v ** 2
        psi, theta = np.meshgrid(psi, theta)
        side = np.sin(psi)[..., None] * self.right + np.cos(psi)[..., None] * self.up
        return np.cos(theta)[..., None] * self.c + np.sin(theta)[..., None] * side

    def polar_coordinates(self, d):
        alpha = np.arccos(np.clip(L.dot(d, self.c), -1, 1))
        psi = np.arctan2(L.dot(d, self.right), L.dot(d, self.up))
        return alpha, np.mod(0.5 + psi / (2 * math.pi), 1.0), np.sqrt(alpha / self.max_angle)


def lens_alpha(frame, width):
    x = np.arange(width) / (width - 1)
    return frame.alpha_c + (math.pi - frame.alpha_c) * np.exp(frame.k * (x - 1))


def bake_lens_table(profile, frame, width):
    alpha = lens_alpha(frame, width)
    r_o = profile["observerRadius"]
    s0 = math.sqrt(1 - 2 / r_o)
    b = r_o * np.sin(alpha) / s0
    steps = 0.001 * np.minimum(1.0, b / 2)
    outcome, phi, _ = L.integrate(np.full(width, 1 / r_o), np.cos(alpha) / b, steps, 8 * math.pi)
    phi = np.where(outcome == L.ESCAPED, phi, 8 * math.pi)
    codes = np.zeros((1, width, 3), np.uint16)
    for i, value in enumerate(phi):
        codes[0, i, 0], codes[0, i, 1] = V.encode_lens(float(value))
    return codes, int((outcome != L.ESCAPED).sum())


def find_max_angle(lens, disc, frame, margin=1.0):
    """Largest angle from the hole at which the disc is seen (degrees); `frame` spans 179."""
    hit = lens.trace(frame.polar_directions(720, 720), disc)["hit"]
    rows = np.flatnonzero(hit.any(axis=1))
    if not rows.size:
        raise ValueError("the disc is not visible")
    theta = 179 * ((rows.max() + 1) / 720) ** 2
    return min(179.0, math.ceil(theta + margin))


def bake_disc_map(lens, disc, frame, width, ss, chunk=64):
    height = width // 2
    acc = np.zeros((height, width, 4))
    hits = np.zeros((height, width))
    for y0 in range(0, height, chunk):
        y1 = min(height, y0 + chunk)
        for jx, jy in jitters(ss):
            dirs = frame.polar_directions(width, height, (jx, jy), (y0, y1))
            tr = lens.trace(dirs, disc)
            h = tr["hit"]
            acc[y0:y1, :, 0] += np.where(h, tr["radius"], 0)
            acc[y0:y1, :, 1] += np.where(h, np.cos(tr["azimuth"]), 0)
            acc[y0:y1, :, 2] += np.where(h, np.sin(tr["azimuth"]), 0)
            acc[y0:y1, :, 3] += np.where(h, tr["g"], 0)
            hits[y0:y1] += h
    n = ss * ss
    radius = acc[..., 0] / np.maximum(hits, 1)
    g = acc[..., 3] / np.maximum(hits, 1)
    valid = hits > 0
    # Hit-less texels borrow radius and g from neighbours (wrapping in u) so
    # bilinear filtering at the edge never blends in garbage; coverage is 0.
    for _ in range(6):
        grow = ~valid
        if not grow.any():
            break
        sr, sg, cnt = np.zeros_like(radius), np.zeros_like(g), np.zeros_like(radius)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            vr = np.roll(np.roll(valid, dx, 1), dy, 0)
            sr += np.where(vr, np.roll(np.roll(radius, dx, 1), dy, 0), 0)
            sg += np.where(vr, np.roll(np.roll(g, dx, 1), dy, 0), 0)
            cnt += vr
        grow &= cnt > 0
        radius = np.where(grow, sr / np.maximum(cnt, 1), radius)
        g = np.where(grow, sg / np.maximum(cnt, 1), g)
        valid |= grow
    radius = np.where(valid, radius, disc.outer)
    g = np.where(valid, g, 1.0)
    return radius, acc[..., 1] / n, acc[..., 2] / n, g


def encode_disc_map(radius, cx, sy, g, disc):
    def code(x):
        return np.clip(np.round(x * 65535), 0, 65535).astype(np.uint16)
    return np.stack([code((radius - disc.inner) / (disc.outer - disc.inner)), code(0.5 + 0.5 * cx),
                     code(0.5 + 0.5 * sy), code(g / 2)], -1)


# ---------------------------------------------------------------- turbulence texture

def periodic_perlin(x, y, period_x, period_y, seed):
    rng = np.random.default_rng(seed)
    angle = rng.uniform(0, 2 * math.pi, (period_y, period_x))
    gx, gy = np.cos(angle), np.sin(angle)
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    xf, yf = x - xi, y - yi

    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    u, v = fade(xf), fade(yf)
    total = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            ix, iy = (xi + dx) % period_x, (yi + dy) % period_y
            dot = gx[iy, ix] * (xf - dx) + gy[iy, ix] * (yf - dy)
            total = total + (u if dx else 1 - u) * (v if dy else 1 - v) * dot
    return total


def bake_disc_texture(width, height, azimuth_cells, radial_cells, octaves, gain, style, seed=17, band=256):
    """Tiling turbulence; N = 8*(value-0.5) has zero mean and unit variance."""
    x = (np.arange(width) + 0.5) / width
    total = np.empty((height, width))
    norm, amp = 0.0, 1.0
    for _ in range(octaves):
        norm += amp
        amp *= gain
    for y0 in range(0, height, band):  # in bands of rows, to keep memory low
        y = (np.arange(y0, min(height, y0 + band)) + 0.5) / height
        bx, by = np.meshgrid(x, y)
        acc, amp = 0.0, 1.0
        for o in range(octaves):
            px, py = azimuth_cells * 2 ** o, radial_cells * 2 ** o
            n = periodic_perlin(bx * px, by * py, px, py, seed * 31 + o) * 1.4
            acc = acc + amp * ((1 - 2 * np.abs(n)) ** 3 if style == "ridged" else n)
            amp *= gain
        total[y0:y0 + band] = acc
    total = total / norm
    field = (total - total.mean()) / (total.std() + 1e-9)
    return np.clip(np.round((0.5 + field / 8) * 65535), 0, 65535).astype(np.uint16)


# ---------------------------------------------------------------- reference reader

def emission_profile(r, inner, p):
    peak_x = ((2 * p + 1) / (2 * p)) ** 2
    peak = peak_x ** -p * (1 - math.sqrt(1 / peak_x))
    return np.clip((r / inner) ** -p * (1 - np.sqrt(inner / r)) / peak, 0, None)


def axis_rotation(axis, angle):
    axis = L.unit(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def flare_states(profile, t):
    """Live flares at flow time t: list of (radius, azimuth, envelope), newest last, at most 3."""
    flares, disc = profile.get("flares"), profile["disc"]
    if not flares:
        return []

    def h(j, s):
        return (s * (j + 1)) % 1.0
    live = []
    j_max = int(t // flares["intervalSeconds"]) + 1
    j_min = max(0, int((t - flares["lifeSeconds"]) // flares["intervalSeconds"]) - 1)
    for j in range(j_min, j_max + 1):
        born = (j + 0.3 * h(j, FLARE_BIRTH)) * flares["intervalSeconds"]
        age = t - born
        if not 0 < age < flares["lifeSeconds"]:
            continue
        lo, hi = flares["radiusRange"]
        radius = disc["inner"] * (lo + (hi - lo) * h(j, PLASTIC))
        omega = disc["spin"] * 2 * math.pi / disc["iscoPeriodSeconds"] * (disc["inner"] / radius) ** 1.5
        azimuth = 2 * math.pi * h(j, ROOT2) + omega * t
        live.append((radius, azimuth, math.sin(math.pi * age / flares["lifeSeconds"]) ** 2))
    return live[-3:]


def bilinear_tiled(img, u, v):
    """Bilinear sample wrapping both axes (a tiling texture)."""
    h, w = img.shape[:2]
    x, y = u * w - 0.5, v * h - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]

    def px(xx, yy):
        return img[np.mod(yy, h), np.mod(xx, w)].astype(np.float64)
    top = px(x0, y0) * (1 - fx) + px(x0 + 1, y0) * fx
    bottom = px(x0, y0 + 1) * (1 - fx) + px(x0 + 1, y0 + 1) * fx
    return top * (1 - fy) + bottom * fy


class Reference:
    """Per-pixel contract mathematics on the packaged files."""

    def __init__(self, view_dir, profile):
        self.p = profile
        self.frame = Frame(profile)
        lens = read_png16(view_dir / profile["lensTable"]).astype(np.float64)
        self.lens = 8 * math.pi * (lens[0, :, 0] * 65536 + lens[0, :, 1]) / (2 ** 32 - 1)
        sky = np.asarray(Image.open(view_dir / profile["skyTexture"]).convert("RGB"))
        self.sky = np.empty(sky.shape, np.float32)
        for y0 in range(0, sky.shape[0], 256):  # in bands, to keep memory low
            self.sky[y0:y0 + 256] = srgb_to_linear(sky[y0:y0 + 256].astype(np.float32) / 255)
        self.map = read_png16(view_dir / profile["discMap"]).astype(np.float32) / 65535
        self.texture = read_png16(view_dir / profile["discTexture"]).astype(np.float32)[..., None] / 65535
        self.glow = (read_png16(view_dir / profile["glowTexture"]).astype(np.float32) / 65535
                     if "glowTexture" in profile else None)

    def controls(self, **overrides):
        c = {"driftSpeed": self.p["drift"]["degreesPerSecond"], "flowSpeed": 1.0, "doppler": self.p["doppler"],
             "glow": self.p["glow"], "flares": 1.0, "detail": 1.0, "brightness": 1.0}
        c.update(overrides)
        return c

    def render(self, d, drift_angle, flow_time, ctl):
        p, f, disc = self.p, self.frame, self.p["disc"]
        shape = d.shape[:-1]
        d = d.reshape(-1, 3)
        alpha, u, v = f.polar_coordinates(d)
        captured = alpha < f.alpha_c + V.LENS_DELTA
        with np.errstate(divide="ignore", invalid="ignore"):
            x = 1 + np.log(np.maximum(alpha - f.alpha_c, 1e-300) / (math.pi - f.alpha_c)) / f.k
        pos = np.clip(x, 0, 1) * (self.lens.size - 1)
        i0 = np.clip(np.floor(pos).astype(np.int64), 0, self.lens.size - 2)
        phi = self.lens[i0] + (self.lens[i0 + 1] - self.lens[i0]) * (pos - i0)
        perp = d - L.dot(d, f.e1)[:, None] * f.e1
        norm = np.linalg.norm(perp, axis=1, keepdims=True)
        e2 = np.where(norm > 1e-12, perp / np.maximum(norm, 1e-300), f.up)
        escape = np.cos(phi)[:, None] * f.e1 + np.sin(phi)[:, None] * e2
        axis = {"up": f.up, "right": f.right, "view": f.c}[p["drift"]["axis"]]
        s = np.einsum("ij,nj->ni", axis_rotation(axis, -drift_angle), escape)
        su, sv = L.direction_to_equirect(s)
        col = np.where(captured[:, None], 0.0, bilinear(self.sky, su, sv, wrap_x=True))

        inside = alpha < f.max_angle
        if inside.any():
            m = bilinear(self.map, u[inside], v[inside], wrap_x=True)
            r = disc["inner"] + m[:, 0] * (disc["outer"] - disc["inner"])
            cx, sy = 2 * (m[:, 1] - 0.5), 2 * (m[:, 2] - 0.5)
            cov = np.minimum(1, np.hypot(cx, sy))
            phid = np.arctan2(sy, cx)
            g = 2 * m[:, 3]
            covered = cov > 0
            if covered.any():
                r, cov, phid, g = r[covered], cov[covered], phid[covered], g[covered]
                rgb = self.disc_rgb(r, phid, g, flow_time, ctl)
                idx = np.flatnonzero(inside)[covered]
                col[idx] = col[idx] * (1 - cov[:, None]) + tonemap(rgb) * cov[:, None]
            if self.glow is not None:
                glow = bilinear(self.glow, u[inside], v[inside], wrap_x=True)
                col[np.flatnonzero(inside)] += tonemap(4 * glow * ctl["glow"])
        return col.reshape(shape + (3,))

    def disc_rgb(self, r, phid, g, t, ctl):
        disc = self.p["disc"]
        omega = disc["spin"] * 2 * math.pi / disc["iscoPeriodSeconds"] * (disc["inner"] / r) ** 1.5
        period = disc["regenerationSeconds"]
        parts = []
        for k in (0, 1):
            phase = t / period + 0.5 * k
            cycle, frac = math.floor(phase), phase - math.floor(phase)
            w = 1 - abs(2 * frac - 1)
            if w <= 0:
                parts.append((0.0, 0.0))
                continue
            n = 2 * cycle + k + 1
            ou, ov = (GOLDEN * n) % 1.0, (PLASTIC * n) % 1.0
            tu = np.mod((phid - omega * frac * period) / (2 * math.pi) + ou, 1.0)
            tv = np.mod(ctl["detail"] * np.log(r / disc["inner"]) / disc["textureLogSpan"] + ov, 1.0)
            parts.append((w, 8 * (bilinear_tiled(self.texture, tu, tv)[:, 0] - 0.5)))
        norm = math.sqrt(sum(w * w for w, _ in parts)) or 1.0
        noise = sum(w * n for w, n in parts) / norm
        boost = 1.0
        if self.p.get("flares"):
            fl = self.p["flares"]
            for radius, azimuth, envelope in flare_states(self.p, t):
                dphi = np.angle(np.exp(1j * (phid - azimuth)))
                boost = boost + fl["brightness"] * ctl["flares"] * envelope * np.exp(
                    -((r - radius) / fl["width"]) ** 2 - (dphi / (fl["arcLength"] / radius)) ** 2)
        profile = emission_profile(r, disc["inner"], disc["profileExponent"])
        pattern = np.exp(disc["contrast"] * noise - disc["contrast"] ** 2 / 2) * boost
        dop = ctl["doppler"]
        intensity = g ** (4 * dop) * profile * pattern * disc["exposure"] * ctl["brightness"]
        temperature = disc["peakTemperatureKelvin"] * (np.maximum(profile, 1e-4) * boost) ** 0.25 * g ** dop
        return blackbody_rgb(temperature) * intensity[:, None]


# ---------------------------------------------------------------- glow

def blur_rows(image, sigma):
    """Gaussian blur along axis 0 (zero-padded, not wrapping), via FFT."""
    pad = int(math.ceil(4 * sigma)) + 1
    n = image.shape[0] + 2 * pad
    padded = np.zeros((n,) + image.shape[1:])
    padded[pad:pad + image.shape[0]] = image
    freq = np.fft.rfftfreq(n)
    kernel = np.exp(-2 * (math.pi * freq * sigma) ** 2)
    spec = np.fft.rfft(padded, axis=0) * kernel.reshape((-1,) + (1,) * (image.ndim - 1))
    return np.fft.irfft(spec, n=n, axis=0)[pad:pad + image.shape[0]]


def bake_glow(frame, disc_map, profile, width, sigmas_degrees):
    """Blurred bare-disc radiance (pattern 1, authored Doppler) / 4 in the polar mapping."""
    radius, cx, sy, g = disc_map
    disc = profile["disc"]
    dop = profile["doppler"]
    cov = np.minimum(1, np.hypot(cx, sy))
    hdr = np.empty(cov.shape + (3,))
    for y0 in range(0, cov.shape[0], 256):  # in bands of rows, to keep memory low
        rows = slice(y0, y0 + 256)
        p = emission_profile(np.clip(radius[rows], disc["inner"], disc["outer"]), disc["inner"],
                             disc["profileExponent"])
        rgb = blackbody_rgb(disc["peakTemperatureKelvin"] * np.maximum(p, 1e-4) ** 0.25 * g[rows] ** dop)
        hdr[rows] = rgb * (g[rows] ** (4 * dop) * p * disc["exposure"] * cov[rows])[..., None]
    # Resample to rows linear in angle, blur on the sphere (separable: polar
    # angle fixed, azimuth widened by 1/sin(angle) per row), resample back.
    h_src, w_src = cov.shape
    height = width // 2
    lin_rows = 2 * height
    theta = (np.arange(lin_rows) + 0.5) / lin_rows * frame.max_angle
    src_v = np.sqrt(theta / frame.max_angle) * h_src - 0.5
    y0 = np.clip(np.floor(src_v).astype(int), 0, h_src - 2)
    fy = np.clip(src_v - y0, 0, 1)[:, None, None]
    small = np.stack([np.asarray(Image.fromarray(hdr[..., k].astype(np.float32), "F")
                                 .resize((width, h_src), Image.BOX)) for k in range(3)], -1)
    lin = small[y0] * (1 - fy) + small[y0 + 1] * fy
    out = np.zeros_like(lin)
    freq = np.fft.rfftfreq(width)  # cycles per texel in azimuth
    for sigma in sigmas_degrees:
        s = math.radians(sigma)
        rows_sigma = s / frame.max_angle * lin_rows
        # Continue through the pole: rows above angle 0 are the opposite azimuth.
        pad = min(lin_rows, int(math.ceil(4 * rows_sigma)) + 1)
        across = np.roll(lin[:pad][::-1], width // 2, axis=1)
        blurred = blur_rows(np.concatenate([across, lin]), rows_sigma)[pad:]
        sin_t = np.maximum(np.sin(theta), 1e-3)
        az_sigma = np.minimum(s / sin_t / (2 * math.pi) * width, 4 * width)  # texels
        kernel = np.exp(-2 * (math.pi * freq[None, :] * az_sigma[:, None]) ** 2)
        spec = np.fft.rfft(blurred, axis=1) * kernel[..., None]
        out += np.fft.irfft(spec, n=width, axis=1)
    out /= len(sigmas_degrees)
    v = (np.arange(height) + 0.5) / height
    rows = np.clip(v ** 2 * lin_rows - 0.5, 0, lin_rows - 1)
    r0 = np.clip(np.floor(rows).astype(int), 0, lin_rows - 2)
    fr = (rows - r0)[:, None, None]
    glow = out[r0] * (1 - fr) + out[r0 + 1] * fr
    return np.clip(np.round(np.clip(glow / 4, 0, 1) * 65535), 0, 65535).astype(np.uint16)


# ---------------------------------------------------------------- package

def auto_exposure(disc_map, profile, target=1.6):
    radius, cx, sy, g = disc_map
    disc = profile["disc"]
    covered = np.hypot(cx, sy) > 0.5
    p = emission_profile(np.clip(radius[covered], disc["inner"], disc["outer"]), disc["inner"], disc["profileExponent"])
    intensity = g[covered] ** (4 * profile["doppler"]) * p
    return target / max(float(np.percentile(intensity, 99.5)), 1e-6)


def render_equirect(ref, width, ss, drift_angle=0.0, flow_time=0.0, chunk=128):
    height = width // 2
    ctl = ref.controls()
    out = np.zeros((height, width, 3), np.float32)
    for y0 in range(0, height, chunk):
        y1 = min(height, y0 + chunk)
        acc = 0.0
        for j in jitters(ss):
            acc = acc + ref.render(L.equirect_directions(width, height, y0, y1, j), drift_angle, flow_time, ctl)
        out[y0:y1] = acc / (ss * ss)
    return out


def render_thumbnail(ref, hfov_degrees, size=(1024, 512), ss=3):
    """Library cover: a perspective view centred on the hole at time zero.

    It frames the subject instead of shrinking the whole sky, and is rendered
    directly rather than resampled from the panorama so the disc stays sharp.
    """
    ctl = ref.controls()
    width, height = size
    acc = 0.0
    for j in jitters(ss):
        acc = acc + ref.render(camera_directions(ref.frame.c, width, height, hfov_degrees, j), 0.0, 0.0, ctl)
    return acc / (ss * ss)


def to_srgb8(linear, rows=256):
    """Linear RGB -> 8-bit sRGB, a band of rows at a time to keep memory low."""
    out = np.empty(linear.shape, np.uint8)
    for y0 in range(0, linear.shape[0], rows):
        out[y0:y0 + rows] = (linear_to_srgb(linear[y0:y0 + rows]) * 255 + 0.5).astype(np.uint8)
    return out


def save_jpeg(path, linear, quality=92, size=None):
    img = Image.fromarray(to_srgb8(linear))
    if size:
        img = img.resize(size, Image.LANCZOS)
    img.save(path, quality=quality)


def parse_controls(values):
    """NAME=VALUE pairs for the Edit View Motion controls, checked against their ranges."""
    controls = {}
    for item in values:
        name, _, raw = item.partition("=")
        if name not in V.CONTROLS:
            raise SystemExit("unknown control %r; choose from %s" % (name, ", ".join(sorted(V.CONTROLS))))
        value = float(raw)
        low, high, _ = V.CONTROLS[name]
        if not low <= value <= high:
            raise SystemExit("control %s must be %g-%g" % (name, low, high))
        controls[name] = value
    return controls


def bake(recipe, sky_path, out, panorama_width=8192, log=print):
    """Bake `recipe` (a dict) and the sky image into the Package v2 source folder `out`.

    Returns the destination directory inside `out`.
    """
    out = Path(out)
    if out.exists():
        raise SystemExit("refusing to overwrite %s" % out)
    if PLACEHOLDER in json.dumps(recipe.get("provenance", {})):
        raise SystemExit("replace %r in the recipe's provenance with your own name before baking" % PLACEHOLDER)
    if panorama_width % 2:
        raise SystemExit("the panorama width must be even")
    sky = Image.open(sky_path).convert("RGB")
    if sky.width != 2 * sky.height:
        raise SystemExit("the sky must be 2:1")
    dest_id = recipe["destinationID"]
    view_dir = out / "catalog" / "destinations" / dest_id
    (view_dir / "black-hole").mkdir(parents=True)

    profile = json.loads(json.dumps(recipe["blackHole"]))
    profile.update(version=1, skyTexture="black-hole/sky.jpg", lensTable="black-hole/lens.png",
                   discMap="black-hole/disc-map.png", discTexture="black-hole/disc-texture.png",
                   glowTexture="black-hole/glow.png")
    bake_settings = recipe["bake"]
    frame_probe = Frame(dict(profile, discMapMaxAngleDegrees=179))
    t0 = time.time()
    lens = L.Lens(profile["observerRadius"], frame_probe.c)
    d = profile["disc"]
    disc = L.Disc(frame_probe.c, bake_settings["inclinationDegrees"], bake_settings["rollDegrees"],
                  d["inner"], d["outer"], d["spin"])
    profile["discMapMaxAngleDegrees"] = find_max_angle(lens, disc, frame_probe)
    frame = Frame(profile)
    log("disc within %s deg" % profile["discMapMaxAngleDegrees"])

    codes, unresolved = bake_lens_table(profile, frame, bake_settings["lensWidth"])
    write_png16(view_dir / profile["lensTable"], codes)
    log("lens table %d (%d unresolved at the critical end) %.0fs"
        % (bake_settings["lensWidth"], unresolved, time.time() - t0))

    disc_map = bake_disc_map(lens, disc, frame, bake_settings["discMapWidth"], bake_settings["supersample"])
    if profile["disc"].get("exposure") is None:
        profile["disc"]["exposure"] = round(
            auto_exposure(disc_map, profile) * bake_settings.get("exposureScale", 1.0), 6)
    write_png16(view_dir / profile["discMap"], encode_disc_map(*disc_map, disc))
    log("disc map %d %.0fs" % (bake_settings["discMapWidth"], time.time() - t0))

    tex = bake_settings["texture"]
    write_png16(view_dir / profile["discTexture"], bake_disc_texture(
        tex["width"], tex["height"], tex["azimuthCells"], tex["radialCells"], tex["octaves"], tex["gain"],
        tex["style"]))
    write_png16(view_dir / profile["glowTexture"],
                bake_glow(frame, disc_map, profile, bake_settings["glowWidth"], bake_settings["glowSigmasDegrees"]))
    sky.save(view_dir / profile["skyTexture"], quality=95)
    log("textures %.0fs" % (time.time() - t0))

    problems = []
    V.validate_definition(profile, lambda ok, message: ok or problems.append(message))
    if problems:
        raise SystemExit("profile invalid: " + "; ".join(problems))

    del lens, disc_map  # free the bake buffers before rendering
    ref = Reference(view_dir, profile)
    panorama = render_equirect(ref, panorama_width, 2)
    save_jpeg(view_dir / "panorama.jpg", panorama)
    lighting = np.asarray(Image.fromarray(np.clip(panorama * 255, 0, 255).astype(np.uint8))
                          .resize((1024, 512), Image.BOX).filter(ImageFilter.GaussianBlur(6)),
                          dtype=np.float32) / 255
    save_jpeg(view_dir / "lighting.jpg", lighting, size=None)
    save_jpeg(view_dir / "thumbnail.jpg", render_thumbnail(ref, bake_settings["thumbnailHfovDegrees"]), quality=95)
    log("panorama %.0fs" % (time.time() - t0))

    destination = {
        "formatVersion": 2, "id": dest_id, "title": recipe["title"], "caption": recipe["caption"],
        "panorama": {"path": "panorama.jpg", "projection": "equirectangular", "width": panorama_width,
                     "height": panorama_width // 2, "initialYawDegrees": 0},
        "thumbnail": "thumbnail.jpg", "provenance": "provenance.json",
        "environment": {"imageBasedLight": "lighting.jpg", "skyGainEV": 0, "exposureEV": 0, "condition": "night",
                        "directSun": {"enabled": False, "azimuthDegrees": 0, "elevationDegrees": 20,
                                      "illuminanceLux": 0}},
        "blackHole": profile,
    }
    (view_dir / "destination.json").write_text(json.dumps(destination, indent=2) + "\n")
    (view_dir / "provenance.json").write_text(json.dumps(recipe["provenance"], indent=2) + "\n")
    (out / "locusplace.json").write_text(json.dumps({
        "formatVersion": 1, "packageID": recipe.get("packageID", dest_id), "contentVersion": recipe["contentVersion"],
        "minimumAppVersion": ".".join(map(str, V.MINIMUM_APP)),
        "contents": {"destinationIDs": [dest_id], "experienceIDs": [], "spaceIDs": []}}, indent=2) + "\n")
    log("package source %s" % out)
    return view_dir


def render_stills(ref, profile, out_dir, times, size, controls):
    """Perspective stills centred on the hole at the given seconds of foreground time."""
    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = (int(x) for x in size.split("x"))
    cams = [camera_directions(ref.frame.c, width, height, 90, j) for j in jitters(2)]
    ctl = ref.controls(**controls)
    written = []
    for t in times:
        drift = math.radians(ctl["driftSpeed"]) * t
        img = sum(ref.render(c, drift, t * ctl["flowSpeed"], ctl) for c in cams) / len(cams)
        path = out_dir / ("still-%06.2fs.png" % t)
        Image.fromarray((linear_to_srgb(img) * 255 + 0.5).astype(np.uint8)).save(path)
        written.append(path)
    return written


def render_frames(ref, profile, frames, seconds, fps, size, controls):
    """A numbered PNG sequence (and reference.mp4 when ffmpeg is installed)."""
    frames.mkdir(parents=True, exist_ok=True)
    width, height = (int(x) for x in size.split("x"))
    cams = [camera_directions(ref.frame.c, width, height, 90, j) for j in jitters(2)]
    ctl = ref.controls(**controls)
    for i in range(int(seconds * fps)):
        t = i / fps
        drift = math.radians(ctl["driftSpeed"]) * t
        img = sum(ref.render(c, drift, t * ctl["flowSpeed"], ctl) for c in cams) / len(cams)
        Image.fromarray((linear_to_srgb(img) * 255 + 0.5).astype(np.uint8)).save(frames / ("%05d.png" % i))
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.png"),
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(frames / "reference.mp4")],
                       check=True)
        print("video", frames / "reference.mp4")
    else:
        print("frames in %s (install ffmpeg to also get reference.mp4)" % frames)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recipe", help="recipe JSON, for example recipes/ring.view.json")
    ap.add_argument("--sky", help="unlensed 2:1 sky from compose_sky.py")
    ap.add_argument("--out", help="Package v2 source folder to create (must not exist)")
    ap.add_argument("--panorama-width", type=int, default=8192, help="panorama.jpg width (default 8192)")
    ap.add_argument("--view", metavar="SOURCE_DIR",
                    help="preview or re-cover an existing baked source folder instead of baking")
    ap.add_argument("--stills", metavar="SECONDS",
                    help="comma-separated times to render as 1920x1080 stills, e.g. 0,5,10")
    ap.add_argument("--stills-dir", metavar="DIR", help="where --stills go (default: <source>-stills)")
    ap.add_argument("--frames", metavar="DIR", help="render a reference PNG sequence into DIR")
    ap.add_argument("--seconds", type=float, default=10, help="length of --frames (default 10)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1920x1080", help="still and frame size (default 1920x1080)")
    ap.add_argument("--control", action="append", default=[], metavar="NAME=VALUE",
                    help="preview an Edit View Motion setting: driftSpeed, flowSpeed, doppler, glow, flares, "
                         "detail or brightness; repeatable")
    ap.add_argument("--thumbnail-only", action="store_true",
                    help="with --view, re-render thumbnail.jpg using the recipe's thumbnailHfovDegrees")
    args = ap.parse_args(argv)
    recipe = json.loads(Path(args.recipe).read_text())
    controls = parse_controls(args.control)

    if args.view:
        source = Path(args.view)
        view_dir = source / "catalog" / "destinations" / recipe["destinationID"]
    else:
        if not (args.sky and args.out):
            ap.error("--sky and --out are required unless --view is given")
        view_dir = bake(recipe, args.sky, args.out, args.panorama_width,
                        log=lambda message: print(message, flush=True))
        source = Path(args.out)

    profile = json.loads((view_dir / "destination.json").read_text())["blackHole"]
    ref = Reference(view_dir, profile)
    if args.thumbnail_only:
        save_jpeg(view_dir / "thumbnail.jpg", render_thumbnail(ref, recipe["bake"]["thumbnailHfovDegrees"]),
                  quality=95)
        print("thumbnail", view_dir / "thumbnail.jpg")
    if args.stills:
        times = [float(x) for x in args.stills.split(",") if x.strip()]
        out_dir = Path(args.stills_dir) if args.stills_dir else source.parent / (source.name + "-stills")
        for path in render_stills(ref, profile, out_dir, times, args.size, controls):
            print("still", path)
    if args.frames:
        render_frames(ref, profile, Path(args.frames), args.seconds, args.fps, args.size, controls)


if __name__ == "__main__":
    main()
