"""Minimal KTX1 header parser for the ASTC sky GPU-texture sidecar
(`locus.view.gpu-texture.v1`, docs/package-spec-v2.md "View GPU texture
sidecar"). Parses only the fixed 64-byte header; the compressed texture data
itself is opaque here and handed to RealityKit unparsed by the viewer.

Shared by `validate_locusplace.py` (archive validator) and
`gpu_texture_sidecar.py` (producer); the Swift counterpart that the import
validator and package loader share is `viewer/LocusViewer/Models/Ktx1Header.swift`
-- keep the three in sync when the format changes.

Runs under the repo's `scripts/` Python 3.9 floor (see AGENTS.md): no
dataclasses `slots=`/`kw_only=`, no `X | Y` unions at runtime (guarded by
`from __future__ import annotations`), no `match`.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# The 12-byte magic every KTX1 file starts with (Khronos KTX File Format 1).
MAGIC = bytes([0xAB, 0x4B, 0x54, 0x58, 0x20, 0x31, 0x31, 0xBB, 0x0D, 0x0A, 0x1A, 0x0A])

# GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR (KHR_texture_compression_astc_hdr /
# _ldr). This is the only glInternalFormat the v1 sidecar profile (always
# sRGB) accepts.
GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR = 0x93D4

# GL_COMPRESSED_RGBA_ASTC_6x6_KHR -- the linear (non-sRGB) counterpart, used
# by the v2 sidecar (`locus.view.gpu-texture.v2`) for `celestial.cloudTexture`,
# which is sampled with RealityKit's `.raw` semantic (no gamma decode) the
# same way the uncompressed PNG path already is.
GL_COMPRESSED_RGBA_ASTC_6x6_KHR = 0x93B4

HEADER_SIZE = 64


class Ktx1Error(Exception):
    pass


@dataclass(frozen=True)
class Ktx1Header:
    little_endian: bool
    gl_type: int
    gl_type_size: int
    gl_format: int
    gl_internal_format: int
    gl_base_internal_format: int
    pixel_width: int
    pixel_height: int
    pixel_depth: int
    number_of_array_elements: int
    number_of_faces: int
    number_of_mipmap_levels: int
    bytes_of_key_value_data: int


def parse_header(data: bytes) -> Ktx1Header:
    """Parse the fixed 64-byte KTX1 header from the start of `data`.

    Raises `Ktx1Error` with a specific reason on any structural problem;
    callers decide how that becomes a validation failure.
    """
    if len(data) < HEADER_SIZE:
        raise Ktx1Error("file is smaller than a KTX1 header")
    if data[:12] != MAGIC:
        raise Ktx1Error("bad KTX1 magic")
    endianness = struct.unpack_from("<I", data, 12)[0]
    if endianness == 0x04030201:
        fmt = "<12I"
        little_endian = True
    elif endianness == 0x01020304:
        fmt = ">12I"
        little_endian = False
    else:
        raise Ktx1Error("bad KTX1 endianness field")
    values = struct.unpack_from(fmt, data, 16)
    (
        gl_type, gl_type_size, gl_format, gl_internal_format,
        gl_base_internal_format, pixel_width, pixel_height, pixel_depth,
        number_of_array_elements, number_of_faces, number_of_mipmap_levels,
        bytes_of_key_value_data,
    ) = values
    return Ktx1Header(
        little_endian=little_endian,
        gl_type=gl_type,
        gl_type_size=gl_type_size,
        gl_format=gl_format,
        gl_internal_format=gl_internal_format,
        gl_base_internal_format=gl_base_internal_format,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
        pixel_depth=pixel_depth,
        number_of_array_elements=number_of_array_elements,
        number_of_faces=number_of_faces,
        number_of_mipmap_levels=number_of_mipmap_levels,
        bytes_of_key_value_data=bytes_of_key_value_data,
    )


def write_header(
    pixel_width: int,
    pixel_height: int,
    *,
    gl_internal_format: int = GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR,
    number_of_mipmap_levels: int = 1,
    gl_type: int = 0,
    gl_type_size: int = 1,
    gl_format: int = 0,
    gl_base_internal_format: int = 0x1908,  # GL_RGBA
    pixel_depth: int = 0,
    number_of_array_elements: int = 0,
    number_of_faces: int = 1,
    bytes_of_key_value_data: int = 0,
) -> bytes:
    """Encode a little-endian KTX1 header. The inverse of `parse_header`,
    kept here so producer, validator and test code share one byte layout
    instead of each guessing the field order independently. Real sidecar
    files are always written by Xcode's TextureConverter, not this
    function -- it exists for tests that need a structurally valid header
    without paying for a real ASTC encode.
    """
    return MAGIC + struct.pack(
        "<13I",
        0x04030201,
        gl_type, gl_type_size, gl_format, gl_internal_format,
        gl_base_internal_format, pixel_width, pixel_height, pixel_depth,
        number_of_array_elements, number_of_faces, number_of_mipmap_levels,
        bytes_of_key_value_data,
    )


def astc_6x6_expected_byte_range(width: int, height: int) -> "tuple[int, int]":
    """A loose, sane (lower, upper) byte-size bound for an ASTC 6x6 sRGB KTX1
    at `width`x`height` with baked mips: 16 bytes per 6x6 block is exact for
    the base level; mips add at most another ~33%. The bound intentionally
    stays wide -- it exists to catch a truncated/substituted file or a
    completely wrong compression format, not to pin an exact encoder output
    size (`--max_mipmaps` and encoder version can both shift it a little).
    """
    base_blocks = -(-width // 6) * -(-height // 6)
    base_bytes = base_blocks * 16
    return (base_bytes // 4, base_bytes * 2 + HEADER_SIZE)
