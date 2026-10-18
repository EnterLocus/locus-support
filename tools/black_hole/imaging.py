# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Colour, sampling, camera and 16-bit PNG helpers shared by the black-hole tools."""
import math
import struct
import zlib
from pathlib import Path

import numpy as np

import black_hole_lens as L


# ---------------------------------------------------------------- colour

def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)


def blackbody_rgb(kelvin):
    """Linear sRGB of a blackbody with luminance Y = 1 (Kim et al. Planckian locus)."""
    t = np.clip(kelvin, 1667.0, 25000.0)
    x = np.where(t <= 4000,
                 -0.2661239e9 / t**3 - 0.2343589e6 / t**2 + 0.8776956e3 / t + 0.179910,
                 -3.0258469e9 / t**3 + 2.1070379e6 / t**2 + 0.2226347e3 / t + 0.240390)
    y = np.where(t <= 2222, -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683,
                 np.where(t <= 4000, -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867,
                          3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483))
    X, Z = x / y, (1 - x - y) / y
    rgb = np.stack([3.2404542 * X - 1.5371385 - 0.4985314 * Z,
                    -0.9692660 * X + 1.8760108 + 0.0415560 * Z,
                    0.0556434 * X - 0.2040259 + 1.0572252 * Z], axis=-1)
    return np.clip(rgb, 0, None)


def tonemap(x):
    """ACES filmic fit (Narkowicz), display-linear output."""
    return np.clip(x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


# ---------------------------------------------------------------- sampling and cameras

def bilinear(img, u, v, wrap_x=False):
    """Bilinear sample of img (H, W[, C]) at image coordinates u, v in [0, 1]."""
    h, w = img.shape[:2]
    x, y = u * w - 0.5, v * h - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]

    def px(xx, yy):
        xx = np.mod(xx, w) if wrap_x else np.clip(xx, 0, w - 1)
        return img[np.clip(yy, 0, h - 1), xx].astype(np.float64)

    top = px(x0, y0) * (1 - fx) + px(x0 + 1, y0) * fx
    bottom = px(x0, y0 + 1) * (1 - fx) + px(x0 + 1, y0 + 1) * fx
    return top * (1 - fy) + bottom * fy


def camera_directions(c, width, height, hfov_degrees, jitter=(0.5, 0.5)):
    """View-frame directions of a pinhole camera looking along c (screen-up stays up)."""
    right, up = L.tangent_basis(c)
    ext = math.tan(math.radians(hfov_degrees) / 2)
    xs = (2 * (np.arange(width) + jitter[0]) / width - 1) * ext
    ys = -(2 * (np.arange(height) + jitter[1]) / height - 1) * ext * height / width
    gx, gy = np.meshgrid(xs, ys)
    return L.unit(c + gx[..., None] * right + gy[..., None] * up)


def jitters(n):
    """n x n stratified sub-pixel offsets for supersampling."""
    return [((i + 0.5) / n, (j + 0.5) / n) for j in range(n) for i in range(n)]


# ---------------------------------------------------------------- 16-bit PNG

def write_png16(path, codes):
    """Write uint16 codes (H, W) or (H, W, 3|4) as a non-interlaced 16-bit PNG."""
    codes = np.asarray(codes, dtype=np.uint16)
    if codes.ndim == 2:
        codes = codes[..., None]
    height, width, channels = codes.shape
    colour = {1: 0, 3: 2, 4: 6}[channels]
    rows = np.ascontiguousarray(codes.astype(">u2").reshape(height, width * channels)).view(np.uint8)
    previous = np.vstack([np.zeros((1, rows.shape[1]), np.uint8), rows[:-1]])
    filtered = (rows.astype(np.int16) - previous).astype(np.uint8)  # PNG "Up"
    raw = np.hstack([np.full((height, 1), 2, np.uint8), filtered]).tobytes()

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", width, height, 16, colour, 0, 0, 0)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def read_png16(path):
    """Read a non-interlaced 16-bit PNG written with filters None/Up (as `write_png16` does)."""
    data = Path(path).read_bytes()
    offset, idat, header = 8, b"", None
    while offset < len(data):
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        body = data[offset + 8:offset + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        offset += 12 + length
    width, height, depth, colour, _, _, interlace = header
    if depth != 16 or interlace:
        raise ValueError("expected a non-interlaced 16-bit PNG")
    channels = {0: 1, 2: 3, 6: 4}[colour]
    stride = width * channels * 2
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(height, stride + 1)
    if not np.isin(raw[:, 0], (0, 2)).all():
        raise ValueError("only None/Up row filters are supported")
    rows = raw[:, 1:].astype(np.int64)
    up = raw[:, 0] == 2
    out = np.empty((height, stride), np.uint8)
    previous = np.zeros(stride, np.int64)
    for y in range(height):
        row = (rows[y] + previous) & 255 if up[y] else rows[y]
        out[y] = row
        previous = row
    codes = out.view(">u2").astype(np.uint16).reshape(height, width, channels)
    return codes[..., 0] if channels == 1 else codes


def png_header(data):
    """(width, height, bit depth, colour type, interlace) from PNG bytes, or None if not a PNG."""
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    return width, height, depth, colour, interlace
