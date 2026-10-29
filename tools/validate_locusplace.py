#!/usr/bin/env python3
"""Validate a .locusplace archive without installing it.

This standard-library tool mirrors the shipping v1 transport, integrity,
Package-v2, provenance, image, and USDZ security checks closely enough for
authors and CI. The visionOS importer remains the installation authority.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from content_localization import LocalizationError, validate_localizations

# Sibling scripts/ modules (panorama_media) are imported lazily below; make
# sure they're importable even when this file is loaded by path (e.g. via
# importlib from the test suite) rather than run as `scripts/validate_locusplace.py`,
# which would otherwise put scripts/ on sys.path automatically.
_SCRIPTS_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIRECTORY)


ARCHIVE_BYTES = 1_073_741_824
ENTRY_COUNT = 4_096
MANIFEST_BYTES = 1_048_576
FILE_BYTES = 805_306_368
TOTAL_BYTES = 2_147_483_648
COMPRESSION_RATIO = 200
PATH_BYTES = 512
COMPONENT_BYTES = 128
JSON_BYTES = 1_048_576
# A `sky.stars.catalog` file's own cap (procedural_sky.STAR_CATALOG_MAX_BYTES);
# one under a `.json` name is bound by JSON_BYTES like every JSON member.
STAR_CATALOG_BYTES = 1024 * 1024
PROVENANCE_BYTES = 65_536
IMAGE_DIMENSION = 32_768
IMAGE_PIXELS = 150_000_000
TOTAL_IMAGE_PIXELS = 500_000_000
MODEL_ENTRIES = 4_096
MODEL_BYTES = 805_306_368
MODEL_EXPANDED_BYTES = 1_610_612_736
MODEL_TEXTURE_PIXELS = 500_000_000
MODEL_TEXTURE_DIMENSION = 16_384
TRIANGLES = 5_000_000
MATERIALS = 1_024
ENTITIES = 100_000
EXR_HEADER_BYTES = 1_048_576
MODEL_FLATTENED_BYTES = 268_435_456
MP4_MOOV_BYTES = 8_388_608
VISUAL_SAMPLE_ENTRY_FIXED_BYTES = 78  # SampleEntry(8) + VisualSampleEntry extension(70)

COLLECTIONS = {
    "destinations": ("destinationIDs", "destination.json"),
    "spaces": ("spaceIDs", "space.json"),
    "experiences": ("experienceIDs", "experience.json"),
}
IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
IDENTIFIER_MAX = 128
SHA256_CHARS = frozenset("0123456789abcdef")
USDZ_EXTENSIONS = frozenset(
    {"usd", "usda", "usdc", "png", "jpg", "jpeg", "exr", "m4a", "wav", "mp3"}
)
AUTHORING_SOURCE_EXTENSIONS = frozenset(
    {"blend", "blend1", "blend2", "fbx", "obj", "mtl", "gltf", "glb"}
)
SOF_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)
HEVC_VISUAL_SAMPLE_ENTRY_TYPES = frozenset({b"hvc1", b"hev1"})
AVC_VISUAL_SAMPLE_ENTRY_TYPES = frozenset({b"avc1", b"avc3"})
VISUAL_SAMPLE_ENTRY_TYPES = HEVC_VISUAL_SAMPLE_ENTRY_TYPES | AVC_VISUAL_SAMPLE_ENTRY_TYPES
AVC_EXTENDED_CHROMA_PROFILES = frozenset({100, 110, 122, 144})


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def is_finite_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def object_without_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_json(data: bytes, path: str) -> dict[str, Any]:
    require(len(data) <= JSON_BYTES, f"{path} exceeds the JSON byte budget")
    def reject_nonstandard_number(value):
        raise ValidationError(f"{path} contains non-standard number {value}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=object_without_duplicate_keys,
            parse_constant=reject_nonstandard_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{path} is not valid UTF-8 JSON: {error}") from error
    require(isinstance(value, dict), f"{path} root must be an object")
    return value


def exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    context: str,
) -> None:
    keys = set(value)
    unknown = keys - required - optional
    missing = required - keys
    if unknown:
        raise ValidationError(
            f"{context} has unknown field {sorted(unknown)[0]}"
        )
    if missing:
        raise ValidationError(
            f"{context} is missing field {sorted(missing)[0]}"
        )


def valid_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= IDENTIFIER_MAX
        and value[0].isascii()
        and value[0].isalnum()
        and all(character in IDENTIFIER_CHARS for character in value)
    )


# Room View ground fields (`locus.room.view-ground.v1`,
# `locus.room.view-ground-keepout.v1`): their shared App floor and the
# authored floor-offset range, mirrored by SpacePackage in the viewer.
VIEW_GROUND_MINIMUM_APP = (1, 4, 4)
VIEW_GROUND_MAXIMUM_FLOOR_OFFSET_METERS = 100
VIEW_MIDGROUND_VISIBILITY_MINIMUM_APP = (1, 4, 4)
VIEW_MIDGROUND_VISIBILITIES = {"all", "terrainOnly", "hidden"}


def parse_version(value: Any, field: str) -> tuple[int, int, int]:
    require(isinstance(value, str), f"{field} must be a semantic version")
    parts = value.split(".")
    require(
        len(parts) == 3 and all(part and part.isascii() and part.isdigit() for part in parts),
        f"{field} must contain exactly three numeric components",
    )
    return tuple(int(part) for part in parts)


def canonical_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= SHA256_CHARS


def safe_path(raw: str, *, allow_manifest: bool, directory: bool = False) -> str:
    require(isinstance(raw, str), "ZIP paths must be strings")
    value = raw[:-1] if directory and raw.endswith("/") else raw
    components = value.split("/")
    require(value, f"unsafe archive path: {raw!r}")
    require(unicodedata.normalize("NFC", value) == value, f"non-NFC path: {raw}")
    require(len(value.encode("utf-8")) <= PATH_BYTES, f"path is too long: {raw}")
    require(not value.startswith("/") and "\\" not in value, f"unsafe archive path: {raw}")
    require(not any(ord(character) < 32 or ord(character) == 127 for character in value),
            f"control character in path: {raw!r}")
    require(
        all(
            component not in {"", ".", ".."}
            and len(component.encode("utf-8")) <= COMPONENT_BYTES
            for component in components
        ),
        f"unsafe archive path: {raw}",
    )
    require(
        (allow_manifest and value == "locusplace.json") or components[0] == "catalog",
        f"path is outside the .locusplace namespace: {raw}",
    )
    return value


def collision_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def stream_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    maximum: int,
    capture: int = 0,
) -> tuple[str, bytes]:
    digest = hashlib.sha256()
    size = 0
    prefix = bytearray()
    try:
        with archive.open(info, "r") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                require(size <= maximum, f"{info.filename} expanded past its budget")
                digest.update(chunk)
                if len(prefix) < capture:
                    prefix.extend(chunk[: capture - len(prefix)])
    except (RuntimeError, zipfile.BadZipFile, NotImplementedError) as error:
        raise ValidationError(f"cannot read {info.filename}: {error}") from error
    require(size == info.file_size, f"{info.filename} size changed while reading")
    return digest.hexdigest(), bytes(prefix)


def calculate_content_hash(records: list[dict[str, Any]]) -> str:
    """Return the v1 envelope hash for normalized file records."""
    canonical = bytearray()
    for record in sorted(records, key=lambda item: item["path"]):
        canonical.extend(record["path"].encode("utf-8"))
        canonical.append(0)
        canonical.extend(str(record["byteCount"]).encode("ascii"))
        canonical.append(0)
        canonical.extend(record["sha256"].encode("ascii"))
        canonical.append(0)
    return hashlib.sha256(canonical).hexdigest()


def validate_envelope(data: bytes, current_app_version: str) -> dict[str, Any]:
    manifest = decode_json(data, "locusplace.json")
    exact_keys(
        manifest,
        required={
            "formatVersion", "packageID", "contentVersion", "minimumAppVersion",
            "contents", "files", "contentHash",
        },
        context="locusplace.json",
    )
    require(type(manifest["formatVersion"]) is int and manifest["formatVersion"] == 1,
            "unsupported .locusplace formatVersion")
    require(valid_identifier(manifest["packageID"]), "invalid packageID")
    parse_version(manifest["contentVersion"], "contentVersion")
    minimum = parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
    current = parse_version(current_app_version, "currentAppVersion")
    require(minimum <= current, f"package requires Locus {manifest['minimumAppVersion']}")

    contents = manifest["contents"]
    require(isinstance(contents, dict), "contents must be an object")
    exact_keys(
        contents,
        required={"destinationIDs", "spaceIDs", "experienceIDs"},
        context="contents",
    )
    all_ids = []
    for field in ("destinationIDs", "spaceIDs", "experienceIDs"):
        values = contents[field]
        require(isinstance(values, list), f"contents.{field} must be an array")
        require(all(valid_identifier(item) for item in values), f"contents.{field} has invalid ID")
        all_ids.extend(values)
    require(all_ids, "a .locusplace must contain content")
    require(len(set(all_ids)) == len(all_ids), "content IDs must be unique")

    records = manifest["files"]
    require(isinstance(records, list), "files must be an array")
    seen = set()
    normalized_records = []
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"files[{index}] must be an object")
        exact_keys(
            record,
            required={"path", "byteCount", "sha256"},
            context=f"files[{index}]",
        )
        path = safe_path(record["path"], allow_manifest=False)
        key = collision_key(path)
        require(key not in seen, f"duplicate or colliding file path: {path}")
        seen.add(key)
        require(type(record["byteCount"]) is int and record["byteCount"] >= 0,
                f"invalid byteCount for {path}")
        require(canonical_sha256(record["sha256"]), f"invalid SHA-256 for {path}")
        normalized_records.append(record)

    calculated = calculate_content_hash(normalized_records)
    require(canonical_sha256(manifest["contentHash"]), "invalid contentHash")
    require(calculated == manifest["contentHash"], "contentHash mismatch")
    return manifest


def read_exact(source: BinaryIO, count: int, message: str) -> bytes:
    data = source.read(count)
    require(len(data) == count, message)
    return data


def png_filtered_layout(
    width: int, height: int, bit_depth: int, channels: int, interlace: int
) -> tuple[int, list[int]]:
    bits_per_pixel = bit_depth * channels
    filters: list[int] = []
    total = 0

    def add_pass(pass_width: int, pass_height: int) -> None:
        nonlocal total
        if pass_width <= 0 or pass_height <= 0:
            return
        row_bytes = (pass_width * bits_per_pixel + 7) // 8
        for _ in range(pass_height):
            filters.append(total)
            total += 1 + row_bytes

    if interlace == 0:
        add_pass(width, height)
    else:
        starts_x = (0, 4, 0, 2, 0, 1, 0)
        starts_y = (0, 0, 4, 0, 2, 0, 1)
        steps_x = (8, 8, 4, 4, 2, 2, 1)
        steps_y = (8, 8, 8, 4, 4, 2, 2)
        for start_x, start_y, step_x, step_y in zip(
            starts_x, starts_y, steps_x, steps_y
        ):
            pass_width = (
                0 if width <= start_x
                else (width - start_x + step_x - 1) // step_x
            )
            pass_height = (
                0 if height <= start_y
                else (height - start_y + step_y - 1) // step_y
            )
            add_pass(pass_width, pass_height)
    return total, filters


def png_dimensions(source: BinaryIO, file_size: int, path: str) -> tuple[int, int]:
    require(
        read_exact(source, 8, f"malformed PNG: {path}") == b"\x89PNG\r\n\x1a\n",
        f"malformed PNG: {path}",
    )
    width = height = None
    decompressor = zlib.decompressobj()
    decompressed = 0
    expected = None
    saw_idat = False
    saw_iend = False
    saw_palette = False
    filter_positions: list[int] = []
    next_filter = 0

    def validate_filters(decoded: bytes, starting_at: int) -> None:
        nonlocal next_filter
        ending_at = starting_at + len(decoded)
        while (next_filter < len(filter_positions)
               and filter_positions[next_filter] < ending_at):
            position = filter_positions[next_filter]
            require(position >= starting_at and decoded[position - starting_at] <= 4,
                    f"PNG scanline filter is invalid: {path}")
            next_filter += 1

    while source.tell() < file_size:
        length, = struct.unpack(">I", read_exact(source, 4, f"truncated PNG: {path}"))
        kind = read_exact(source, 4, f"truncated PNG: {path}")
        require(length <= FILE_BYTES, f"PNG chunk is too large: {path}")
        data = read_exact(source, length, f"truncated PNG: {path}")
        declared_crc, = struct.unpack(
            ">I", read_exact(source, 4, f"truncated PNG: {path}")
        )
        require(
            zlib.crc32(data, zlib.crc32(kind)) & 0xFFFFFFFF == declared_crc,
            f"PNG checksum mismatch: {path}",
        )
        if width is None:
            require(kind == b"IHDR" and length == 13, f"malformed PNG: {path}")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            allowed_depths = {
                0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8},
                4: {8, 16}, 6: {8, 16},
            }
            require(
                width > 0 and height > 0
                and color_type in allowed_depths
                and bit_depth in allowed_depths[color_type]
                and compression == 0 and filtering == 0 and interlace in {0, 1},
                f"unsupported PNG encoding: {path}",
            )
            require(
                width <= IMAGE_DIMENSION
                and height <= IMAGE_DIMENSION
                and width * height <= IMAGE_PIXELS,
                f"image budget exceeded: {path}",
            )
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
            expected, filter_positions = png_filtered_layout(
                width, height, bit_depth, channels, interlace
            )
            continue
        if kind == b"PLTE":
            require(not saw_idat and length > 0 and length % 3 == 0,
                    f"malformed PNG palette: {path}")
            saw_palette = True
        elif kind == b"IDAT":
            saw_idat = True
            remaining = expected - decompressed + 1
            try:
                decoded = decompressor.decompress(data, max(1, remaining))
            except zlib.error as error:
                raise ValidationError(f"PNG pixel payload is malformed: {path}") from error
            validate_filters(decoded, decompressed)
            decompressed += len(decoded)
            require(
                decompressed <= expected and not decompressor.unconsumed_tail,
                f"PNG pixel payload exceeds dimensions: {path}",
            )
        elif kind == b"IEND":
            require(length == 0 and saw_idat, f"malformed PNG ending: {path}")
            try:
                decoded = decompressor.flush(max(1, expected - decompressed + 1))
            except zlib.error as error:
                raise ValidationError(f"PNG pixel payload is malformed: {path}") from error
            validate_filters(decoded, decompressed)
            decompressed += len(decoded)
            require(
                decompressor.eof and decompressed == expected
                and not decompressor.unused_data
                and next_filter == len(filter_positions),
                f"PNG pixel payload is incomplete: {path}",
            )
            saw_iend = True
            break
        elif 65 <= kind[0] <= 90:
            raise ValidationError(f"unsupported critical PNG chunk {kind!r}: {path}")
    require(saw_iend and source.tell() == file_size, f"truncated or trailing PNG: {path}")
    if color_type == 3:
        require(saw_palette, f"indexed PNG has no palette: {path}")
    return width, height


def jpeg_dimensions(source: BinaryIO, file_size: int, path: str, components=None) -> tuple[int, int]:
    require(read_exact(source, 2, f"malformed JPEG: {path}") == b"\xff\xd8",
            f"malformed JPEG: {path}")
    width = height = None
    while source.tell() < file_size:
        prefix = read_exact(source, 1, f"truncated JPEG: {path}")
        require(prefix == b"\xff", f"malformed JPEG marker stream: {path}")
        marker = 0xFF
        while marker == 0xFF:
            marker = read_exact(source, 1, f"truncated JPEG: {path}")[0]
        require(marker not in {0x00, 0xD8, 0xD9}, f"malformed JPEG marker: {path}")
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        length, = struct.unpack(">H", read_exact(source, 2, f"truncated JPEG: {path}"))
        require(length >= 2, f"malformed JPEG segment: {path}")
        segment = read_exact(source, length - 2, f"truncated JPEG: {path}")
        if marker in SOF_MARKERS:
            require(len(segment) >= 6, f"malformed JPEG frame: {path}")
            height, width = struct.unpack(">HH", segment[1:5])
            if components is not None:
                components.append(segment[5])
            require(width > 0 and height > 0, f"malformed JPEG frame: {path}")
        if marker == 0xDA:
            require(width is not None, f"JPEG dimensions unavailable: {path}")
            # The first FF D9 after SOS must be the last two bytes of the file.
            # bytes.find replaces a per-byte Python loop (the hot spot of a
            # cold publication, #1426); the byte carried over from the previous
            # chunk keeps a pair split across a chunk boundary visible.
            previous = b""
            while chunk := source.read(64 * 1024):
                found = (previous + chunk).find(b"\xff\xd9")
                if found >= 0:
                    require(
                        found + 2 - len(previous) == len(chunk) and not source.read(1),
                        f"JPEG has trailing bytes: {path}",
                    )
                    return width, height
                previous = chunk[-1:]
            raise ValidationError(f"JPEG pixel payload is incomplete: {path}")
    raise ValidationError(f"JPEG pixel payload is incomplete: {path}")


def opaque_grayscale_image(archive, info, path):
    """ImageIO's one-channel admission for near-orbit cloud/region masks."""
    with archive.open(info) as source:
        signature = source.read(8)
        source.seek(0)
        if signature != b'\x89PNG\r\n\x1a\n':
            components = []
            jpeg_dimensions(source, info.file_size, path, components)
            return bool(components) and components[-1] == 1
        _, _, _, color_type = png_ihdr(archive, info, path)
        if color_type != 0:
            return False
        source.seek(8)
        while source.tell() < info.file_size:
            length, kind = struct.unpack('>I4s', read_exact(source, 8, path))
            if kind == b'tRNS':
                return False
            source.seek(length + 4, 1)
        return True


def require_imageio_decode(source: BinaryIO, path: str, suffix: str) -> None:
    """Force macOS ImageIO to decode pixels, matching the shipping importer."""
    sips = shutil.which("sips")
    require(sips is not None, "macOS sips is required for complete image validation")
    try:
        source.seek(0)
    except (OSError, ValueError) as error:
        raise ValidationError(f"image payload cannot be reread: {path}") from error
    with tempfile.TemporaryDirectory(prefix="locusplace-image-") as directory:
        root = Path(directory)
        input_path = root / f"source{suffix}"
        output_path = root / "decoded.png"
        with input_path.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        try:
            decoded = subprocess.run(
                [
                    sips,
                    "-s", "format", "png",
                    "-z", "1", "2",
                    str(input_path),
                    "--out", str(output_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ValidationError(f"image decode exceeded its time budget: {path}") from error
        require(
            decoded.returncode == 0
            and output_path.is_file()
            and output_path.stat().st_size > 0,
            f"ImageIO could not decode the complete pixel payload: {path}",
        )


def raster_image_dimensions(data: bytes, path: str) -> tuple[int, int]:
    """Validate a complete public JPEG/PNG and return its decoded dimensions."""
    source = io.BytesIO(data)
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        dimensions = png_dimensions(source, len(data), path)
        suffix = ".png"
    elif data.startswith(b"\xff\xd8"):
        dimensions = jpeg_dimensions(source, len(data), path)
        suffix = ".jpg"
    else:
        raise ValidationError(f"unsupported image content: {path}")
    require_imageio_decode(source, path, suffix)
    return dimensions


def exr_channel_names(value: bytes, path: str) -> set[str]:
    offset = 0
    channels: set[str] = set()
    while offset < len(value):
        end = value.find(b"\0", offset)
        require(end >= 0, f"EXR channel list is incomplete: {path}")
        raw_name = value[offset:end]
        offset = end + 1
        if not raw_name:
            require(offset == len(value), f"EXR channel list has trailing data: {path}")
            break
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as error:
            raise ValidationError(f"EXR channel name is malformed: {path}") from error
        require(name not in channels and offset + 16 <= len(value),
                f"EXR channel list is malformed: {path}")
        pixel_type, = struct.unpack("<I", value[offset:offset + 4])
        p_linear = value[offset + 4]
        reserved = value[offset + 5:offset + 8]
        x_sampling, y_sampling = struct.unpack("<II", value[offset + 8:offset + 16])
        require(
            name in {"R", "G", "B", "A"} and pixel_type == 1
            and p_linear in {0, 1} and reserved == b"\0\0\0"
            and x_sampling == 1 and y_sampling == 1,
            f"EXR must contain only full-resolution half-float RGB(A): {path}",
        )
        channels.add(name)
        offset += 16
    require({"R", "G", "B"} <= channels and channels <= {"R", "G", "B", "A"},
            f"EXR must contain half-float RGB channels: {path}")
    return channels


EXR_LINES_PER_CHUNK = {0: 1, 2: 1, 3: 16}
EXR_CHUNK_DECODE_BYTES = 16 * 1024 * 1024


def exr_stream_dimensions(
    source: BinaryIO, file_size: int, path: str
) -> tuple[int, int]:
    require(read_exact(source, 4, f"malformed EXR: {path}") == b"v/1\x01",
            f"malformed EXR: {path}")
    version_word, = struct.unpack("<I", read_exact(source, 4, f"truncated EXR: {path}"))
    require(version_word == 2, f"unsupported EXR version or layout: {path}")
    attributes: dict[str, tuple[str, bytes]] = {}

    def cstring() -> str:
        value = bytearray()
        while source.tell() < min(file_size, EXR_HEADER_BYTES):
            byte = read_exact(source, 1, f"EXR header is incomplete: {path}")
            if byte == b"\0":
                try:
                    return value.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValidationError(f"EXR header is malformed: {path}") from error
            value.extend(byte)
        raise ValidationError(f"EXR header exceeds its byte budget: {path}")

    while source.tell() < min(file_size, EXR_HEADER_BYTES):
        name = cstring()
        if not name:
            break
        kind = cstring()
        size, = struct.unpack("<I", read_exact(source, 4, f"EXR header is incomplete: {path}"))
        require(name not in attributes and source.tell() + size <= EXR_HEADER_BYTES,
                f"EXR header is malformed: {path}")
        attributes[name] = (kind, read_exact(source, size, f"EXR header is incomplete: {path}"))
    else:
        raise ValidationError(f"EXR header is incomplete: {path}")

    channels_type, channels_value = attributes.get("channels", (None, None))
    compression_type, compression_value = attributes.get("compression", (None, None))
    window_type, window_value = attributes.get("dataWindow", (None, None))
    require(channels_type == "chlist" and channels_value is not None,
            f"EXR channels are missing: {path}")
    channel_names = exr_channel_names(channels_value, path)
    require(compression_type == "compression" and compression_value is not None
            and len(compression_value) == 1,
            f"EXR compression is missing: {path}")
    compression = compression_value[0]
    require(compression in EXR_LINES_PER_CHUNK, f"unsupported EXR compression: {path}")
    require(window_type == "box2i" and window_value is not None and len(window_value) == 16,
            f"EXR dataWindow is missing: {path}")
    min_x, min_y, max_x, max_y = struct.unpack("<iiii", window_value)
    require(max_x >= min_x and max_y >= min_y, f"invalid EXR dataWindow: {path}")
    width, height = max_x - min_x + 1, max_y - min_y + 1
    lines_per_chunk = EXR_LINES_PER_CHUNK[compression]
    chunk_count = (height + lines_per_chunk - 1) // lines_per_chunk
    require(chunk_count > 0 and source.tell() + 8 * chunk_count <= file_size,
            f"EXR chunk table is incomplete: {path}")
    offsets = [
        struct.unpack("<Q", read_exact(source, 8, f"EXR chunk table is incomplete: {path}"))[0]
        for _ in range(chunk_count)
    ]
    data_start = source.tell()
    require(len(set(offsets)) == chunk_count and min(offsets) >= data_start,
            f"EXR chunk table is malformed: {path}")
    expected_y = {min_y + index * lines_per_chunk for index in range(chunk_count)}
    actual_y = set()
    final_end = data_start
    sorted_offsets = sorted(offsets)
    for index, chunk_offset in enumerate(sorted_offsets):
        require(chunk_offset + 8 <= file_size, f"EXR chunk offset is invalid: {path}")
        try:
            source.seek(chunk_offset)
        except (OSError, ValueError) as error:
            raise ValidationError(f"EXR chunk offset is unreadable: {path}") from error
        y, packed_size = struct.unpack(
            "<iI", read_exact(source, 8, f"EXR chunk is incomplete: {path}")
        )
        chunk_end = chunk_offset + 8 + packed_size
        next_offset = sorted_offsets[index + 1] if index + 1 < chunk_count else file_size
        require(
            packed_size > 0 and chunk_end <= next_offset and chunk_end <= file_size,
            f"EXR chunk payload is incomplete or overlapping: {path}",
        )
        rows = min(lines_per_chunk, max_y - y + 1)
        expected_size = rows * width * len(channel_names) * 2
        require(rows > 0 and expected_size <= EXR_CHUNK_DECODE_BYTES,
                f"EXR decoded chunk exceeds its byte budget: {path}")
        payload = read_exact(
            source, packed_size, f"EXR chunk payload is incomplete: {path}"
        )
        if compression == 0 or packed_size == expected_size:
            require(packed_size == expected_size,
                    f"EXR raw chunk has the wrong size: {path}")
        else:
            decoder = zlib.decompressobj()
            try:
                decoded = decoder.decompress(payload, expected_size + 1)
                decoded += decoder.flush(expected_size + 1 - len(decoded))
            except zlib.error as error:
                raise ValidationError(
                    f"EXR ZIP chunk is malformed: {path}"
                ) from error
            require(
                decoder.eof and not decoder.unconsumed_tail
                and not decoder.unused_data and len(decoded) == expected_size,
                f"EXR ZIP chunk is malformed: {path}",
            )
        actual_y.add(y)
        final_end = max(final_end, chunk_end)
    require(actual_y == expected_y and final_end == file_size,
            f"EXR scanline chunks are incomplete: {path}")
    return width, height


def exr_dimensions(data: bytes, path: str) -> tuple[int, int]:
    source = io.BytesIO(data)
    dimensions = exr_stream_dimensions(source, len(data), path)
    require_imageio_decode(source, path, ".exr")
    return dimensions


def image_dimensions(data: bytes, path: str) -> tuple[int, int]:
    """Validate a complete supported USDZ texture."""
    if data.startswith(b"v/1\x01"):
        return exr_dimensions(data, path)
    return raster_image_dimensions(data, path)


def stream_image_dimensions(
    source: BinaryIO, file_size: int, path: str, *, allow_exr: bool
) -> tuple[int, int]:
    signature = read_exact(source, min(8, file_size), f"image is empty: {path}")
    source.seek(0)
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        dimensions = png_dimensions(source, file_size, path)
        suffix = ".png"
    elif signature.startswith(b"\xff\xd8"):
        dimensions = jpeg_dimensions(source, file_size, path)
        suffix = ".jpg"
    elif allow_exr and signature.startswith(b"v/1\x01"):
        dimensions = exr_stream_dimensions(source, file_size, path)
        suffix = ".exr"
    else:
        raise ValidationError(f"unsupported image content: {path}")
    require_imageio_decode(source, path, suffix)
    return dimensions


def archive_image_dimensions(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    path: str,
    *,
    allow_exr: bool,
) -> tuple[int, int]:
    with archive.open(info) as source:
        return stream_image_dimensions(
            source, info.file_size, path, allow_exr=allow_exr
        )


def add_pixels(
    total: int, dimensions: tuple[int, int], path: str, *, maximum_dimension: int,
    maximum_total: int,
) -> int:
    width, height = dimensions
    pixels = width * height
    require(
        width > 0 and height > 0
        and width <= maximum_dimension and height <= maximum_dimension
        and pixels <= IMAGE_PIXELS and total + pixels <= maximum_total,
        f"image budget exceeded: {path}",
    )
    return total + pixels


def skip_mp4_payload(source: BinaryIO, count: int, path: str) -> None:
    """Discard `count` bytes from an MP4 box payload in bounded chunks.

    Used for boxes we don't need to inspect — notably 'mdat', which can be
    up to the 128 MiB media asset limit and must never be materialized.
    """
    remaining = count
    while remaining > 0:
        chunk = source.read(min(remaining, 1024 * 1024))
        require(chunk, f"truncated MP4 payload: {path}")
        remaining -= len(chunk)


def mp4_box_header(
    source: BinaryIO, remaining: int, path: str
) -> tuple[bytes, int, int]:
    """Read one MP4 box header, handling 32-bit and 64-bit `largesize`.

    `remaining` bounds the enclosing region so a size==0 "extends to the end
    of the enclosing box" header can be resolved. Returns
    (box_type, payload_size, header_size).
    """
    require(remaining >= 8, f"truncated MP4 box header: {path}")
    head = read_exact(source, 8, f"truncated MP4 box header: {path}")
    size, box_type = struct.unpack(">I4s", head)
    header_size = 8
    if size == 1:
        require(remaining >= 16, f"truncated MP4 64-bit box size: {path}")
        size, = struct.unpack(
            ">Q", read_exact(source, 8, f"truncated MP4 64-bit box size: {path}")
        )
        header_size = 16
    if size == 0:
        payload_size = remaining - header_size
    else:
        require(size >= header_size, f"malformed MP4 box size: {path}")
        payload_size = size - header_size
    require(header_size + payload_size <= remaining, f"MP4 box exceeds its container: {path}")
    return box_type, payload_size, header_size


def mp4_moov_payload(archive: zipfile.ZipFile, info: zipfile.ZipInfo, path: str) -> bytes:
    """Return the raw payload of an MP4's top-level 'moov' box.

    Walks the top-level box list with bounded, forward-only reads, skipping
    every other box (notably 'mdat', which is never materialized) whether it
    falls before or after 'moov'. The structural 'moov' subtree itself is
    small by construction, so it is capped and read fully into memory for
    simple in-memory parsing of its children.
    """
    moov_payload: bytes | None = None
    with archive.open(info) as source:
        remaining = info.file_size
        while remaining > 0:
            box_type, payload_size, header_size = mp4_box_header(source, remaining, path)
            remaining -= header_size
            if box_type == b"moov" and moov_payload is None:
                require(payload_size <= MP4_MOOV_BYTES, f"MP4 moov box is too large: {path}")
                moov_payload = read_exact(source, payload_size, f"truncated MP4 moov box: {path}")
            else:
                skip_mp4_payload(source, payload_size, path)
            remaining -= payload_size
    require(moov_payload is not None, f"media video has no MP4 moov box: {path}")
    return moov_payload


def mp4_child_boxes(data: bytes, path: str):
    """Yield (box_type, payload) for each box in an in-memory MP4 container.

    Only used on already-bounded content (the 'moov' subtree and its
    descendants), so it is safe to slice `data` directly.
    """
    offset = 0
    total = len(data)
    while offset < total:
        require(offset + 8 <= total, f"truncated MP4 box header: {path}")
        size, box_type = struct.unpack_from(">I4s", data, offset)
        header_size = 8
        if size == 1:
            require(offset + 16 <= total, f"truncated MP4 64-bit box size: {path}")
            size, = struct.unpack_from(">Q", data, offset + 8)
            header_size = 16
        require(size == 0 or size >= header_size, f"malformed MP4 box size: {path}")
        end = total if size == 0 else offset + size
        require(offset + header_size <= end <= total, f"MP4 box exceeds its container: {path}")
        yield box_type, data[offset + header_size:end]
        offset = end


def mp4_first_child(data: bytes | None, wanted: bytes, path: str) -> bytes | None:
    if data is None:
        return None
    for box_type, payload in mp4_child_boxes(data, path):
        if box_type == wanted:
            return payload
    return None


def mp4_visual_sample_entry(moov_payload: bytes, path: str) -> tuple[bytes, bytes] | None:
    """Return (sample_entry_type, sample_entry_payload) for the first
    HEVC/H.264 visual sample entry found in any 'trak' of `moov_payload`, in
    document order, or None if there isn't one (e.g. an audio-only file).
    """
    for box_type, trak in mp4_child_boxes(moov_payload, path):
        if box_type != b"trak":
            continue
        mdia = mp4_first_child(trak, b"mdia", path)
        minf = mp4_first_child(mdia, b"minf", path)
        stbl = mp4_first_child(minf, b"stbl", path)
        stsd = mp4_first_child(stbl, b"stsd", path)
        if stsd is None:
            continue
        require(len(stsd) >= 8, f"malformed MP4 stsd box: {path}")
        for entry_type, entry in mp4_child_boxes(stsd[8:], path):
            if entry_type in VISUAL_SAMPLE_ENTRY_TYPES:
                return entry_type, entry
    return None


def require_hevc_pixel_format(entry_payload: bytes, path: str) -> None:
    """Enforce 8-bit 4:2:0 from an HEVCDecoderConfigurationRecord ('hvcC').

    Field layout is ISO/IEC 14496-15 8.3.3.1.2: chromaFormat is the low 2
    bits of byte 16 (after configurationVersion, the profile/tier/level
    fields, and the reserved+min_spatial_segmentation_idc/parallelismType
    bytes); bitDepthLumaMinus8 and bitDepthChromaMinus8 are the low 3 bits
    of bytes 17 and 18 respectively.
    """
    require(len(entry_payload) >= VISUAL_SAMPLE_ENTRY_FIXED_BYTES,
            f"malformed MP4 visual sample entry: {path}")
    config = mp4_first_child(
        entry_payload[VISUAL_SAMPLE_ENTRY_FIXED_BYTES:], b"hvcC", path
    )
    require(config is not None, f"media video has no hvcC box: {path}")
    require(len(config) >= 19, f"malformed MP4 hvcC box: {path}")
    chroma_format = config[16] & 0x03
    bit_depth_luma = config[17] & 0x07
    bit_depth_chroma = config[18] & 0x07
    require(
        chroma_format == 1,
        "media video must be 8-bit 4:2:0 limited-range HEVC/H.264: "
        f"{path} (chromaFormat {chroma_format})",
    )
    require(
        bit_depth_luma == 0 and bit_depth_chroma == 0,
        "media video must be 8-bit 4:2:0 limited-range HEVC/H.264: "
        f"{path} (bitDepth {bit_depth_luma + 8}/{bit_depth_chroma + 8})",
    )


def require_avc_pixel_format(entry_payload: bytes, path: str) -> None:
    """Enforce 8-bit 4:2:0 from an AVCDecoderConfigurationRecord ('avcC').

    Baseline/Main-profile records (ISO/IEC 14496-15 5.2.4.1.1) have no
    chroma/bit-depth fields at all and are 4:2:0 8-bit by definition; only
    the High-profile family (100/110/122/144) carries the trailing
    chroma_format/bit_depth_* bytes, which sit after the variable-length SPS
    and PPS NALU lists.
    """
    require(len(entry_payload) >= VISUAL_SAMPLE_ENTRY_FIXED_BYTES,
            f"malformed MP4 visual sample entry: {path}")
    config = mp4_first_child(
        entry_payload[VISUAL_SAMPLE_ENTRY_FIXED_BYTES:], b"avcC", path
    )
    require(config is not None, f"media video has no avcC box: {path}")
    require(len(config) >= 6, f"malformed MP4 avcC box: {path}")
    profile_idc = config[1]
    offset = 6
    for _ in range(config[5] & 0x1F):  # numOfSequenceParameterSets
        require(offset + 2 <= len(config), f"malformed MP4 avcC box: {path}")
        length, = struct.unpack_from(">H", config, offset)
        offset += 2 + length
        require(offset <= len(config), f"malformed MP4 avcC box: {path}")
    require(offset < len(config), f"malformed MP4 avcC box: {path}")
    num_pps = config[offset]
    offset += 1
    for _ in range(num_pps):
        require(offset + 2 <= len(config), f"malformed MP4 avcC box: {path}")
        length, = struct.unpack_from(">H", config, offset)
        offset += 2 + length
        require(offset <= len(config), f"malformed MP4 avcC box: {path}")
    if profile_idc not in AVC_EXTENDED_CHROMA_PROFILES:
        return  # baseline/main: 4:2:0 8-bit by definition, nothing more to check
    require(offset + 3 <= len(config), f"malformed MP4 avcC box: {path}")
    chroma_format = config[offset] & 0x03
    bit_depth_luma = config[offset + 1] & 0x07
    bit_depth_chroma = config[offset + 2] & 0x07
    require(
        chroma_format == 1 and bit_depth_luma == 0 and bit_depth_chroma == 0,
        "media video must be 8-bit 4:2:0 limited-range HEVC/H.264: "
        f"{path} (chromaFormat {chroma_format}, "
        f"bitDepth {bit_depth_luma + 8}/{bit_depth_chroma + 8})",
    )


def require_limited_range_color(entry_payload: bytes, path: str) -> None:
    """Reject a full-range 'colr' box of type 'nclx' if present.

    ISO/IEC 14496-12: the full_range_flag is the top bit of the byte after
    the three colour-description fields. A 'colr' box is optional and any
    non-'nclx' colour_type is left alone.
    """
    colr = mp4_first_child(
        entry_payload[VISUAL_SAMPLE_ENTRY_FIXED_BYTES:], b"colr", path
    )
    if colr is None:
        return
    require(len(colr) >= 4, f"malformed MP4 colr box: {path}")
    if colr[0:4] != b"nclx":
        return
    require(len(colr) >= 11, f"malformed MP4 colr box: {path}")
    require(
        colr[10] & 0x80 == 0,
        "media video must be 8-bit 4:2:0 limited-range HEVC/H.264: "
        f"{path} (full-range color)",
    )


def require_media_video_pixel_format(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, path: str
) -> None:
    """Reject a media video asset that is not 8-bit 4:2:0 limited-range.

    Regression guard for #157-adjacent-2026-09-11: an animated View's
    main.mp4 was encoded by feeding rgb24 raw frames to libx265 without
    `format=yuv420p`, producing HEVC 4:4:4 (gbrp) full-range video. That
    passed the container-signature-only check below and imported, but
    visionOS decoded it with wrong colours. The repo's own encoders
    (cut_media_loop.py, stitch_sector_tiles.py) already force yuv420p and
    tv range; this enforces the same contract on import.
    """
    moov_payload = mp4_moov_payload(archive, info, path)
    entry = mp4_visual_sample_entry(moov_payload, path)
    require(
        entry is not None,
        "media video must be 8-bit 4:2:0 limited-range HEVC/H.264: "
        f"{path} (no HEVC/H.264 sample entry)",
    )
    entry_type, entry_payload = entry
    if entry_type in HEVC_VISUAL_SAMPLE_ENTRY_TYPES:
        require_hevc_pixel_format(entry_payload, path)
    else:
        require_avc_pixel_format(entry_payload, path)
    require_limited_range_color(entry_payload, path)


def require_https(value: Any, field: str) -> None:
    require(isinstance(value, str), f"{field} must be an HTTPS URL")
    parsed = urllib.parse.urlsplit(value)
    require(
        parsed.scheme.lower() == "https" and bool(parsed.hostname)
        and parsed.username is None and parsed.password is None and not parsed.fragment,
        f"{field} must be an HTTPS URL without credentials or fragment",
    )


def require_text(value: Any, field: str, maximum: int) -> None:
    require(
        isinstance(value, str) and bool(value.strip())
        and len(value.encode("utf-8")) <= maximum,
        f"{field} is missing or too long",
    )


def validate_license_shape(value: Any, path: str) -> None:
    require(isinstance(value, dict), f"{path} must be an object")
    exact_keys(
        value,
        required={"identifier", "name", "url"},
        context=path,
    )
    require_text(value["identifier"], f"{path}.identifier", 100)
    require_text(value["name"], f"{path}.name", 200)
    require_https(value["url"], f"{path}.url")


def validate_rights_shape(value: Any, path: str) -> None:
    require(isinstance(value, dict), f"{path} must be an object")
    exact_keys(
        value,
        required={"statement", "url"},
        context=path,
    )
    require_text(value["statement"], f"{path}.statement", 1_000)
    require_https(value["url"], f"{path}.url")


def validate_provenance(value: dict[str, Any], path: str) -> None:
    exact_keys(
        value,
        required={
            "formatVersion", "creatorOrAgency", "requestedCredit",
            "modificationNotes", "aiGenerated",
        },
        optional={
            "sourcePageURL", "originalAssetURL", "license", "rights",
            "aiProvider", "importSource",
        },
        context=path,
    )
    require(type(value["formatVersion"]) is int and value["formatVersion"] == 1,
            f"{path}.formatVersion must be 1")
    require_text(value["creatorOrAgency"], f"{path}.creatorOrAgency", 200)
    require_text(value["requestedCredit"], f"{path}.requestedCredit", 1_000)
    require_text(value["modificationNotes"], f"{path}.modificationNotes", 2_000)
    require(type(value["aiGenerated"]) is bool, f"{path}.aiGenerated must be boolean")
    has_license = "license" in value
    has_rights = "rights" in value
    require(
        has_license != has_rights,
        f"{path} must contain exactly one of license or rights",
    )
    license_value = value.get("license")
    if has_license:
        validate_license_shape(license_value, f"{path}.license")
    else:
        validate_rights_shape(value["rights"], f"{path}.rights")
    for field in ("sourcePageURL", "originalAssetURL"):
        if field in value:
            require_https(value[field], f"{path}.{field}")
    if value["aiGenerated"]:
        require_text(value.get("aiProvider"), f"{path}.aiProvider", 200)
    else:
        require("aiProvider" not in value, f"{path}.aiProvider requires aiGenerated=true")
    if "importSource" in value:
        require(
            value["importSource"] in {"photos", "files"},
            f"{path}.importSource must be photos or files",
        )
        require(
            value["creatorOrAgency"] == "Locus user"
            and isinstance(license_value, dict)
            and license_value["identifier"] == "USER-PROVIDED"
            and value["requestedCredit"] == "Imported by the user"
            and value["modificationNotes"]
                == "Normalized to JPEG and packaged locally by Locus."
            and value["aiGenerated"] is False
            and "sourcePageURL" not in value
            and "originalAssetURL" not in value,
            f"{path}.importSource is reserved for direct Locus imports",
        )


PROVENANCE_DETAIL_COMPONENTS = frozenset({"picture", "motion", "sound", "sun-free-sky"})


def validate_provenance_detail(
    value: dict[str, Any],
    media: Any,
    provenance: dict[str, Any],
    path: str,
    sound: Any = None,
) -> None:
    exact_keys(value, required={"formatVersion", "components"}, context=path)
    require(type(value["formatVersion"]) is int and value["formatVersion"] == 1,
            f"{path}.formatVersion must be 1")
    components = value["components"]
    require(isinstance(components, list) and bool(components),
            f"{path}.components must be a non-empty array")

    video_source_ids: set[str] = set()
    all_source_ids: set[str] = set()
    if isinstance(media, dict):
        for source in media.get("sources") or []:
            if isinstance(source, dict) and isinstance(source.get("id"), str):
                all_source_ids.add(source["id"])
                if "video" in source:
                    video_source_ids.add(source["id"])

    if isinstance(sound, dict):
        all_source_ids.update(source['id'] for source in sound.get('sources', []) if isinstance(source, dict) and isinstance(source.get('id'), str))

    picture_count = 0
    seen_source_ids: set[str] = set()
    for index, entry in enumerate(components):
        entry_path = f"{path}.components[{index}]"
        require(isinstance(entry, dict), f"{entry_path} must be an object")
        exact_keys(
            entry,
            required={"component", "aiGenerated"},
            optional={
                "providers", "sourceID", "credit", "license", "rights",
                "sourcePageURL", "notes",
            },
            context=entry_path,
        )
        component = entry["component"]
        require(component in PROVENANCE_DETAIL_COMPONENTS,
                f"{entry_path}.component is invalid")
        require(type(entry["aiGenerated"]) is bool,
                f"{entry_path}.aiGenerated must be boolean")
        ai_generated = entry["aiGenerated"]
        if ai_generated:
            providers = entry.get("providers")
            require(
                isinstance(providers, list) and bool(providers) and all(
                    isinstance(item, str) and bool(item)
                    and len(item.encode("utf-8")) <= 200
                    for item in providers
                ),
                f"{entry_path}.providers is required and must be a non-empty "
                "array of short strings when aiGenerated is true",
            )
        else:
            require("providers" not in entry,
                    f"{entry_path}.providers requires aiGenerated=true")

        if component == "picture":
            picture_count += 1
            require(
                ai_generated == provenance.get("aiGenerated"),
                f"{entry_path}.aiGenerated must match provenance.json aiGenerated",
            )
        elif component == "sun-free-sky":
            require(isinstance(entry.get("notes"), str) and bool(entry["notes"].strip()),
                    entry_path + ".notes must name the sun-free sky tool/run")
        elif component == "motion":
            require(bool(video_source_ids),
                    f"{entry_path} requires media with a video source")
        else:
            require(bool(all_source_ids),
                    f"{entry_path} requires media with at least one source")

        if "sourceID" in entry:
            source_id = entry["sourceID"]
            require(isinstance(source_id, str) and source_id in all_source_ids,
                    f"{entry_path}.sourceID must name a media.sources[].id or sound.sources[].id")
            require(source_id not in seen_source_ids,
                    f"{entry_path}.sourceID duplicates another component")
            seen_source_ids.add(source_id)

        if "credit" in entry:
            require_text(entry["credit"], f"{entry_path}.credit", 200)
        if "notes" in entry:
            require_text(entry["notes"], f"{entry_path}.notes", 2_000)
        if "sourcePageURL" in entry:
            require_https(entry["sourcePageURL"], f"{entry_path}.sourcePageURL")

        has_license = "license" in entry
        has_rights = "rights" in entry
        require(
            not (has_license and has_rights),
            f"{entry_path} must contain at most one of license or rights",
        )
        if has_license:
            validate_license_shape(entry["license"], f"{entry_path}.license")
        if has_rights:
            validate_rights_shape(entry["rights"], f"{entry_path}.rights")

    require(picture_count <= 1,
            f"{path}.components must contain at most one picture entry")


def require_number_list(value: Any, count: int, field: str, *, positive=False) -> None:
    require(isinstance(value, list) and len(value) == count, f"{field} must have {count} values")
    require(
        all(
            type(item) in {int, float}
            and math.isfinite(item)
            and (not positive or item > 0)
            for item in value
        ),
        f"{field} has invalid values",
    )


def validate_teleport_catalog(
    value: dict[str, Any], house_id: Any, context: str
) -> set[str]:
    require(valid_identifier(house_id), f"{context}.houseID is invalid")
    houses = value.get("houses")
    require(isinstance(houses, dict), f"{context}.houses must be an object")

    # JSONDecoder decodes every house before PackageV2Store selects one, so
    # every entry must have the public document shape even though semantic
    # checks below apply only to houses[houseID].
    for candidate_id, raw_points in houses.items():
        require(isinstance(candidate_id, str), f"{context}.houses has an invalid key")
        require(isinstance(raw_points, list),
                f"{context}.houses.{candidate_id} must be an array")
        for index, point in enumerate(raw_points):
            point_context = f"{context}.houses.{candidate_id}[{index}]"
            require(isinstance(point, dict), f"{point_context} must be an object")
            for field in ("id", "title"):
                require(isinstance(point.get(field), str),
                        f"{point_context}.{field} must be a string")
            require_number_list(
                point.get("anchorXZ"), 2, f"{point_context}.anchorXZ")
            for field in ("sourceFloorOffset", "eyeHeight", "yawRadians"):
                number = point.get(field)
                require(type(number) in {int, float} and math.isfinite(number),
                        f"{point_context}.{field} must be finite")

    require(house_id in houses, f"teleportCatalog has no house named {house_id}")
    require(
        bool(houses[house_id]),
        f"{context}.houses.{house_id} must contain at least one teleport point",
    )
    point_ids: set[str] = set()
    for index, point in enumerate(houses[house_id]):
        point_context = f"teleportPoints[{index}]"
        point_id = point["id"]
        require(valid_identifier(point_id), f"{point_context}.id is invalid")
        require(point_id not in point_ids,
                f"teleportPoints.id contains duplicate value {point_id}")
        point_ids.add(point_id)
        require(bool(point["title"].strip()), f"{point_context}.title is invalid")
        require(all(0 <= number <= 1 for number in point["anchorXZ"]),
                f"{point_context}.anchorXZ has invalid values")
        require(point["sourceFloorOffset"] >= 0,
                f"{point_context}.sourceFloorOffset is invalid")
        require(point["eyeHeight"] > 0,
                f"{point_context}.eyeHeight is invalid")
    return point_ids


def validate_seat_groups(
    value: Any, teleport_ids: set[str], context: str
) -> None:
    require(isinstance(value, list) and value, f"{context} must be a non-empty array")
    group_ids: set[str] = set()
    member_ids: set[str] = set()
    for index, group in enumerate(value):
        group_context = f"{context}[{index}]"
        require(isinstance(group, dict), f"{group_context} must be an object")
        exact_keys(
            group, required={"id", "title", "seatIDs"}, context=group_context)
        group_id = group["id"]
        require(valid_identifier(group_id), f"{group_context}.id is invalid")
        require(group_id not in group_ids,
                f"{context}.id contains duplicate value {group_id}")
        group_ids.add(group_id)
        require_text(group["title"], f"{group_context}.title", 200)
        seat_ids = group["seatIDs"]
        require(isinstance(seat_ids, list) and seat_ids,
                f"{group_context}.seatIDs must be a non-empty array")
        for seat_id in seat_ids:
            require(valid_identifier(seat_id),
                    f"{group_context}.seatIDs contains an invalid ID")
            require(seat_id in teleport_ids,
                    f"{group_context}.seatIDs references unknown teleport {seat_id}")
            require(seat_id not in member_ids,
                    f"{context}.seatIDs contains duplicate value {seat_id}")
            member_ids.add(seat_id)


def valid_video_surface_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.encode("utf-8")) <= 64
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value)
    )


def validate_video_surfaces(
    value: Any, luminaire_group_ids: set[str], context: str
) -> set[str]:
    """Structural shape only; entity resolution and ftyp/size checks on the
    referenced `.mp4` happen against the actual archive bytes in
    `validate_payload`, matching how `sound` and `media` assets are checked.
    """
    require(isinstance(value, list) and value and len(value) <= 2,
            f"{context} must contain 1 or 2 surfaces")
    ids: set[str] = set()
    videos: set[str] = set()
    for index, surface in enumerate(value):
        surface_context = f"{context}[{index}]"
        require(isinstance(surface, dict), f"{surface_context} must be an object")
        exact_keys(
            surface,
            required={"id", "displayName", "entityName", "video"},
            optional={"luminaireGroupID"},
            context=surface_context,
        )
        require(valid_video_surface_identifier(surface["id"]),
                f"{surface_context}.id is invalid")
        require(surface["id"] not in ids,
                f"{context}.id contains duplicate value {surface['id']}")
        ids.add(surface["id"])
        require_text(surface["displayName"], f"{surface_context}.displayName", 200)
        require_text(surface["entityName"], f"{surface_context}.entityName", 200)
        video = surface["video"]
        require(
            isinstance(video, str) and video
            and "/" not in video and "\\" not in video
            and video.lower().endswith(".mp4"),
            f"{surface_context}.video is invalid",
        )
        require(video not in videos,
                f"{context}.video contains duplicate value {video}")
        videos.add(video)
        if "luminaireGroupID" in surface:
            require(surface["luminaireGroupID"] in luminaire_group_ids,
                    f"{surface_context}.luminaireGroupID is unknown")
    return videos


def validate_baked_light_layers(
    value: Any, luminaire_group_ids: set[str], context: str
) -> set[str]:
    """Structural shape only; byte limit, PNG header/dimension, and
    referenced-set-equals-actual-files are checked by the caller against the
    real extracted files, matching `validate_video_surfaces`.
    """
    require(isinstance(value, list) and value and len(value) <= 12,
            f"{context} must contain 1 to 12 entries")
    used_group_ids: set[str] = set()
    images: set[str] = set()
    for index, layer in enumerate(value):
        layer_context = f"{context}[{index}]"
        require(isinstance(layer, dict), f"{layer_context} must be an object")
        exact_keys(
            layer,
            required={"luminaireGroupID", "image"},
            context=layer_context,
        )
        group_id = layer["luminaireGroupID"]
        require(isinstance(group_id, str) and group_id in luminaire_group_ids,
                f"{layer_context}.luminaireGroupID is unknown")
        require(group_id not in used_group_ids,
                f"{layer_context}.luminaireGroupID is already used by another layer")
        used_group_ids.add(group_id)
        image = layer["image"]
        require(
            isinstance(image, str) and image
            and "/" not in image and "\\" not in image
            and image.lower().endswith(".png"),
            f"{layer_context}.image is invalid",
        )
        require(image not in images,
                f"{context} contains duplicate value {image}")
        images.add(image)
    return images


def light_layer_png_info(data: bytes, path: str) -> tuple[int, int, int, int]:
    """(width, height, bit depth, color type), reusing `png_dimensions`'
    full structural PNG decode/checksum validation and additionally reading
    the leading IHDR's bit depth and color type so the caller can enforce
    the light-layer-specific "8- or 16-bit RGB or RGBA" contract.
    """
    require(data.startswith(b"\x89PNG\r\n\x1a\n"), f"{path} must be a PNG file")
    width, height = png_dimensions(io.BytesIO(data), len(data), path)
    _, _, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", data[16:29])
    return width, height, bit_depth, color_type


PARTICLE_EFFECT_PRESETS = {"fire"}


def validate_particle_effects(value: Any, context: str) -> None:
    """Structural shape only; `anchorEntity` resolution is checked the same
    way as every other authored USDZ entity reference in this package, not
    here (this validator never opens `scene.usdz`).
    """
    require(isinstance(value, list) and value and len(value) <= 4,
            f"{context} must contain 1 to 4 entries")
    ids: set[str] = set()
    for index, effect in enumerate(value):
        effect_context = f"{context}[{index}]"
        require(isinstance(effect, dict), f"{effect_context} must be an object")
        exact_keys(
            effect,
            required={"id", "displayName", "preset", "anchorEntity", "sizeMeters"},
            context=effect_context,
        )
        require(valid_video_surface_identifier(effect["id"]),
                f"{effect_context}.id is invalid")
        require(effect["id"] not in ids,
                f"{context}.id contains duplicate value {effect['id']}")
        ids.add(effect["id"])
        require_text(effect["displayName"], f"{effect_context}.displayName", 200)
        require(effect["preset"] in PARTICLE_EFFECT_PRESETS,
                f"{effect_context}.preset is unknown")
        require_text(effect["anchorEntity"], f"{effect_context}.anchorEntity", 200)
        require_number_list(
            effect["sizeMeters"], 3, f"{effect_context}.sizeMeters")
        require(
            all(0 < component <= 3 for component in effect["sizeMeters"]),
            f"{effect_context}.sizeMeters components must be within (0, 3]")


def validate_spatial_adaptation(
    value: Any, teleport_ids: set[str], context: str
) -> None:
    require(isinstance(value, dict), f"{context} must be an object")
    walls = value.get("wallEntities")
    roofs = value.get("roofEntities")
    desks = value.get("deskEntitiesByTeleportID")
    require(isinstance(walls, list) and all(isinstance(item, str) for item in walls),
            f"{context}.wallEntities must be a string array")
    require(isinstance(roofs, list) and all(isinstance(item, str) for item in roofs),
            f"{context}.roofEntities must be a string array")
    require(
        isinstance(desks, dict)
        and all(isinstance(key, str) and isinstance(item, str)
                for key, item in desks.items()),
        f"{context}.deskEntitiesByTeleportID must be a string map",
    )
    for field, names in (("wallEntities", walls), ("roofEntities", roofs)):
        require(all(bool(name.strip()) for name in names),
                f"{context}.{field} contains an empty name")
        require(len(names) == len(set(names)),
                f"{context}.{field} contains a duplicate name")
    require(set(walls).isdisjoint(roofs),
            f"{context}.wallEntities overlaps roofEntities")
    for teleport_id, entity_name in desks.items():
        require(valid_identifier(teleport_id),
                f"{context}.deskEntitiesByTeleportID has an invalid teleport ID")
        require(teleport_id in teleport_ids and bool(entity_name.strip()),
                f"{context}.deskEntitiesByTeleportID.{teleport_id} is invalid")
    if "deskGroupEntitiesByTeleportID" in value:
        groups = value["deskGroupEntitiesByTeleportID"]
        require(isinstance(groups, dict),
                f"{context}.deskGroupEntitiesByTeleportID must be an object")
        for teleport_id, entity_name in groups.items():
            require(
                isinstance(teleport_id, str) and isinstance(entity_name, str)
                and bool(entity_name.strip()),
                f"{context}.deskGroupEntitiesByTeleportID.{teleport_id} is invalid",
            )
            require(
                teleport_id in desks,
                f"{context}.deskGroupEntitiesByTeleportID.{teleport_id} has no desk surface",
            )


def validate_usdz(
    outer: zipfile.ZipFile, info: zipfile.ZipInfo, path: str
) -> dict[str, int]:
    require(info.file_size <= MODEL_BYTES, f"model budget exceeded: {path}")
    # A real temp file, not tempfile.SpooledTemporaryFile: on Python < 3.11
    # SpooledTemporaryFile has no seekable() while it is still the in-memory
    # BytesIO (it only proxies the underlying file's methods after rolling
    # over to disk), and zipfile.ZipFile requires a seekable file object.
    # That broke every USDZ small enough to stay in memory. file_size is
    # already bounded by MODEL_BYTES above, so this can't grow unbounded.
    with tempfile.TemporaryFile() as temporary:
        with outer.open(info) as source:
            while chunk := source.read(1024 * 1024):
                temporary.write(chunk)
        temporary.seek(0)
        try:
            model = zipfile.ZipFile(temporary)
        except zipfile.BadZipFile as error:
            raise ValidationError(f"Room scene is not USDZ: {path}") from error
        with model:
            entries = model.infolist()
            require(0 < len(entries) <= MODEL_ENTRIES, f"model entry budget exceeded: {path}")
            seen = set()
            expanded = 0
            texture_pixels = 0
            has_root_layer = False
            for entry in entries:
                require(not is_symlink(entry), f"USDZ symlink is not allowed: {entry.filename}")
                value = safe_model_path(entry.filename, entry.is_dir())
                key = collision_key(value)
                require(key not in seen, f"duplicate USDZ path: {entry.filename}")
                seen.add(key)
                if entry.is_dir():
                    continue
                require(entry.compress_type == zipfile.ZIP_STORED,
                        f"USDZ entry is compressed: {entry.filename}")
                expanded += entry.file_size
                require(expanded <= MODEL_EXPANDED_BYTES, f"model expanded budget exceeded: {path}")
                extension = PurePosixPath(value).suffix.lower().lstrip(".")
                require(extension in USDZ_EXTENSIONS,
                        f"unsupported USDZ entry: {entry.filename}")
                if "/" not in value and extension in {"usd", "usda", "usdc"}:
                    has_root_layer = True
                if extension in {"png", "jpg", "jpeg", "exr"}:
                    with model.open(entry) as source:
                        dimensions = stream_image_dimensions(
                            source,
                            entry.file_size,
                            entry.filename,
                            allow_exr=True,
                        )
                    texture_pixels = add_pixels(
                        texture_pixels, dimensions, entry.filename,
                        maximum_dimension=MODEL_TEXTURE_DIMENSION,
                        maximum_total=MODEL_TEXTURE_PIXELS,
                    )
            require(has_root_layer, f"USDZ has no root USD layer: {path}")
        temporary.seek(0)
        statistics = actual_usd_statistics(temporary, path)
        require(
            statistics["triangleCount"] <= TRIANGLES,
            f"actual USD triangle budget exceeded: {path}",
        )
        require(
            statistics["materialCount"] <= MATERIALS,
            f"actual USD material budget exceeded: {path}",
        )
        require(
            statistics["entityCount"] <= ENTITIES,
            f"actual USD entity budget exceeded: {path}",
        )
        return statistics


def actual_usd_statistics(model: BinaryIO, path: str) -> dict[str, int]:
    """Load and flatten the real USD stage before counting its authored prims.

    Xcode's USD tools understand USDA, USDC, references, variants, and USDZ.
    That keeps the public validator from treating self-reported quality fields
    as a security boundary. Unsupported instancing and procedural shapes fail
    closed because their rendered expansion is not directly countable here.
    """
    usdchecker = shutil.which("usdchecker")
    usdcat = shutil.which("usdcat")
    require(
        usdchecker is not None and usdcat is not None,
        "usdchecker and usdcat are required for actual USD budget inspection",
    )
    with tempfile.TemporaryDirectory(prefix="locusplace-usd-") as directory:
        root = Path(directory)
        model_path = root / "scene.usdz"
        flattened_path = root / "scene.usda"
        model.seek(0)
        with model_path.open("wb") as output:
            shutil.copyfileobj(model, output, length=1024 * 1024)
        try:
            checked = subprocess.run(
                [usdchecker, "--arkit", str(model_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=False,
            )
            require(
                checked.returncode == 0,
                f"Room scene fails RealityKit USD validation: {path}",
            )
            flattened = subprocess.run(
                [
                    usdcat,
                    "--flatten",
                    "--skipSourceFileComment",
                    str(model_path),
                    "-o",
                    str(flattened_path),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
                check=False,
            )
            require(
                flattened.returncode == 0 and flattened_path.is_file(),
                f"Room scene could not be flattened for inspection: {path}",
            )
        except subprocess.TimeoutExpired as error:
            raise ValidationError(
                f"Room scene exceeded the USD inspection time budget: {path}"
            ) from error
        require(
            flattened_path.stat().st_size <= MODEL_FLATTENED_BYTES,
            f"flattened USD budget exceeded: {path}",
        )
        return inspect_flattened_usda(flattened_path, path)


def inspect_flattened_usda(path: Path, source_path: str) -> dict[str, int]:
    prim = re.compile(r'^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s+"')
    face_counts_start = re.compile(r"\bfaceVertexCounts\s*=\s*\[")
    statistics = {
        "triangleCount": 0,
        "materialCount": 0,
        "entityCount": 0,
    }
    reading_face_counts = False

    with path.open("r", encoding="utf-8") as source:
        for line in source:
            match = prim.match(line)
            if match:
                prim_type = match.group(1)
                statistics["entityCount"] += 1
                if prim_type == "Material":
                    statistics["materialCount"] += 1
                elif prim_type == "Cube":
                    statistics["triangleCount"] += 12
                elif prim_type in {
                    "PointInstancer", "Sphere", "Capsule", "Cylinder", "Cone",
                }:
                    raise ValidationError(
                        "USD procedural or instanced geometry cannot be "
                        f"bounded safely: {source_path} ({prim_type})"
                    )
            if "instanceable = true" in line:
                raise ValidationError(
                    f"USD native instances are not allowed: {source_path}"
                )
            if "faceVertexCounts.timeSamples" in line:
                raise ValidationError(
                    f"time-sampled USD topology is not allowed: {source_path}"
                )

            segment = line
            if not reading_face_counts:
                start = face_counts_start.search(segment)
                if not start:
                    continue
                segment = segment[start.end():]
                reading_face_counts = True
            if reading_face_counts:
                if "]" in segment:
                    segment, _ = segment.split("]", 1)
                    reading_face_counts = False
                integers = re.findall(r"-?\d+", segment)
                residue = re.sub(r"-?\d+", "", segment)
                require(
                    not residue.replace(",", "").strip(),
                    f"USD face topology is malformed: {source_path}",
                )
                for raw_count in integers:
                    count = int(raw_count)
                    require(
                        count >= 0,
                        f"USD face topology is malformed: {source_path}",
                    )
                    statistics["triangleCount"] += max(0, count - 2)

    require(
        not reading_face_counts,
        f"USD face topology is malformed: {source_path}",
    )
    return statistics


def safe_model_path(raw: str, directory: bool) -> str:
    value = raw[:-1] if directory and raw.endswith("/") else raw
    components = value.split("/")
    require(value and unicodedata.normalize("NFC", value) == value,
            f"unsafe USDZ path: {raw}")
    require(len(value.encode("utf-8")) <= PATH_BYTES, f"USDZ path is too long: {raw}")
    require(not value.startswith("/") and "\\" not in value, f"unsafe USDZ path: {raw}")
    require(
        all(component not in {"", ".", ".."} and len(component.encode("utf-8")) <= COMPONENT_BYTES
            for component in components),
        f"unsafe USDZ path: {raw}",
    )
    return value


# `destination.midground.windSway` numeric ranges. Mirrors
# `PackageV2Store.validate(at:)`'s `midground.windSway` block in
# viewer/LocusViewer/Models/PackageV2.swift; keep both in sync.
MIDGROUND_WIND_SWAY_RANGES: dict[str, tuple[float, float]] = {
    "amplitudeDegrees": (0.0, 15.0),
    "periodSeconds": (0.5, 30.0),
    "directionDegrees": (-360.0, 360.0),
    "wavelengthMeters": (1.0, 200.0),
}

# The first app version that renders `midground.windSway.wavelengthMeters`
# as a travelling wave; older readers would silently keep per-plant sway.
MIDGROUND_WIND_SWAY_WAVE_MINIMUM_APP = (1, 3, 4)

# `destination.midground.water` numeric ranges. Mirrors
# `PackageV2Store.validate(_ water:, in:)` in
# viewer/LocusViewer/Models/PackageV2.swift; keep both in sync.
MIDGROUND_WATER_RANGES: dict[str, tuple[float, float]] = {
    "levelMeters": (-20.0, 0.0),
    "tileMeters": (0.25, 100.0),
    "normalStrength": (0.0, 4.0),
    "waveSpeed": (0.0, 10.0),
    "reflectionBlur": (0.0, 8.0),
    "sunGlint": (0.0, 20.0),
    # Virtual metres, not a cutoff on the water's own visible extent: the
    # viewer's horizon skirt (viewer/LocusViewer/Rendering/LakeWater.swift's
    # `disc`) renders water to the painted shoreline regardless of these
    # values now. They fade only the fine detail (normal/ripple/FFT
    # strength, reflection and glint sharpness) toward a smooth, blurred
    # reflection -- see `DetailFade` in
    # viewer/tools/make_lake_water_material.py and
    # docs/package-spec-v2.md's `midground.water.fadeStartMeters`. The
    # upper bound matches that shader's own MAX_VIRTUAL_DISTANCE clamp.
    "fadeStartMeters": (1.0, 5000.0),
    "fadeEndMeters": (1.0, 5000.0),
    "waveDirectionDegrees": (-360.0, 360.0),
}

# `destination.midground.water.shore` numeric ranges. Mirrors the same
# Swift-side `validate(_ water:, in:)`.
MIDGROUND_SHORE_RANGES: dict[str, tuple[float, float]] = {
    "clarity": (0.0, 20.0),
    "swashAmplitudeMeters": (0.0, 0.5),
    "swashPeriodSeconds": (0.5, 60.0),
    "foam": (0.0, 4.0),
    "caustics": (0.0, 4.0),
    "beachSlope": (0.02, 1.0),
}

# `destination.midground.water.waves` numeric ranges (excluding `frames`/
# `columns`, which are integer counts checked separately). Mirrors the same
# Swift-side `validate(_ water:, in:)`.
MIDGROUND_WAVES_RANGES: dict[str, tuple[float, float]] = {
    "loopSeconds": (1.0, 120.0),
    "tileMeters": (0.5, 50.0),
}

# `destination.midground.water.surf` numeric ranges (excluding
# `crossShoreMeters`/`alongShoreMeters`/`cellMeters`, checked together
# below since they also bound the solver grid). Mirrors the same
# Swift-side `validate(_ water:, in:)`.
MIDGROUND_SURF_RANGES: dict[str, tuple[float, float]] = {
    "strength": (0.0, 2.0),
    "tideMeters": (-0.5, 0.5),
    "shoreNormalDegrees": (-360.0, 360.0),
}


def png_ihdr(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, path: str
) -> tuple[int, int, int, int]:
    """Read `(width, height, bitDepth, colorType)` from a PNG's IHDR chunk
    without decoding the rest of the file. Callers that also need full
    decode/dimension validation still call `archive_image_dimensions`; this
    is only for the extra bit-depth/color-type checks it does not do."""
    with archive.open(info) as source:
        header = source.read(26)
    require(
        len(header) == 26 and header[:8] == b"\x89PNG\r\n\x1a\n"
        and header[12:16] == b"IHDR",
        f"{path} must be a PNG",
    )
    width, height, bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
    return width, height, bit_depth, color_type


def validate_midground_water_waves(
    base: str,
    waves: Any,
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    referenced_asset,
    account_image,
) -> None:
    """Validate `destination.midground.water.waves`, a looping FFT
    wave-normal atlas (`WaveFrames.texture` in
    viewer/LocusViewer/Rendering/WaveFrames.swift slices it into a mipmapped
    2D texture array, one square frame per array slice, `columns` per atlas
    row, row-major). Beyond the ordinary file/range checks, the atlas must
    actually hold that layout: its width must divide evenly into `columns`
    equal-width frames, and its height must fit `ceil(frames / columns)`
    rows of that same size, exactly what `WaveFrames.texture` requires to
    slice it without reading past a row or column boundary."""
    require(isinstance(waves, dict), f"{base}.midground.water.waves must be an object")
    exact_keys(
        waves,
        required={"atlas", "frames", "columns", "loopSeconds", "tileMeters"},
        context=f"{base}.midground.water.waves",
    )
    frames = waves["frames"]
    columns = waves["columns"]
    require(
        isinstance(frames, int) and not isinstance(frames, bool) and 2 <= frames <= 512,
        f"{base}.midground.water.waves.frames must be an integer 2...512",
    )
    require(
        isinstance(columns, int) and not isinstance(columns, bool) and 1 <= columns <= 64,
        f"{base}.midground.water.waves.columns must be an integer 1...64",
    )
    for field, (lower, upper) in MIDGROUND_WAVES_RANGES.items():
        value = waves[field]
        require(
            is_finite_number(value) and lower <= value <= upper,
            f"{base}.midground.water.waves.{field} must be finite and within range",
        )
    atlas_path = referenced_asset(base, waves["atlas"], "midground.water.waves.atlas")
    width, height = archive_image_dimensions(
        archive, infos[atlas_path], atlas_path, allow_exr=False)
    account_image(atlas_path, (width, height))
    png_ihdr(archive, infos[atlas_path], atlas_path)
    require(
        width % columns == 0,
        f"{atlas_path} width must be evenly divisible by waves.columns",
    )
    size = width // columns
    rows = -(-frames // columns)  # ceil division, matching WaveFrames.texture
    require(
        height >= rows * size,
        f"{atlas_path} height must be at least "
        "ceil(frames / columns) * (width / columns)",
    )


def validate_midground_water_shore(
    base: str,
    shore: Any,
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    referenced_asset,
    account_image,
) -> None:
    """Validate `destination.midground.water.shore`, the top-down bake used
    for the beach/shallow-water look. `bedAlbedo` follows the ordinary
    JPEG/PNG rule every other referenced image does; `bedHeight` is
    stricter, an 8-bit grayscale PNG the shader reads as a raw height
    channel; `detail` just needs to be a genuine PNG. The optional `field`
    (run-up height and wave-phase per texel) is stricter too: an 8-bit RGB
    PNG, not grayscale or RGBA. The optional `sunVisibility` (255 = fully
    sunlit, same extent/orientation as `bedHeight`) is an 8-bit grayscale
    PNG like `bedHeight`; absent means the shader treats the bed as fully
    sunlit."""
    require(isinstance(shore, dict), f"{base}.midground.water.shore must be an object")
    exact_keys(
        shore,
        required={
            "bedAlbedo", "bedHeight", "detail", "extentMeters", "heightRangeMeters",
        },
        optional={
            "clarity", "swashAmplitudeMeters", "swashPeriodSeconds", "foam", "caustics",
            "field", "beachSlope", "sunVisibility",
        },
        context=f"{base}.midground.water.shore",
    )
    albedo_path = referenced_asset(
        base, shore["bedAlbedo"], "midground.water.shore.bedAlbedo")
    account_image(
        albedo_path,
        archive_image_dimensions(archive, infos[albedo_path], albedo_path, allow_exr=False),
    )

    height_path = referenced_asset(
        base, shore["bedHeight"], "midground.water.shore.bedHeight")
    account_image(
        height_path,
        archive_image_dimensions(archive, infos[height_path], height_path, allow_exr=False),
    )
    _, _, bit_depth, color_type = png_ihdr(archive, infos[height_path], height_path)
    require(
        bit_depth == 8 and color_type == 0,
        f"{height_path} must be an 8-bit grayscale PNG",
    )

    detail_path = referenced_asset(
        base, shore["detail"], "midground.water.shore.detail")
    account_image(
        detail_path,
        archive_image_dimensions(archive, infos[detail_path], detail_path, allow_exr=False),
    )
    _, _, _, detail_color_type = png_ihdr(
        archive, infos[detail_path], detail_path)
    require(
        detail_color_type in {2, 6},
        f"{detail_path} must be an RGB PNG",
    )

    if "field" in shore:
        field_path = referenced_asset(
            base, shore["field"], "midground.water.shore.field")
        field_dimensions = archive_image_dimensions(
            archive, infos[field_path], field_path, allow_exr=False)
        account_image(field_path, field_dimensions)
        _, _, field_bit_depth, field_color_type = png_ihdr(
            archive, infos[field_path], field_path)
        require(
            field_bit_depth == 8 and field_color_type == 2,
            f"{field_path} must be an 8-bit RGB PNG",
        )

    if "sunVisibility" in shore:
        # Same extent/orientation as bedHeight, 255 = fully sunlit; absent
        # means the shader treats the bed as fully sunlit everywhere, so
        # this asset stays optional (see LakeWater.usda's SunVisibility
        # input and PackageV2's shore.sunVisibility doc comment).
        sun_visibility_path = referenced_asset(
            base, shore["sunVisibility"], "midground.water.shore.sunVisibility")
        sun_visibility_dimensions = archive_image_dimensions(
            archive, infos[sun_visibility_path], sun_visibility_path, allow_exr=False)
        account_image(sun_visibility_path, sun_visibility_dimensions)
        _, _, sun_visibility_bit_depth, sun_visibility_color_type = png_ihdr(
            archive, infos[sun_visibility_path], sun_visibility_path)
        require(
            sun_visibility_bit_depth == 8 and sun_visibility_color_type == 0,
            f"{sun_visibility_path} must be an 8-bit grayscale PNG",
        )

    extent = shore["extentMeters"]
    require(
        isinstance(extent, list) and len(extent) == 4
        and all(is_finite_number(v) and abs(v) <= 200 for v in extent)
        and extent[0] < extent[2] and extent[1] < extent[3],
        f"{base}.midground.water.shore.extentMeters must be four finite "
        "values [minX, minZ, maxX, maxZ] with minX < maxX and minZ < maxZ, "
        "each with |v| <= 200",
    )
    height_range = shore["heightRangeMeters"]
    require(
        isinstance(height_range, list) and len(height_range) == 2
        and all(is_finite_number(v) and abs(v) <= 50 for v in height_range)
        and height_range[0] < height_range[1],
        f"{base}.midground.water.shore.heightRangeMeters must be two "
        "finite values [lo, hi] with lo < hi, each with |v| <= 50",
    )

    def in_shore_range(field: str, value: Any) -> bool:
        lower, upper = MIDGROUND_SHORE_RANGES[field]
        return is_finite_number(value) and lower <= value <= upper

    for field in MIDGROUND_SHORE_RANGES:
        if field not in shore:
            continue
        require(
            in_shore_range(field, shore[field]),
            f"{base}.midground.water.shore.{field} must be finite and within range",
        )


def validate_midground_water_surf(
    base: str,
    surf: Any,
    has_shore: bool,
) -> None:
    """Validate `destination.midground.water.surf`, the real-time SWE
    solver domain (viewer/LocusViewer/Rendering/SurfSimulation/). No
    referenced assets: the two textures it needs are solver output, not
    baked files. `preset` maps to `SurfSimulation.SurfConfiguration`'s
    named presets; `shoreNormalDegrees` uses the same convention as
    `waveDirectionDegrees`. Mirrors the same Swift-side
    `validate(_ water:, in:)`, including its "requires shore" constraint
    (the solver's bathymetry comes from `shore.bedHeight`)."""
    require(isinstance(surf, dict), f"{base}.midground.water.surf must be an object")
    require(
        has_shore,
        f"{base}.midground.water.surf requires midground.water.shore",
    )
    exact_keys(
        surf,
        required={"preset", "originMeters", "shoreNormalDegrees", "crossShoreMeters", "alongShoreMeters"},
        optional={"strength", "tideMeters", "cellMeters"},
        context=f"{base}.midground.water.surf",
    )
    require(
        surf["preset"] in ("calm-lake", "lake-swell", "ocean-surf"),
        f"{base}.midground.water.surf.preset must be 'calm-lake', 'lake-swell', or 'ocean-surf'",
    )

    def in_surf_range(field: str, value: Any) -> bool:
        lower, upper = MIDGROUND_SURF_RANGES[field]
        return is_finite_number(value) and lower <= value <= upper

    for field in MIDGROUND_SURF_RANGES:
        if field not in surf:
            continue
        require(
            in_surf_range(field, surf[field]),
            f"{base}.midground.water.surf.{field} must be finite and within range",
        )
    origin = surf["originMeters"]
    require(
        isinstance(origin, list) and len(origin) == 2
        and all(is_finite_number(v) and abs(v) <= 200 for v in origin),
        f"{base}.midground.water.surf.originMeters must be two finite "
        "values [x, z], each with |v| <= 200",
    )
    cross_shore = surf["crossShoreMeters"]
    along_shore = surf["alongShoreMeters"]
    require(
        is_finite_number(cross_shore) and 2.0 <= cross_shore <= 100.0,
        f"{base}.midground.water.surf.crossShoreMeters must be finite and within 2...100",
    )
    require(
        is_finite_number(along_shore) and 2.0 <= along_shore <= 100.0,
        f"{base}.midground.water.surf.alongShoreMeters must be finite and within 2...100",
    )
    cell_meters = surf.get("cellMeters", 0.25)
    require(
        is_finite_number(cell_meters) and 0.05 <= cell_meters <= 1.0,
        f"{base}.midground.water.surf.cellMeters must be finite and within 0.05...1.0",
    )
    grid_x = -(-cross_shore // cell_meters)  # ceil division, matching PackageV2Store.validate
    grid_z = -(-along_shore // cell_meters)
    require(
        4 <= grid_x <= 256 and 4 <= grid_z <= 256,
        f"{base}.midground.water.surf.cellMeters must keep the solver grid within 4...256 cells per axis",
    )


def validate_midground_water(
    base: str,
    water: Any,
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    referenced_asset,
    account_image,
) -> None:
    """Validate `destination.midground.water`, the viewer-rendered lake
    plane. Files must exist (checked by `referenced_asset`, shared with every
    other asset reference), the mask must be a genuine positive 2:1
    equirectangular image in the panorama's own projection, and the normal
    map must be a genuine decodable image. Every numeric field mirrors the
    Swift-side range exactly (see `MIDGROUND_WATER_RANGES` above)."""
    require(isinstance(water, dict), f"{base}.midground.water must be an object")
    exact_keys(
        water,
        required={"levelMeters", "mask", "normalMap"},
        optional={
            "tileMeters", "color", "normalStrength", "waveSpeed",
            "reflectionBlur", "sunGlint", "fadeStartMeters", "fadeEndMeters",
            "waveDirectionDegrees", "shore", "waves", "surf",
        },
        context=f"{base}.midground.water",
    )

    def in_range(field: str, value: Any) -> bool:
        lower, upper = MIDGROUND_WATER_RANGES[field]
        return is_finite_number(value) and lower <= value <= upper

    require(
        in_range("levelMeters", water["levelMeters"]),
        f"{base}.midground.water.levelMeters must be finite and within range",
    )
    mask_path = referenced_asset(base, water["mask"], "midground.water.mask")
    mask_dimensions = archive_image_dimensions(
        archive, infos[mask_path], mask_path, allow_exr=False)
    account_image(mask_path, mask_dimensions)
    require(
        mask_dimensions[0] == 2 * mask_dimensions[1],
        f"{mask_path} must be a positive 2:1 equirectangular mask",
    )
    _, _, _, mask_color_type = png_ihdr(archive, infos[mask_path], mask_path)
    require(mask_color_type == 0, f"{mask_path} must be a grayscale PNG")
    normal_path = referenced_asset(
        base, water["normalMap"], "midground.water.normalMap")
    account_image(
        normal_path,
        archive_image_dimensions(archive, infos[normal_path], normal_path, allow_exr=False),
    )
    _, _, _, normal_color_type = png_ihdr(archive, infos[normal_path], normal_path)
    require(normal_color_type in {2, 6}, f"{normal_path} must be an RGB PNG")

    for field in (
        "tileMeters", "normalStrength", "waveSpeed", "reflectionBlur",
        "sunGlint", "fadeStartMeters", "fadeEndMeters", "waveDirectionDegrees",
    ):
        if field not in water:
            continue
        require(
            in_range(field, water[field]),
            f"{base}.midground.water.{field} must be finite and within range",
        )
    if "fadeStartMeters" in water and "fadeEndMeters" in water:
        require(
            water["fadeStartMeters"] < water["fadeEndMeters"],
            f"{base}.midground.water.fadeEndMeters must exceed fadeStartMeters",
        )
    if "color" in water:
        color = water["color"]
        require(
            isinstance(color, list) and len(color) == 3
            and all(is_finite_number(v) and 0 <= v <= 1 for v in color),
            f"{base}.midground.water.color must be three finite values between 0 and 1",
        )
    if "waves" in water:
        validate_midground_water_waves(
            base, water["waves"], archive, infos, referenced_asset, account_image)
    if "shore" in water:
        validate_midground_water_shore(
            base, water["shore"], archive, infos, referenced_asset, account_image)
    if "surf" in water:
        validate_midground_water_surf(base, water["surf"], "shore" in water)


def validate_payload(
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    manifest: dict[str, Any],
    json_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    warnings = []
    sun_heuristic_findings = []
    contents = manifest["contents"]
    declared = {
        collection: set(contents[field])
        for collection, (field, _) in COLLECTIONS.items()
    }
    for path in infos:
        if path == "locusplace.json":
            continue
        components = path.split("/")
        require(
            len(components) >= 4 and components[0] == "catalog"
            and components[1] in COLLECTIONS
            and components[2] in declared[components[1]],
            f"unknown or undeclared payload path: {path}",
        )

    packages: dict[str, dict[str, dict[str, Any]]] = {
        collection: {} for collection in COLLECTIONS
    }
    referenced_files: set[str] = set()
    for collection, (_, filename) in COLLECTIONS.items():
        for package_id in sorted(declared[collection]):
            path = f"catalog/{collection}/{package_id}/{filename}"
            require(path in infos, f"missing Package-v2 manifest: {path}")
            value = json_cache.get(path)
            require(value is not None, f"Package-v2 manifest was not decoded: {path}")
            require(type(value.get("formatVersion")) is int and value["formatVersion"] == 2,
                    f"{path} must use Package-v2")
            require(value.get("id") == package_id, f"{path} has mismatched ID")
            require_text(value.get("title"), f"{path}.title", 10_000)
            packages[collection][package_id] = value
            referenced_files.add(path)

    def referenced_asset(base: str, raw: Any, field: str) -> str:
        path = package_asset(base, raw, infos, field)
        referenced_files.add(path)
        return path

    def title_ids(items: Any) -> set[str]:
        if not isinstance(items, list):
            return set()
        return {item["id"] for item in items
                if isinstance(item, dict) and isinstance(item.get("id"), str)}

    def validate_display_localizations(
        package: dict[str, Any], context: str, references: dict[str, set[str]]
    ) -> None:
        if "localizations" not in package:
            return
        try:
            validate_localizations(package["localizations"], references=references,
                                   context=context + ".localizations")
        except LocalizationError as error:
            raise ValidationError(str(error)) from error

    total_pixels = 0
    from water_contract import GENERATED_TEXTURE_BYTES, GLOW_TEXTURE_BYTES, MAXIMUM_TEXTURE_BYTES, OCEAN_TEXTURE_BYTES, REFLECTION_REGISTRATION_TEXTURE_BYTES, texture_bytes
    total_water_bytes = GENERATED_TEXTURE_BYTES
    glow_texture_reserved = False
    total_oceans = 0
    for collection in ('destinations', 'spaces'):
        for sound_id, sound_package in packages[collection].items():
            if sound_package.get('sound') is not None:
                from package_sound import validate_definition, MINIMUM_APP, MUSIC_MINIMUM_APP, has_music
                require(parse_version(manifest['minimumAppVersion'], 'minimumAppVersion') >= MINIMUM_APP,
                        'sound requires minimumAppVersion >= 1.1.4')
                if has_music(sound_package['sound']):
                    require(parse_version(manifest['minimumAppVersion'], 'minimumAppVersion') >= MUSIC_MINIMUM_APP,
                            'Room music requires minimumAppVersion >= 1.4.1')
                for raw in validate_definition(sound_package['sound'], require, 'view' if collection == 'destinations' else 'room'):
                    asset = referenced_asset(f'catalog/{collection}/{sound_id}', raw, 'sound.path')
                    require(0 < infos[asset].file_size <= 128 * 1024 * 1024, 'sound asset byte limit')
    for destination_id, destination in packages["destinations"].items():
        for profile_name in ("celestial", "nearOrbit"):
            profile = destination.get(profile_name)
            require(not (isinstance(profile, dict) and "oceanGlint" in profile),
                    "oceanGlint is retired and unsupported by the current Locus reader")
        base = f"catalog/destinations/{destination_id}"
        validate_display_localizations(destination, base, {
            "seatTitles": set(),
            "seatGroupTitles": set(),
            "soundTitles": title_ids((destination.get("sound") or {}).get("sources")),
            "mediaTitles": title_ids((destination.get("media") or {}).get("sources")),
            "lightTitles": title_ids((destination.get("lighting") or {}).get("luminaireGroups")),
            "animationTitles": title_ids(destination.get("ambientAnimations")),
            "videoTitles": title_ids(destination.get("videoSurfaces")),
            "particleTitles": title_ids(destination.get("particleEffects")),
        })
        for field in ("depthLayers", "splat", "audio"):
            require(
                destination.get(field) is None,
                f"unsupported public-import Destination field: {field}",
            )
        panorama = destination.get("panorama")
        require(isinstance(panorama, dict), f"{base}/destination.json.panorama is required")
        require(panorama.get("projection") == "equirectangular", "unsupported panorama projection")
        width = panorama.get("width")
        height = panorama.get("height")
        require(type(width) is int and type(height) is int and width > 0 and width == 2 * height,
                f"{base} panorama dimensions must be positive 2:1")
        initial_yaw = panorama.get("initialYawDegrees")
        require(
            initial_yaw is None or is_finite_number(initial_yaw),
            f"{base}.panorama.initialYawDegrees must be finite",
        )
        panorama_path = referenced_asset(base, panorama.get("path"), "panorama.path")
        dimensions = archive_image_dimensions(
            archive, infos[panorama_path], panorama_path, allow_exr=False)
        require(dimensions == (width, height), f"{panorama_path} dimensions do not match manifest")
        total_pixels = add_pixels(
            total_pixels, dimensions, panorama_path,
            maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS,
        )
        require(not (destination.get("clouds") is not None and destination.get("media") is not None), "clouds cannot coexist with media in v1")
        media = destination.get("media")
        if media is not None:
            from panorama_media import validate_definition, MINIMUM_APP
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                    "panorama media requires minimumAppVersion >= 1.1.2")
            paths = validate_definition(media, require)
            require(hashlib.sha256(archive.read(panorama_path)).hexdigest() == media["sourcePanoramaSHA256"],
                    "media panorama hash mismatch")
            mask_path = referenced_asset(base, media["mask"], "media.mask")
            mask_dimensions = archive_image_dimensions(archive, infos[mask_path], mask_path, allow_exr=False)
            require(mask_dimensions[0] == 2 * mask_dimensions[1], "media mask must be equirectangular 2:1")
            total_pixels = add_pixels(total_pixels, mask_dimensions, mask_path,
                                      maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS)
            for kind, raw in paths:
                asset_path = referenced_asset(base, raw, "media." + kind)
                require(0 < infos[asset_path].file_size <= 128 * 1024 * 1024, "media asset byte limit")
                with archive.open(asset_path) as source:
                    signature = source.read(12)
                if kind == "video" or raw.lower().endswith('.m4a'):
                    require(signature[4:8] == b'ftyp', "media requires MP4/M4A container")
                    if kind == "video":
                        require_media_video_pixel_format(archive, infos[asset_path], asset_path)
                else:
                    require(raw.lower().endswith('.mp3') and (signature[:3] == b'ID3' or
                            (len(signature) >= 2 and signature[0] == 255 and signature[1] & 224 == 224)),
                            "media requires MP3 or M4A audio")
        near_orbit = destination.get("nearOrbit")
        # v2 only: global fields and tile paths that are eligible
        # `gpuTextures` sources, `source -> (field, dimensions, asset)`, plus
        # the tile source paths every one of which must carry a sidecar.
        near_orbit_gpu_sources: dict[str, tuple[str, tuple[int, int], str]] = {}
        near_orbit_tile_sources: list[str] = []
        near_orbit_v2 = (isinstance(near_orbit, dict) and type(near_orbit.get("version")) is int
                         and near_orbit["version"] == 2)
        if near_orbit_v2:
            from near_orbit_profile import (ASSETS_V2, MINIMUM_APP_V2, MINIMUM_APP_SURFACE,
                                            MINIMUM_APP_OCEAN_GLINT,
                                            validate as validate_near_orbit,
                                            proof_path, validate_proof, validate_star_catalog,
                                            validate_tile_manifest, validate_surface_manifest,
                                            STAR_CATALOG_MAX_BYTES, PROOF_MAX_BYTES)
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP_V2,
                    "nearOrbit v2 requires minimumAppVersion >= 1.3.0")
            if "oceanGlint" in near_orbit:
                require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP_OCEAN_GLINT,
                        "nearOrbit v2 requires minimumAppVersion >= 1.3.2")
            try:
                validate_near_orbit(near_orbit)
            except ValueError as error:
                raise ValidationError(str(error)) from error
            if "surface" in near_orbit:
                require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP_SURFACE,
                        "nearOrbit surface requires minimumAppVersion >= 1.3.2")
            require(near_orbit["fallbackPanorama"] == panorama["path"],
                    "nearOrbit fallbackPanorama must equal panorama.path")
            require(all(destination.get(field) is None for field in (
                "celestial", "sky", "media", "midground", "water", "fireflies", "clouds", "pointLights")),
                "nearOrbit cannot coexist with other dynamic View profiles")
            require((destination.get("environment") or {}).get("sunPath") is None,
                    "nearOrbit cannot coexist with environment.sunPath")
            near_assets = {}
            near_images = {}
            image_paths = {field: near_orbit[field] for field in ASSETS_V2}
            if "oceanGlint" in near_orbit:
                image_paths["oceanGlint.mask"] = near_orbit["oceanGlint"]["mask"]
            for field, raw in image_paths.items():
                asset = referenced_asset(base, raw, "nearOrbit." + field)
                near_assets[raw] = asset
                near_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                require(near_dimensions[0] == 2 * near_dimensions[1] and near_dimensions[0] <= 8192,
                        "nearOrbit.%s image dimensions exceed profile limits" % field)
                opaque_gray = field in ("cloudTexture", "oceanGlint.mask") and opaque_grayscale_image(archive, infos[asset], asset)
                if field == "oceanGlint.mask":
                    require(opaque_gray, "oceanGlint.mask must be opaque grayscale PNG")
                near_images[field] = (near_dimensions[0], near_dimensions[1], opaque_gray)
                if field != "fallbackPanorama":
                    total_pixels = add_pixels(total_pixels, near_dimensions, asset,
                        maximum_dimension=8192, maximum_total=TOTAL_IMAGE_PIXELS)
                if field != "skyMask":
                    near_orbit_gpu_sources[raw] = (field, near_dimensions, asset)
            catalog_asset = referenced_asset(base, near_orbit['starCatalog'], 'nearOrbit.starCatalog')
            near_assets[near_orbit['starCatalog']] = catalog_asset
            require(infos[catalog_asset].file_size <= STAR_CATALOG_MAX_BYTES, 'nearOrbit star catalog exceeds byte budget')
            validate_star_catalog(json_cache.get(catalog_asset), require)
            if "tiles" in near_orbit:
                tiles = near_orbit["tiles"]
                manifest_asset = referenced_asset(base, tiles["manifest"], "nearOrbit.tiles.manifest")
                near_assets[tiles["manifest"]] = manifest_asset
                tile_assets = {}
                def read_tile(raw):
                    tile_assets[raw] = referenced_asset(base, raw, "nearOrbit.tiles")
                    return archive.read(tile_assets[raw])
                try:
                    tile_manifest = validate_tile_manifest(near_orbit, archive.read(manifest_asset), read_tile)
                except ValueError as error:
                    raise ValidationError(str(error)) from error
                for entry in tile_manifest["tiles"]:
                    raw = entry["path"]
                    asset = tile_assets[raw]
                    tile_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                    require(tile_dimensions == (tiles["tileSize"], tiles["tileSize"]),
                            "nearOrbit tile %s must be %d square" % (raw, tiles["tileSize"]))
                    total_pixels = add_pixels(total_pixels, tile_dimensions, asset,
                        maximum_dimension=tiles["tileSize"], maximum_total=TOTAL_IMAGE_PIXELS)
                    near_orbit_gpu_sources[raw] = ("tile", tile_dimensions, asset)
                    near_orbit_tile_sources.append(raw)
                if "surface" in near_orbit:
                    # Per-tile terrain slopes and water cover on the same grid:
                    # lossless 8-bit RGB PNGs, each streamed from a linear
                    # ASTC sidecar (docs/package-spec-v2.md "Surface data").
                    surface = near_orbit["surface"]
                    surface_manifest_asset = referenced_asset(base, surface["manifest"], "nearOrbit.surface.manifest")
                    near_assets[surface["manifest"]] = surface_manifest_asset
                    surface_assets = {}
                    def read_surface(raw):
                        surface_assets[raw] = referenced_asset(base, raw, "nearOrbit.surface")
                        return archive.read(surface_assets[raw])
                    try:
                        surface_manifest = validate_surface_manifest(
                            near_orbit, archive.read(surface_manifest_asset), read_surface,
                            [entry["path"] for entry in tile_manifest["tiles"]])
                    except ValueError as error:
                        raise ValidationError(str(error)) from error
                    for entry in surface_manifest["tiles"]:
                        raw = entry["path"]
                        asset = surface_assets[raw]
                        surface_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                        require(surface_dimensions == (surface["tileSize"], surface["tileSize"]),
                                "nearOrbit surface tile %s must be %d square" % (raw, surface["tileSize"]))
                        _, _, bit_depth, color_type = png_ihdr(archive, infos[asset], asset)
                        require(bit_depth == 8 and color_type == 2,
                                "nearOrbit surface tile %s must be an 8-bit RGB PNG" % raw)
                        total_pixels = add_pixels(total_pixels, surface_dimensions, asset,
                            maximum_dimension=surface["tileSize"], maximum_total=TOTAL_IMAGE_PIXELS)
                        near_orbit_gpu_sources[raw] = ("surface", surface_dimensions, asset)
                        near_orbit_tile_sources.append(raw)
            proof_asset = referenced_asset(base, proof_path(near_orbit), "nearOrbit fallback proof")
            require(infos[proof_asset].file_size <= PROOF_MAX_BYTES, 'nearOrbit fallback proof exceeds byte budget')
            try:
                validate_proof(near_orbit, json_cache.get(proof_asset),
                               lambda raw: archive.read(near_assets[raw]))
            except ValueError as error:
                raise ValidationError(str(error)) from error
        elif near_orbit is not None:
            from near_orbit_profile import (ASSETS, MINIMUM_APP, validate as validate_near_orbit,
                                            proof_path, validate_proof, validate_star_catalog,
                                            validate_texture_budget, STAR_CATALOG_MAX_BYTES, PROOF_MAX_BYTES)
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                    "nearOrbit requires minimumAppVersion >= 1.3.0")
            try:
                validate_near_orbit(near_orbit)
            except ValueError as error:
                raise ValidationError(str(error)) from error
            require(near_orbit["fallbackPanorama"] == panorama["path"],
                    "nearOrbit fallbackPanorama must equal panorama.path")
            require(all(destination.get(field) is None for field in (
                "celestial", "sky", "media", "midground", "water", "fireflies", "clouds", "pointLights")),
                "nearOrbit cannot coexist with other dynamic View profiles")
            require((destination.get("environment") or {}).get("sunPath") is None,
                    "nearOrbit cannot coexist with environment.sunPath")
            near_assets = {}
            near_images = {}
            for field in ASSETS:
                asset = referenced_asset(base, near_orbit[field], "nearOrbit." + field)
                near_assets[near_orbit[field]] = asset
                near_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                square = field in ("regionTexture", "regionMask")
                maximum = 2048 if square else (8192 if field == "galaxyTexture" else 4096)
                require(near_dimensions[0] == near_dimensions[1] * (1 if square else 2)
                        and near_dimensions[0] <= maximum,
                        "nearOrbit.%s image dimensions exceed profile limits" % field)
                if field == "regionTexture":
                    require(near_dimensions == (1024, 1024), "nearOrbit.regionTexture must be 1024 square for the native LOD pool")
                opaque_gray = field in ('cloudTexture', 'regionMask') and opaque_grayscale_image(archive, infos[asset], asset)
                near_images[field] = (near_dimensions[0], near_dimensions[1], opaque_gray)
                if field != "fallbackPanorama":
                    total_pixels = add_pixels(total_pixels, near_dimensions, asset,
                        maximum_dimension=maximum, maximum_total=TOTAL_IMAGE_PIXELS)
            validate_texture_budget(near_images, require)
            catalog_asset = referenced_asset(base, near_orbit['starCatalog'], 'nearOrbit.starCatalog')
            near_assets[near_orbit['starCatalog']] = catalog_asset
            require(infos[catalog_asset].file_size <= STAR_CATALOG_MAX_BYTES, 'nearOrbit star catalog exceeds byte budget')
            validate_star_catalog(json_cache.get(catalog_asset), require)
            proof_asset = referenced_asset(base, proof_path(near_orbit), "nearOrbit fallback proof")
            require(infos[proof_asset].file_size <= PROOF_MAX_BYTES, 'nearOrbit fallback proof exceeds byte budget')
            try:
                validate_proof(near_orbit, json_cache.get(proof_asset),
                               lambda raw: archive.read(near_assets[raw]))
            except ValueError as error:
                raise ValidationError(str(error)) from error
        celestial = destination.get("celestial")
        # Populated only for the four celestial fields that are eligible
        # `gpuTextures` (v2) sources: `sunDisc.skyMask` is intentionally
        # excluded (docs/package-spec-v2.md "View GPU texture sidecar v2").
        celestial_gpu_texture_sources: dict[str, tuple[str, tuple[int, int], str]] = {}
        if celestial is not None:
            from celestial_view import validate_definition as validate_celestial, minimum_app as celestial_minimum_app
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= celestial_minimum_app(celestial),
                    "celestial requires minimumAppVersion compatible with profile version")
            require(destination.get("media") is None and destination.get("midground") is None,
                    "celestial cannot coexist with media or midground")
            if destination.get("sky") is not None:
                require(parse_version(manifest["minimumAppVersion"],"minimumAppVersion") >= (1,3,0),"celestial sky requires minimumAppVersion >=1.3.0")
                s=destination["sky"]
                require(isinstance(s,dict) and s.get("stars") is not None and s.get("aurora") is None and s.get("moon") is None,"celestial sky requires stars and excludes aurora/Moon")
            for field, raw in validate_celestial(celestial, require).items():
                asset = referenced_asset(base, raw, "celestial." + field)
                celestial_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                maximum = 16384 if field == "backgroundPanorama" else 8192
                require(celestial_dimensions[0] == 2 * celestial_dimensions[1] and celestial_dimensions[0] <= maximum,
                        "celestial.%s must be 2:1 and at most %s pixels wide" % (field, maximum))
                total_pixels = add_pixels(total_pixels, celestial_dimensions, asset,
                    maximum_dimension=maximum, maximum_total=TOTAL_IMAGE_PIXELS)
                if field in ("sunDisc.skyMask", "oceanGlint.mask"):
                    _, _, _, color_type = png_ihdr(archive, infos[asset], asset)
                    require(color_type == 0, "celestial.%s must be a grayscale PNG" % field)
                    if field == "oceanGlint.mask":
                        require(opaque_grayscale_image(archive, infos[asset], asset), "oceanGlint.mask must be opaque")
                if field in ("backgroundPanorama", "dayTexture", "nightTexture", "cloudTexture", "oceanGlint.mask"):
                    celestial_gpu_texture_sources[raw] = (field, celestial_dimensions, asset)
            if "advection" in celestial:
                from celestial_advection import validate_flow_header
                advection = celestial["advection"]
                asset = referenced_asset(base, advection["flowTexture"], "celestial.advection.flowTexture")
                validate_flow_header(advection, *png_ihdr(archive, infos[asset], asset), require)
                flow_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                total_pixels = add_pixels(total_pixels, flow_dimensions, asset,
                    maximum_dimension=(16 + 1) * 512, maximum_total=TOTAL_IMAGE_PIXELS)
            if "rings" in celestial:
                # A 1-pixel radial profile, not a 2:1 surface image or a
                # gpuTextures source; it still counts toward the image budget.
                from celestial_rings import PROFILE_WIDTH, validate_profile_header
                asset = referenced_asset(base, celestial["rings"]["profileTexture"], "celestial.rings.profileTexture")
                validate_profile_header(*png_ihdr(archive, infos[asset], asset), require)
                profile_dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                total_pixels = add_pixels(total_pixels, profile_dimensions, asset,
                    maximum_dimension=PROFILE_WIDTH[1], maximum_total=TOTAL_IMAGE_PIXELS)
        black_hole = destination.get("blackHole")
        if black_hole is not None:
            import black_hole_view
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= black_hole_view.MINIMUM_APP,
                    "blackHole requires minimumAppVersion >= 1.3.4")
            require(all(destination.get(field) is None for field in black_hole_view.EXCLUDED),
                    "blackHole cannot coexist with other dynamic View profiles")
            require((destination.get("environment") or {}).get("sunPath") is None,
                    "blackHole cannot coexist with environment.sunPath")
            for field, raw in black_hole_view.validate_definition(black_hole, require).items():
                asset = referenced_asset(base, raw, "blackHole." + field)
                dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                png_format = None
                if asset.lower().endswith(".png"):
                    _, _, bit_depth, color_type = png_ihdr(archive, infos[asset], asset)
                    png_format = (bit_depth, color_type)
                require(field == "skyTexture" or png_format is not None, "blackHole.%s must be a PNG" % field)
                black_hole_view.validate_image(field, dimensions[0], dimensions[1], png_format, require)
                total_pixels = add_pixels(total_pixels, dimensions, asset,
                    maximum_dimension=black_hole_view.SKY_MAX_WIDTH, maximum_total=TOTAL_IMAGE_PIXELS)
        if "fireflies" in destination:
            from fireflies_contract import MINIMUM_APP, validate_definition as validate_fireflies
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                    "fireflies requires minimumAppVersion >= 1.3.0")
            require(destination.get("celestial") is None,
                    "fireflies cannot coexist with celestial")
            validate_fireflies(destination["fireflies"], require, field=base + ".fireflies")
        gpu_texture = destination.get("gpuTexture")
        if gpu_texture is not None:
            from gpu_texture_sidecar import MINIMUM_APP as GPU_TEXTURE_MINIMUM_APP
            from gpu_texture_sidecar import validate_definition as validate_gpu_texture
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= GPU_TEXTURE_MINIMUM_APP,
                "gpuTexture requires minimumAppVersion >= 1.2.3",
            )
            ktx_relative = validate_gpu_texture(gpu_texture, require)
            ktx_path = referenced_asset(base, ktx_relative, "gpuTexture.path")
            require(ktx_path.lower().endswith(".ktx"), f"{ktx_path} must be a .ktx file")
            from ktx1 import (
                GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR,
                Ktx1Error,
                astc_6x6_expected_byte_range,
                parse_header,
            )
            ktx_bytes = archive.read(ktx_path)
            try:
                header = parse_header(ktx_bytes)
            except Ktx1Error as error:
                raise ValidationError(f"{ktx_path}: invalid KTX1 header: {error}")
            require(
                header.gl_internal_format == GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR,
                f"{ktx_path} must be ASTC 6x6 sRGB (glInternalFormat 0x93d4)",
            )
            require(
                (header.pixel_width, header.pixel_height)
                == (gpu_texture["width"], gpu_texture["height"]) == dimensions,
                f"{ktx_path} dimensions do not match gpuTexture manifest and panorama",
            )
            require(
                header.number_of_mipmap_levels == gpu_texture["mipmapLevels"],
                f"{ktx_path} mip level count does not match gpuTexture manifest",
            )
            lower, upper = astc_6x6_expected_byte_range(
                gpu_texture["width"], gpu_texture["height"])
            require(
                lower <= infos[ktx_path].file_size <= upper,
                f"{ktx_path} size is not plausible for ASTC 6x6 sRGB at its declared dimensions",
            )
            require(
                hashlib.sha256(archive.read(panorama_path)).hexdigest()
                == gpu_texture["sourcePanoramaSHA256"],
                "gpuTexture source panorama hash mismatch",
            )
        gpu_textures = destination.get("gpuTextures")
        gpu_sidecar_sizes: dict[str, int] = {}
        if gpu_textures is not None:
            require(gpu_texture is None,
                    "destination cannot declare both gpuTexture and gpuTextures")
            from gpu_texture_sidecar import (
                FORMAT as GPU_TEXTURE_FORMAT_SRGB,
                FORMAT_LINEAR as GPU_TEXTURE_FORMAT_LINEAR,
                MINIMUM_APP_V2 as GPU_TEXTURE_V2_MINIMUM_APP,
                validate_definition_v2 as validate_gpu_textures,
            )
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= GPU_TEXTURE_V2_MINIMUM_APP,
                "gpuTextures requires minimumAppVersion >= 1.3.0",
            )
            from ktx1 import (
                GL_COMPRESSED_RGBA_ASTC_6x6_KHR,
                GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR,
                Ktx1Error,
                astc_6x6_expected_byte_range,
                parse_header,
            )
            # Every source a gpuTextures entry may legally name, with the
            # format it must use and its already-validated real dimensions:
            # the sky panorama (always sRGB) plus any eligible celestial
            # texture (linear only for cloudTexture, matching the `.raw`
            # RealityKit semantic it is sampled with).
            allowed_sources = {panorama["path"]: (GPU_TEXTURE_FORMAT_SRGB, dimensions, panorama_path)}
            for source_path, (field, source_dimensions, source_asset_path) in celestial_gpu_texture_sources.items():
                fmt = GPU_TEXTURE_FORMAT_LINEAR if field in ("cloudTexture", "oceanGlint.mask") else GPU_TEXTURE_FORMAT_SRGB
                allowed_sources[source_path] = (fmt, source_dimensions, source_asset_path)
            for source_path, (field, source_dimensions, source_asset_path) in near_orbit_gpu_sources.items():
                # Surface tiles and the glint mask are raw data, like clouds.
                fmt = (GPU_TEXTURE_FORMAT_LINEAR if field in ("cloudTexture", "surface", "oceanGlint.mask")
                       else GPU_TEXTURE_FORMAT_SRGB)
                allowed_sources[source_path] = (fmt, source_dimensions, source_asset_path)
            entries = validate_gpu_textures(gpu_textures, require)
            for index, entry in enumerate(entries):
                source = entry["source"]
                require(source in allowed_sources,
                        f"gpuTextures[{index}].source is not one of this View's eligible images")
                expected_format, expected_dimensions, source_asset = allowed_sources[source]
                require(entry["format"] == expected_format,
                        f"gpuTextures[{index}] must use format {expected_format} for source {source}")
                ktx_path = referenced_asset(base, entry["path"], f"gpuTextures[{index}].path")
                require(ktx_path.lower().endswith(".ktx"), f"{ktx_path} must be a .ktx file")
                gpu_sidecar_sizes[source] = infos[ktx_path].file_size
                ktx_bytes = archive.read(ktx_path)
                try:
                    header = parse_header(ktx_bytes)
                except Ktx1Error as error:
                    raise ValidationError(f"{ktx_path}: invalid KTX1 header: {error}")
                expected_internal_format = (
                    GL_COMPRESSED_RGBA_ASTC_6x6_KHR
                    if expected_format == GPU_TEXTURE_FORMAT_LINEAR
                    else GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR
                )
                require(
                    header.gl_internal_format == expected_internal_format,
                    f"{ktx_path} must be ASTC 6x6 {'linear' if expected_format == GPU_TEXTURE_FORMAT_LINEAR else 'sRGB'} "
                    f"(glInternalFormat 0x{expected_internal_format:x})",
                )
                require(
                    (header.pixel_width, header.pixel_height)
                    == (entry["width"], entry["height"]) == expected_dimensions,
                    f"{ktx_path} dimensions do not match gpuTextures manifest and its source image",
                )
                require(
                    header.number_of_mipmap_levels == entry["mipmapLevels"],
                    f"{ktx_path} mip level count does not match gpuTextures manifest",
                )
                lower, upper = astc_6x6_expected_byte_range(entry["width"], entry["height"])
                require(
                    lower <= infos[ktx_path].file_size <= upper,
                    f"{ktx_path} size is not plausible for its declared ASTC 6x6 format and dimensions",
                )
                require(
                    hashlib.sha256(archive.read(source_asset)).hexdigest() == entry["sourceSHA256"],
                    f"gpuTextures[{index}] source hash mismatch",
                )
        if near_orbit_v2:
            # Every streamed tile must ship its ASTC sidecar; globals count at
            # their sidecar size when they have one (docs/package-spec-v2.md
            # "View near orbit v2").
            from near_orbit_profile import validate_texture_budget_v2
            for raw in near_orbit_tile_sources:
                require(raw in gpu_sidecar_sizes,
                        "nearOrbit tile %s has no gpuTextures sidecar" % raw)
            validate_texture_budget_v2(
                near_images,
                {field: gpu_sidecar_sizes[raw] for field, raw in image_paths.items()
                 if raw in gpu_sidecar_sizes},
                require)
        point_lights = destination.get("pointLights")
        if point_lights is not None:
            from point_lights import (MAXIMUM_BYTES as POINT_LIGHTS_MAXIMUM_BYTES,
                                      MINIMUM_APP as POINT_LIGHTS_MINIMUM_APP,
                                      validate_definition as validate_point_lights,
                                      validate_table as validate_point_lights_table)
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= POINT_LIGHTS_MINIMUM_APP,
                "pointLights requires minimumAppVersion >= 1.2.5",
            )
            table_relative = validate_point_lights(point_lights, require)
            table_path = referenced_asset(base, table_relative, "pointLights.table")
            require(infos[table_path].file_size <= POINT_LIGHTS_MAXIMUM_BYTES,
                    "point-lights table byte limit")
            validate_point_lights_table(
                decoded_member(archive, infos[table_path], table_path), require)
        provenance_path = referenced_asset(
            base, destination.get("provenance"), "provenance"
        )
        require(infos[provenance_path].file_size <= PROVENANCE_BYTES,
                f"provenance budget exceeded: {provenance_path}")
        provenance_value = decoded_member(archive, infos[provenance_path], provenance_path)
        validate_provenance(provenance_value, provenance_path)
        provenance_detail = destination.get("provenanceDetail")
        if provenance_detail is not None:
            destination_manifest_path = f"{base}/destination.json"
            require(
                isinstance(provenance_detail, dict),
                f"{destination_manifest_path}.provenanceDetail must be an object",
            )
            validate_provenance_detail(
                provenance_detail, media, provenance_value,
                f"{destination_manifest_path}.provenanceDetail",
                sound=destination.get('sound'),
            )
        for field in ("sourceImage", "thumbnail"):
            if field in destination:
                asset = referenced_asset(base, destination[field], field)
                dimensions = archive_image_dimensions(
                    archive, infos[asset], asset, allow_exr=False)
                total_pixels = add_pixels(
                    total_pixels, dimensions, asset,
                    maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS,
                )
        environment = destination.get("environment")
        if environment is not None:
            require(isinstance(environment, dict), f"{base}.environment must be an object")
            for retired in ("visibleSkyHDR", "hdrManifest"):
                require(
                    retired not in environment,
                    f"unsupported V1 View environment field: {retired}",
                )
            for field in (
                "skyGainEV", "exposureEV", "horizonPitchDegrees"
            ):
                value = environment.get(field)
                require(
                    value is None or is_finite_number(value),
                    f"environment.{field} must be finite",
                )
            if "colorGrade" in environment:
                color_grade = environment["colorGrade"]
                require(
                    isinstance(color_grade, dict),
                    "environment.colorGrade must be an object",
                )
                exact_keys(
                    color_grade,
                    required={"contrast", "saturation"},
                    context="environment.colorGrade",
                )
                for field, lower, upper in (
                    ("contrast", 0.5, 2.0),
                    ("saturation", 0.0, 2.0),
                ):
                    value = color_grade[field]
                    require(
                        is_finite_number(value)
                        and lower <= value <= upper,
                        f"environment.colorGrade.{field} must be between "
                        f"{lower:g} and {upper:g}",
                    )
            if "sunPath" in environment:
                from sun_path_contract import MINIMUM_APP, validate_definition as validate_sun_path
                require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                        "sunPath requires minimumAppVersion >= 1.3.0")
                require("directSun" not in environment, "sunPath cannot coexist with directSun")
                require(destination.get("celestial") is None, "sunPath cannot coexist with celestial")
                detail = destination.get("provenanceDetail") or {}
                require(any(c.get("component") == "sun-free-sky" and isinstance(c.get("notes"), str) and c["notes"].strip()
                            for c in detail.get("components", [])), "sunPath requires a sun-free-sky tool/run attestation")
                midground = destination.get("midground")
                legacy_water = midground.get("water") if isinstance(midground, dict) else None
                shore = legacy_water.get("shore") if isinstance(legacy_water, dict) else None
                require(not (isinstance(shore, dict) and "sunVisibility" in shore),
                        "sunPath cannot coexist with static sunVisibility")
                water = destination.get("water")
                regions = water.get("regions") if isinstance(water, dict) else None
                require(not (isinstance(regions, list) and any(isinstance(r, dict) and isinstance(r.get("bed"), dict) and "sunVisibility" in r["bed"] for r in regions)),
                        "sunPath cannot coexist with static sunVisibility")
                def sun_asset(raw, name, grayscale=False):
                    nonlocal total_pixels
                    path = referenced_asset(base, raw, name)
                    dimensions = archive_image_dimensions(archive, infos[path], path, allow_exr=False)
                    total_pixels = add_pixels(total_pixels, dimensions, path, maximum_dimension=4096, maximum_total=TOTAL_IMAGE_PIXELS)
                    depth, color = light_layer_png_info(archive.read(path), path)[2:]
                    require(dimensions[0] == 2 * dimensions[1] and depth == 8 and color == 0,
                            name + " must be an 8-bit grayscale 2:1 PNG")
                validate_sun_path(environment["sunPath"], require, sun_asset)
            if "directSun" in environment:
                direct_sun = environment["directSun"]
                require(
                    isinstance(direct_sun, dict),
                    "environment.directSun must be an object",
                )
                exact_keys(
                    direct_sun,
                    required={"enabled", "illuminanceLux"},
                    optional={"azimuthDegrees", "elevationDegrees"},
                    context="environment.directSun",
                )
                require(
                    type(direct_sun["enabled"]) is bool,
                    "environment.directSun.enabled must be a boolean",
                )
                illuminance = direct_sun["illuminanceLux"]
                require(
                    is_finite_number(illuminance) and illuminance >= 0,
                    "environment.directSun.illuminanceLux must be finite and non-negative",
                )
                for field in ("azimuthDegrees", "elevationDegrees"):
                    value = direct_sun.get(field)
                    require(
                        value is None or is_finite_number(value),
                        f"environment.directSun.{field} must be finite",
                    )
                require(
                    not direct_sun["enabled"]
                    or (
                        direct_sun.get("azimuthDegrees") is not None
                        and direct_sun.get("elevationDegrees") is not None
                    ),
                    "environment.directSun requires azimuthDegrees and elevationDegrees when enabled",
                )
            if "imageBasedLight" in environment:
                asset = referenced_asset(
                    base,
                    environment["imageBasedLight"],
                    "environment.imageBasedLight",
                )
                require(
                    asset != panorama_path,
                    "environment.imageBasedLight must not reuse the visible panorama",
                )
                dimensions = archive_image_dimensions(
                    archive, infos[asset], asset, allow_exr=False)
                total_pixels = add_pixels(
                    total_pixels, dimensions, asset,
                    maximum_dimension=IMAGE_DIMENSION,
                    maximum_total=TOTAL_IMAGE_PIXELS,
                )
                require(
                    dimensions[0] == 2 * dimensions[1],
                    f"{asset} dimensions must be positive 2:1",
                )
            if "sunPath" in environment:
                # Tool-side warning only. The publisher turns these findings
                # into a failure unless a reviewed reason is explicitly given.
                from dataclasses import asdict
                from sun_free_sky_check import check as check_sun_free
                import io
                checked = [panorama_path]
                if environment.get("imageBasedLight"):
                    checked.append(referenced_asset(base, environment["imageBasedLight"], "environment.imageBasedLight"))
                for checked_path in checked:
                    hits = check_sun_free(io.BytesIO(archive.read(checked_path)), environment.get("horizonPitchDegrees") or 0)
                    if hits:
                        sun_heuristic_findings.append({"path": checked_path, "findings": [asdict(hit) for hit in hits]})
                        warnings.append(checked_path + ": sun-free sky heuristic found %d likely sun disc(s)" % len(hits))
        for index, depth in enumerate(destination.get("depthLayers") or []):
            require(isinstance(depth, dict), f"{base}.depthLayers[{index}] must be an object")
            referenced_asset(base, depth.get("path"), f"depthLayers[{index}].path")
        midground = destination.get("midground")
        if midground is not None:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "midground requires minimumAppVersion >= 1.2.1",
            )
            require(isinstance(midground, dict), f"{base}.midground must be an object")
            path = midground.get("path")
            water = midground.get("water")
            require(
                path is not None or water is not None,
                f"{base}.midground must declare path or water",
            )
            if path is not None:
                midground_asset = referenced_asset(base, path, "midground.path")
                require(
                    midground_asset.lower().endswith(".usdz"),
                    f"{base}.midground.path must be a USDZ",
                )
                validate_usdz(archive, infos[midground_asset], midground_asset)
            if "terrainEntities" in midground:
                names = midground["terrainEntities"]
                require(
                    path is not None and isinstance(names, list)
                    and all(isinstance(name, str) and name for name in names)
                    and len(set(names)) == len(names),
                    f"{base}.midground.terrainEntities must be a list of "
                    "unique, non-empty names, and only valid alongside path",
                )
            if "windSway" in midground:
                wind_sway = midground["windSway"]
                require(
                    path is not None and isinstance(wind_sway, dict),
                    f"{base}.midground.windSway is only valid alongside path",
                )
                exact_keys(
                    wind_sway,
                    required={"entities", "amplitudeDegrees", "periodSeconds"},
                    optional={"directionDegrees", "wavelengthMeters"},
                    context=f"{base}.midground.windSway",
                )
                entities = wind_sway["entities"]
                require(
                    isinstance(entities, list) and len(entities) > 0
                    and all(isinstance(name, str) and name for name in entities)
                    and len(set(entities)) == len(entities),
                    f"{base}.midground.windSway.entities must be a list of "
                    "unique, non-empty names, and only valid alongside path",
                )

                def wind_sway_in_range(field: str, value: Any) -> bool:
                    lower, upper = MIDGROUND_WIND_SWAY_RANGES[field]
                    return is_finite_number(value) and lower <= value <= upper

                require(
                    wind_sway_in_range("amplitudeDegrees", wind_sway["amplitudeDegrees"]),
                    f"{base}.midground.windSway.amplitudeDegrees must be finite and within range",
                )
                require(
                    wind_sway_in_range("periodSeconds", wind_sway["periodSeconds"]),
                    f"{base}.midground.windSway.periodSeconds must be finite and within range",
                )
                if "directionDegrees" in wind_sway:
                    require(
                        wind_sway_in_range(
                            "directionDegrees", wind_sway["directionDegrees"]),
                        f"{base}.midground.windSway.directionDegrees must be finite and within range",
                    )
                if "wavelengthMeters" in wind_sway:
                    require(
                        wind_sway_in_range(
                            "wavelengthMeters", wind_sway["wavelengthMeters"]),
                        f"{base}.midground.windSway.wavelengthMeters must be finite and within range",
                    )
                    require(
                        parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                        >= MIDGROUND_WIND_SWAY_WAVE_MINIMUM_APP,
                        "midground.windSway.wavelengthMeters requires minimumAppVersion >= 1.3.4",
                    )
            if water is not None:
                def account_midground_image(path: str, dimensions: tuple[int, int]) -> None:
                    nonlocal total_pixels
                    total_pixels = add_pixels(
                        total_pixels, dimensions, path,
                        maximum_dimension=IMAGE_DIMENSION,
                        maximum_total=TOTAL_IMAGE_PIXELS,
                    )
                validate_midground_water(
                    base, water, archive, infos, referenced_asset,
                    account_midground_image)
        if "water" in destination:
            from water_contract import minimum_app, validate_definition
            require(not (destination.get('midground') or {}).get('water'),
                    'water cannot coexist with midground.water')
            require(destination.get('celestial') is None, 'water cannot coexist with celestial')
            def water_asset(raw, name, png=False, panorama=False, grayscale=False, rgba=False, reflection_registration=False, raw_gray=False, source_only=False):
                nonlocal total_water_bytes
                asset = referenced_asset(base, raw, name)
                if png:
                    require(asset.lower().endswith('.png'), name + ' must be a PNG')
                    dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                    nonlocal total_pixels
                    total_pixels = add_pixels(total_pixels, dimensions, asset, maximum_dimension=4096, maximum_total=TOTAL_IMAGE_PIXELS)
                    if panorama: require(dimensions[0] == 2 * dimensions[1], name + ' must be 2:1')
                    with archive.open(asset) as source:
                        data = source.read()
                    _, _, bit_depth, color_type = light_layer_png_info(data, asset)
                    require(bit_depth == 8 and color_type in (0, 2, 4, 6), name + ' must be an 8-bit non-palette PNG')
                    total_water_bytes += (0 if source_only else dimensions[0] * dimensions[1] if raw_gray or reflection_registration == "mask-layered-v1"
                                          else texture_bytes(*dimensions, mipmaps=name.endswith(('.normalMap', '.albedo', '.landTexture', '.reflectionPanorama'))))
                    require(total_water_bytes <= MAXIMUM_TEXTURE_BYTES, 'water textures exceed the 64 MiB resident budget')
                    if grayscale:
                        require(color_type == 0, name + ' must be a grayscale PNG')
                    if reflection_registration:
                        try:
                            if reflection_registration == "mask-layered-v1":
                                from water_layered_reflection_mask import validate_mask_bytes
                                total_water_bytes += validate_mask_bytes(data, name)["textureBytes"]
                                require(total_water_bytes <= MAXIMUM_TEXTURE_BYTES, "water textures exceed the 64 MiB resident budget")
                            else:
                                from water_reflection_mask import validate_mask_bytes
                                validate_mask_bytes(data, name)
                        except ValueError as error:
                            require(False, str(error))
                    if rgba:
                        require(color_type == 6 and data[26:29] == bytes(3), name + ' must be an 8-bit non-interlaced RGBA PNG')
            validate_definition(destination['water'], owner='view', require=require, asset=water_asset, field=base+'.water')
            required_water_minimum = minimum_app(destination['water'])
            for region in destination['water']['regions']:
                calibration = region.get('contactCalibration')
                if calibration is not None:
                    require(not any(destination.get(key) is not None for key in
                                    ('media', 'clouds', 'sky', 'midground', 'celestial', 'nearOrbit')),
                            'water.contactCalibration requires a photographic View without other geometry layers')
                    mask_path = referenced_asset(base, region['blend']['panoramaMask'], 'contactCalibration.sourceMask')
                    source_path=referenced_asset(base,calibration['sourcePanorama'],'contactCalibration.sourcePanorama')
                    require(hashlib.sha256(archive.read(source_path)).hexdigest()==calibration['sourcePanoramaSHA256'],'contact source panorama hash mismatch')
                    require(hashlib.sha256(archive.read(mask_path)).hexdigest()==calibration['sourceMaskSHA256'],'contact source mask hash mismatch')
                    require((destination.get('environment') or {}).get('horizonPitchDegrees',0)==0,'contact proxy requires rectified zero-pitch source')
                    from water_contact_proxy import validate_assets
                    def contact_bytes(key):return archive.read(referenced_asset(base,calibration[key],'contactCalibration.'+key))
                    try:
                        validate_assets(archive.read(source_path),archive.read(panorama_path),archive.read(mask_path),
                            contact_bytes('removalMask'),contact_bytes('waterCoverage'),json.loads(contact_bytes('landMesh')),
                            region['sizeMeters'][0]/2-region.get('surface',{}).get('waveHeightMeters',.08),calibration['referenceEyeHeightMeters'],
                            calibration.get('sourceProjection'),calibration['referenceSkyCenterMeters'])
                    except ValueError as error:require(False,str(error))
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= required_water_minimum,
                    "water requires minimumAppVersion >= " + ".".join(map(str, required_water_minimum)))
            total_water_bytes += REFLECTION_REGISTRATION_TEXTURE_BYTES * sum(
                region.get('contactCalibration') is None and (region.get('reflectionRegistration') or {}).get('model') == 'mask-image-v1'
                for region in destination['water']['regions'])
            if not glow_texture_reserved and any('glow' in r for r in destination['water']['regions']):
                total_water_bytes += GLOW_TEXTURE_BYTES
                glow_texture_reserved = True
            total_oceans += sum(region.get('surface', {}).get('motion', 'ocean') != 'still'
                                for region in destination['water']['regions'])
            require(total_oceans <= 1, 'water package has more than one ocean')
            total_water_bytes += OCEAN_TEXTURE_BYTES * sum(region.get('surface', {}).get('motion', 'ocean') != 'still'
                                                        for region in destination['water']['regions'])
            require(total_water_bytes <= MAXIMUM_TEXTURE_BYTES, 'water textures exceed the 64 MiB resident budget')
        if "clouds" in destination:
            from clouds_contract import MINIMUM_APP, validate_definition as validate_clouds
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                    "clouds requires minimumAppVersion >= 1.3.0")
            require(destination.get("media") is None, "clouds cannot coexist with media in v1")
            require(destination.get("celestial") is None, "clouds cannot coexist with celestial")
            def cloud_asset(raw, name, grayscale=False):
                nonlocal total_pixels
                path = referenced_asset(base, raw, name)
                dimensions = archive_image_dimensions(archive, infos[path], path, allow_exr=False)
                total_pixels = add_pixels(total_pixels, dimensions, path, maximum_dimension=4096, maximum_total=TOTAL_IMAGE_PIXELS)
                require(dimensions[0] == dimensions[1] * 2, name + " must be 2:1")
                depth, color_type = light_layer_png_info(archive.read(path), path)[2:]
                require(depth == 8 and color_type == (0 if grayscale else 2),
                        name + (" must be an 8-bit grayscale PNG" if grayscale else " must be an 8-bit RGB PNG"))
                return dimensions
            validate_clouds(destination["clouds"], require, cloud_asset, field=base + ".clouds")
            horizon = destination["clouds"].get("horizonDegrees", (destination.get("environment") or {}).get("horizonPitchDegrees", 0))
            require(is_finite_number(horizon) and -10 <= horizon <= 10, "clouds.horizonDegrees must be within -10...10")
        sky = destination.get("sky")
        if sky is not None:
            # docs/package-spec-v2.md "`sky`". Shape and ranges live in
            # procedural_sky.py (mirroring the viewer's
            # `PackageV2Store.validate(_ sky:)`); the mask is checked here
            # against the open archive like `midground.water.mask`.
            from procedural_sky import MINIMUM_APP as SKY_MINIMUM_APP
            from procedural_sky import validate_definition as validate_sky
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= SKY_MINIMUM_APP,
                "sky requires minimumAppVersion >= 1.2.4",
            )
            sky_mask_relative = validate_sky(sky, require)
            sky_mask_path = referenced_asset(base, sky_mask_relative, "sky.mask")
            sky_mask_dimensions = archive_image_dimensions(
                archive, infos[sky_mask_path], sky_mask_path, allow_exr=False)
            total_pixels = add_pixels(
                total_pixels, sky_mask_dimensions, sky_mask_path,
                maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS,
            )
            require(
                sky_mask_dimensions[0] == 2 * sky_mask_dimensions[1],
                f"{sky_mask_path} must be a positive 2:1 equirectangular mask",
            )
            _, _, _, sky_mask_color_type = png_ihdr(
                archive, infos[sky_mask_path], sky_mask_path)
            require(sky_mask_color_type == 0, f"{sky_mask_path} must be a grayscale PNG")
            from procedural_sky import milky_way_map_path, MILKY_WAY_MAP_MINIMUM_APP
            galaxy_relative = milky_way_map_path(sky)
            if galaxy_relative is not None:
                require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MILKY_WAY_MAP_MINIMUM_APP,
                        "milkyWay.diffuseMap requires minimumAppVersion >= 1.3.0")
                galaxy_path = referenced_asset(base, galaxy_relative, "sky.stars.milkyWay.diffuseMap")
                dimensions = archive_image_dimensions(archive, infos[galaxy_path], galaxy_path, allow_exr=False)
                require(64 <= dimensions[0] <= 8192 and dimensions[0] == 2 * dimensions[1],
                        "milkyWay.diffuseMap must be a 2:1 PNG, width 64...8192")
                total_pixels = add_pixels(total_pixels, dimensions, galaxy_path,
                    maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS)
                _, _, depth, color = png_ihdr(archive, infos[galaxy_path], galaxy_path)
                require(depth == 8 and color in (2, 6), "milkyWay.diffuseMap must be an 8-bit RGB/RGBA sRGB PNG")
            # `sky.stars.catalog`: a star catalog file in the same package
            # (docs/package-spec-v2.md "Star catalog file"), validated as the
            # viewer's `ProceduralSkyStarCatalogFile` does. Every `.json`
            # member was already parsed into `json_cache` (duplicate keys and
            # NaN refused, 1 MB budget); a catalog under another suffix is
            # read here under the same 1 MB cap.
            from procedural_sky import parse_star_catalog, real_sky_declared, star_catalog_path
            from procedural_sky import validate_star_catalog
            sky_catalog_relative = star_catalog_path(sky)
            if sky_catalog_relative is not None:
                sky_catalog_path = referenced_asset(base, sky_catalog_relative, "sky.stars.catalog")
                sky_catalog = json_cache.get(sky_catalog_path)
                if sky_catalog is None:
                    sky_catalog_info = infos[sky_catalog_path]
                    require(sky_catalog_info.file_size <= STAR_CATALOG_BYTES,
                            f"{sky_catalog_path} exceeds the star catalog byte budget")
                    sky_catalog = parse_star_catalog(archive.read(sky_catalog_path), require)
                validate_star_catalog(sky_catalog, require, real_sky_declared(sky))
        if destination.get("clouds") is not None and sky is not None:
            from clouds_contract import mask_overlap_fraction
            mask_path = referenced_asset(base, destination["clouds"]["mask"], "clouds.mask")
            fraction = mask_overlap_fraction(archive.read(mask_path), archive.read(sky_mask_path))
            if fraction > 0.01:
                warnings.append(base + ": clouds/sky mask overlap %.2f%%; procedural sky covers those clouds" % (fraction * 100))
        splat = destination.get("splat")
        if splat is not None:
            require(isinstance(splat, dict), f"{base}.splat must be an object")
            if "ply" in splat:
                referenced_asset(base, splat["ply"], "splat.ply")
            variants = splat.get("variants") or {}
            require(isinstance(variants, dict), f"{base}.splat.variants must be an object")
            for tier, raw_path in variants.items():
                referenced_asset(base, raw_path, f"splat.variants.{tier}")
        audio = destination.get("audio")
        if audio is not None:
            require(isinstance(audio, dict), f"{base}.audio must be an object")
            referenced_asset(base, audio.get("path"), "audio.path")

    for space_id, space in packages["spaces"].items():
        base = f"catalog/spaces/{space_id}"
        require("fireflies" not in space, "fireflies belongs to a View")
        require("clouds" not in space, "clouds belongs to a View")
        require("nearOrbit" not in space, "nearOrbit belongs to a View")
        require("sunPath" not in space and not (isinstance(space.get("environment"), dict) and "sunPath" in space["environment"]), "sunPath belongs to a View")
        if "water" in space:
            from water_contract import MINIMUM_APP, validate_definition
            require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= MINIMUM_APP,
                    "water requires minimumAppVersion >= 1.3.0")
            def room_water_asset(raw, name, png=False, panorama=False, grayscale=False, rgba=False):
                nonlocal total_water_bytes
                asset = referenced_asset(base, raw, name)
                if png:
                    require(asset.lower().endswith('.png'), name + ' must be a PNG')
                    dimensions = archive_image_dimensions(archive, infos[asset], asset, allow_exr=False)
                    nonlocal total_pixels
                    total_pixels = add_pixels(total_pixels, dimensions, asset, maximum_dimension=4096, maximum_total=TOTAL_IMAGE_PIXELS)
                    if panorama: require(dimensions[0] == 2 * dimensions[1], name + ' must be 2:1')
                    with archive.open(asset) as source:
                        data = source.read()
                    _, _, bit_depth, color_type = light_layer_png_info(data, asset)
                    require(bit_depth == 8 and color_type in (0, 2, 4, 6), name + ' must be an 8-bit non-palette PNG')
                    total_water_bytes += texture_bytes(*dimensions, mipmaps=name.endswith(('.normalMap', '.albedo', '.landTexture', '.reflectionPanorama')))
                    require(total_water_bytes <= MAXIMUM_TEXTURE_BYTES, 'water textures exceed the 64 MiB resident budget')
                    if grayscale:
                        require(color_type == 0, name + ' must be a grayscale PNG')
                    if rgba:
                        require(color_type == 6 and data[26:29] == bytes(3), name + ' must be an 8-bit non-interlaced RGBA PNG')
            validate_definition(space['water'], owner='room', require=require, asset=room_water_asset, field=base+'.water')
            if not glow_texture_reserved and any('glow' in r for r in space['water']['regions']):
                total_water_bytes += GLOW_TEXTURE_BYTES
                glow_texture_reserved = True
            total_oceans += sum(region.get('surface', {}).get('motion', 'ocean') != 'still'
                                for region in space['water']['regions'])
            require(total_oceans <= 1, 'water package has more than one ocean')
            total_water_bytes += OCEAN_TEXTURE_BYTES * sum(region.get('surface', {}).get('motion', 'ocean') != 'still'
                                                        for region in space['water']['regions'])
            require(total_water_bytes <= MAXIMUM_TEXTURE_BYTES, 'water textures exceed the 64 MiB resident budget')
        if "rendering" in space:
            rendering = space["rendering"]
            require(isinstance(rendering, dict), "rendering must be an object")
            exact_keys(rendering, required={"softenedReflectionEntities", "uiFadeEntities"}, context="rendering")
            for field, names in rendering.items():
                require(isinstance(names, list), f"rendering.{field} must be an array")
                for name in names:
                    require_text(name, f"rendering.{field}", 200)
                require(len(names) == len(set(names)), f"rendering.{field} contains duplicates")
        for group in (space.get("lighting") or {}).get("luminaireGroups", []):
            for proxy in group.get("proxies", [group["proxy"]] if "proxy" in group else []):
                if "direction" not in proxy:
                    continue
                direction = proxy["direction"]
                require_number_list(direction, 3, "proxy.direction")
                require(proxy.get("type") == "spot" and abs(sum(v * v for v in direction) - 1) < 0.001,
                        "proxy.direction must be a unit vector for a spot light")
        scene = referenced_asset(base, space.get("scene"), "scene")
        provenance = referenced_asset(base, space.get("provenance"), "provenance")
        require(infos[provenance].file_size <= PROVENANCE_BYTES,
                f"provenance budget exceeded: {provenance}")
        validate_provenance(
            decoded_member(archive, infos[provenance], provenance),
            provenance,
        )
        # A Space carries a picture too since #180, and the shipping importer
        # charges it to the same pixel budget the Destination's images pay.
        # This loop inspects no other image, so the omission is easy to make
        # and it would leave this tool passing an archive the app rejects.
        if "thumbnail" in space:
            asset = referenced_asset(
                base, space["thumbnail"], "thumbnail")
            dimensions = archive_image_dimensions(
                archive, infos[asset], asset, allow_exr=False)
            total_pixels = add_pixels(
                total_pixels, dimensions, asset,
                maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS,
            )
        if "caption" in space:
            require_text(space["caption"], f"{base}.caption", 2_000)
        if "previewCamera" in space:
            camera = space["previewCamera"]
            require(
                isinstance(camera, dict),
                f"{base}.previewCamera must be an object",
            )
            for field in ("yawDegrees", "pitchDegrees", "zoom"):
                value = camera.get(field)
                require(
                    type(value) in {int, float}
                    and math.isfinite(value)
                    and (field != "zoom" or value > 0),
                    f"{base}.previewCamera.{field} is invalid",
                )
        require_number_list(space.get("seatedOrigin", {}).get("translationMeters"), 3,
                            f"{base}.seatedOrigin.translationMeters")
        require_number_list(space.get("seatedOrigin", {}).get("orientationXYZW"), 4,
                            f"{base}.seatedOrigin.orientationXYZW")
        safe_head = space.get("safeHeadVolume", {})
        require_number_list(safe_head.get("centerMeters"), 3,
                            f"{base}.safeHeadVolume.centerMeters")
        require_number_list(safe_head.get("sizeMeters"), 3,
                            f"{base}.safeHeadVolume.sizeMeters", positive=True)
        quality = space.get("quality")
        require(isinstance(quality, dict), f"{base}.quality is required")
        require(quality.get("status") in {"unverified", "verified"}, f"{base}.quality.status")
        for field, maximum in (
            ("triangleCount", TRIANGLES), ("materialCount", MATERIALS),
            ("entityCount", ENTITIES), ("maxTextureDimension", MODEL_TEXTURE_DIMENSION),
        ):
            value = quality.get(field)
            require(type(value) is int and 0 <= value <= maximum,
                    f"{base}.quality.{field} exceeds its budget")
        collision = space.get("collision") or {}
        require(isinstance(collision, dict), f"{base}.collision must be an object")
        collision_mode = collision.get("mode")
        require(collision_mode in {"embedded", "separate"},
                f"{base}.collision.mode is invalid")
        if collision_mode == "embedded":
            require("path" not in collision, f"{base}.collision.path requires separate mode")
            collision_asset = None
        else:
            collision_asset = referenced_asset(
                base, collision.get("path"), "collision.path")
            require(collision_asset.lower().endswith(".usdz"),
                    f"{base}.collision.path must be a USDZ")
        teleport_catalog = space.get("teleportCatalog")
        teleport_ids: set[str] = set()
        require(
            isinstance(teleport_catalog, dict),
            f"{base}.teleportCatalog is required for an enterable Room",
        )
        catalog_asset = referenced_asset(
            base, teleport_catalog.get("path"), "teleportCatalog.path")
        teleport_ids = validate_teleport_catalog(
            decoded_member(archive, infos[catalog_asset], catalog_asset),
            teleport_catalog.get("houseID"),
            f"{base}.teleportCatalog",
        )
        if "seatGroups" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 0),
                "seatGroups requires minimumAppVersion >= 1.2.0",
            )
            validate_seat_groups(
                space["seatGroups"], teleport_ids, f"{base}.seatGroups")
        if "videoSurfaces" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "videoSurfaces requires minimumAppVersion >= 1.2.1",
            )
            luminaire_group_ids = {
                group.get("id")
                for group in (space.get("lighting") or {}).get("luminaireGroups", [])
                if isinstance(group, dict)
            }
            video_paths = validate_video_surfaces(
                space["videoSurfaces"], luminaire_group_ids, f"{base}.videoSurfaces")
            for raw in video_paths:
                asset = referenced_asset(base, raw, "videoSurfaces.video")
                require(0 < infos[asset].file_size <= 64 * 1024 * 1024,
                        f"{asset} exceeds the video surface byte limit")
                with archive.open(asset) as source:
                    signature = source.read(12)
                require(len(signature) == 12 and signature[4:8] == b"ftyp",
                        f"{asset} must start with an MP4 ftyp box")
        if any(
            isinstance(group, dict) and group.get("illuminatedEntities")
            for group in (space.get("lighting") or {}).get("luminaireGroups", [])
        ):
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "lighting.luminaireGroups.illuminatedEntities requires minimumAppVersion >= 1.2.1",
            )
        baked_indirect = (space.get("lighting") or {}).get("bakedIndirect")
        if isinstance(baked_indirect, dict) and baked_indirect.get("layers"):
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "lighting.bakedIndirect.layers requires minimumAppVersion >= 1.2.1",
            )
            luminaire_group_ids = {
                group.get("id")
                for group in (space.get("lighting") or {}).get("luminaireGroups", [])
                if isinstance(group, dict)
            }
            layer_images = validate_baked_light_layers(
                baked_indirect["layers"], luminaire_group_ids,
                f"{base}.lighting.bakedIndirect.layers")
            layer_dimensions = None
            for image in layer_images:
                asset = referenced_asset(
                    base, image, "lighting.bakedIndirect.layers.image")
                require(0 < infos[asset].file_size <= 64 * 1024 * 1024,
                        f"{asset} exceeds the light layer image byte limit")
                with archive.open(asset) as source:
                    data = source.read()
                width, height, bit_depth, color_type = light_layer_png_info(
                    data, asset)
                require(color_type in (2, 6) and bit_depth in (8, 16),
                        f"{asset} must be an 8- or 16-bit RGB or RGBA PNG")
                require(width <= 4096 and height <= 4096,
                        f"{asset} exceeds the 4096x4096 light layer dimension limit")
                if layer_dimensions is None:
                    layer_dimensions = (width, height)
                else:
                    require(
                        layer_dimensions == (width, height),
                        "lighting.bakedIndirect.layers images must share identical pixel dimensions",
                    )
        if "viewForwardYawRadians" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "viewForwardYawRadians requires minimumAppVersion >= 1.2.1",
            )
            yaw = space["viewForwardYawRadians"]
            require(
                type(yaw) in {int, float} and math.isfinite(yaw)
                and -math.pi <= yaw <= math.pi,
                f"{base}.viewForwardYawRadians is invalid",
            )
        if "viewGroundFloorOffsetMeters" in space:
            # docs/package-spec-v2.md "Room View ground
            # (`locus.room.view-ground.v1`)": metres above the Room model's
            # visual-bounds minimum Y, the teleport `sourceFloorOffset` frame.
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= VIEW_GROUND_MINIMUM_APP,
                "viewGroundFloorOffsetMeters requires minimumAppVersion >= 1.4.4",
            )
            ground = space["viewGroundFloorOffsetMeters"]
            require(
                type(ground) in {int, float} and math.isfinite(ground)
                and 0 <= ground <= VIEW_GROUND_MAXIMUM_FLOOR_OFFSET_METERS,
                f"{base}.viewGroundFloorOffsetMeters must be a finite number in [0, 100]",
            )
        if "viewGroundKeepOut" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= VIEW_GROUND_MINIMUM_APP,
                "viewGroundKeepOut requires minimumAppVersion >= 1.4.4",
            )
            require(
                type(space["viewGroundKeepOut"]) is bool,
                f"{base}.viewGroundKeepOut must be a boolean",
            )
        if "viewMidgroundVisibility" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= VIEW_MIDGROUND_VISIBILITY_MINIMUM_APP,
                "viewMidgroundVisibility requires minimumAppVersion >= 1.4.4",
            )
            require(
                type(space["viewMidgroundVisibility"]) is str
                and space["viewMidgroundVisibility"] in VIEW_MIDGROUND_VISIBILITIES,
                f"{base}.viewMidgroundVisibility must be one of all, terrainOnly, hidden",
            )
        if "particleEffects" in space:
            require(
                parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
                >= (1, 2, 1),
                "particleEffects requires minimumAppVersion >= 1.2.1",
            )
            validate_particle_effects(
                space["particleEffects"], f"{base}.particleEffects")
        if "spatialAdaptation" in space:
            validate_spatial_adaptation(
                space["spatialAdaptation"], teleport_ids,
                f"{base}.spatialAdaptation",
            )
        validate_display_localizations(space, base, {
            "seatTitles": teleport_ids,
            "seatGroupTitles": title_ids(space.get("seatGroups")),
            "soundTitles": title_ids((space.get("sound") or {}).get("sources")),
            "mediaTitles": title_ids((space.get("media") or {}).get("sources")),
            "lightTitles": title_ids((space.get("lighting") or {}).get("luminaireGroups")),
            "animationTitles": title_ids(space.get("ambientAnimations")),
            "videoTitles": title_ids(space.get("videoSurfaces")),
            "particleTitles": title_ids(space.get("particleEffects")),
        })
        actual = validate_usdz(archive, infos[scene], scene)
        if collision_asset is not None:
            collision_actual = validate_usdz(
                archive, infos[collision_asset], collision_asset
            )
            for field, limit, label in (
                ("triangleCount", TRIANGLES, "triangle"),
                ("materialCount", MATERIALS, "material"),
                ("entityCount", ENTITIES, "entity"),
            ):
                require(
                    actual[field] + collision_actual[field] <= limit,
                    f"combined Room USD {label} budget exceeded: {base}",
                )

    external_references = set()
    for experience_id, experience in packages["experiences"].items():
        base = f"catalog/experiences/{experience_id}/experience.json"
        validate_display_localizations(experience, base, {
            field: set() for field in (
                "seatTitles", "seatGroupTitles", "soundTitles", "mediaTitles",
                "lightTitles", "animationTitles", "videoTitles", "particleTitles")
        })
        destination_id = experience.get("destinationID")
        require(valid_identifier(destination_id), f"{base}.destinationID is invalid")
        if destination_id not in packages["destinations"]:
            external_references.add(destination_id)
        space_id = experience.get("spaceID")
        if space_id is not None:
            require(valid_identifier(space_id), f"{base}.spaceID is invalid")
            if space_id not in packages["spaces"]:
                external_references.add(space_id)
        modes = experience.get("supportedModes")
        require(
            isinstance(modes, list) and modes and len(modes) == len(set(modes))
            and set(modes) <= {"virtual-space", "room-portal"},
            f"{base}.supportedModes is invalid",
        )
        composition = experience.get("composition") or {}
        require(isinstance(composition, dict), f"{base}.composition must be an object")
        destination=packages["destinations"].get(destination_id,{})
        if any("contactCalibration" in region for region in (destination.get("water") or {}).get("regions",[])):
            pitch=composition.get("destinationPitchDegrees",0)
            require(type(pitch) in (int,float) and pitch == 0,
                    f"{base}.composition.destinationPitchDegrees must be zero for layered water contacts")
        if "virtual-space" in modes:
            require(space_id is not None, f"{base} virtual-space requires spaceID")
            opening_id = composition.get("destinationOpeningID")
            require(valid_identifier(opening_id),
                    f"{base} virtual-space requires destinationOpeningID")
            if space_id in packages["spaces"]:
                openings = packages["spaces"][space_id].get("destinationOpenings", [])
                require(any(item.get("id") == opening_id for item in openings),
                        f"{base} references a missing Destination opening")

    payload_files = set(infos) - {"locusplace.json"}
    unreferenced = sorted(payload_files - referenced_files)
    require(
        not unreferenced,
        "runtime ZIP contains a file not referenced by Package-v2 metadata: "
        + (unreferenced[0] if unreferenced else ""),
    )

    has_sun_path = any((value.get("environment") or {}).get("sunPath") is not None
                       for key, value in json_cache.items() if key.endswith("/destination.json"))
    if has_sun_path:
        for key, value in json_cache.items():
            if key.endswith("/space.json"):
                require(all((region.get("bed") or {}).get("sunVisibility") is None
                            for region in (value.get("water") or {}).get("regions", [])),
                        "sunPath cannot coexist with static Room sunVisibility")
    return {
        "packageID": manifest["packageID"],
        "contentVersion": manifest["contentVersion"],
        "views": len(packages["destinations"]),
        "rooms": len(packages["spaces"]),
        "experiences": len(packages["experiences"]),
        "externalReferences": sorted(external_references),
        "warnings": warnings,
        "sunHeuristicFindings": sun_heuristic_findings,
    }


def package_asset(
    base: str, relative: Any, infos: dict[str, zipfile.ZipInfo], field: str
) -> str:
    require(isinstance(relative, str), f"{base}.{field} must be a path")
    require(relative and not relative.startswith("/") and "\\" not in relative,
            f"{base}.{field} has an unsafe path")
    components = relative.split("/")
    require(all(component not in {"", ".", ".."} for component in components),
            f"{base}.{field} has an unsafe path")
    path = f"{base}/{relative}"
    require(path in infos and not infos[path].is_dir(), f"{base}.{field} is missing: {relative}")
    return path


def decoded_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    path: str,
) -> dict[str, Any]:
    require(info.file_size <= JSON_BYTES, f"{path} exceeds the JSON byte budget")
    _, data = stream_member(
        archive, info, maximum=JSON_BYTES, capture=JSON_BYTES
    )
    return decode_json(data, path)


def validate(
    path: Path,
    current_app_version: str = "1.0.0",
) -> dict[str, Any]:
    """Validate one `.locusplace` archive.
    """
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "source is not a regular file")
    require(path.stat().st_size <= ARCHIVE_BYTES, "archive exceeds the byte budget")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ValidationError(f"not a readable ZIP archive: {error}") from error

    with archive:
        entries = archive.infolist()
        require(len(entries) <= ENTRY_COUNT, "archive exceeds the entry budget")
        seen = set()
        infos: dict[str, zipfile.ZipInfo] = {}
        total = 0
        manifest_info = None
        for info in entries:
            require(not is_symlink(info), f"symbolic link is not allowed: {info.filename}")
            value = safe_path(
                info.filename, allow_manifest=True, directory=info.is_dir()
            )
            if not info.is_dir() and value != "locusplace.json":
                extension = PurePosixPath(value).suffix.lower().lstrip(".")
                require(
                    extension not in AUTHORING_SOURCE_EXTENSIONS,
                    f"authoring source files are not allowed in a runtime ZIP: {value}",
                )
            key = collision_key(value)
            require(key not in seen, f"duplicate or colliding ZIP path: {info.filename}")
            seen.add(key)
            if info.is_dir():
                continue
            require(not (info.flag_bits & 0x1), f"encrypted entry is not allowed: {value}")
            require(info.compress_size > 0 or info.file_size == 0,
                    f"suspicious compression ratio: {value}")
            require(
                info.file_size == 0 or info.file_size <= info.compress_size * COMPRESSION_RATIO,
                f"suspicious compression ratio: {value}",
            )
            if value == "locusplace.json":
                manifest_info = info
                require(info.file_size <= MANIFEST_BYTES, "locusplace.json is too large")
            else:
                require(info.file_size <= FILE_BYTES, f"file exceeds byte budget: {value}")
                total += info.file_size
                require(total <= TOTAL_BYTES, "archive exceeds expanded byte budget")
            infos[value] = info

        require(manifest_info is not None, "locusplace.json is missing")
        _, manifest_bytes = stream_member(
            archive, manifest_info, maximum=MANIFEST_BYTES, capture=MANIFEST_BYTES
        )
        manifest = validate_envelope(manifest_bytes, current_app_version)
        declarations = {record["path"]: record for record in manifest["files"]}
        payload_infos = {path: info for path, info in infos.items() if path != "locusplace.json"}
        require(set(payload_infos) == set(declarations),
                "archive files do not exactly match locusplace.json")

        json_cache: dict[str, dict[str, Any]] = {}
        for member_path in sorted(payload_infos):
            info = payload_infos[member_path]
            record = declarations[member_path]
            require(info.file_size == record["byteCount"],
                    f"declared byteCount mismatch: {member_path}")
            capture = JSON_BYTES if member_path.lower().endswith(".json") else 0
            if member_path.lower().endswith(".locusmesh"):
                require(info.file_size <= 32 * 1024 * 1024,
                        member_path + ' exceeds the contact mesh byte budget')
            if capture:
                require(info.file_size <= capture, member_path + ' exceeds the JSON byte budget')
            digest, prefix = stream_member(
                archive, info, maximum=FILE_BYTES, capture=capture
            )
            require(digest == record["sha256"], f"SHA-256 mismatch: {member_path}")
            if capture:
                json_cache[member_path] = decode_json(prefix, member_path)

        return validate_payload(archive, payload_infos, manifest, json_cache)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("archive", type=Path)
    result.add_argument(
        "--current-app-version", default="1.0.0",
        help="three-component Locus version used for compatibility checks",
    )
    result.add_argument("--json", action="store_true", help="print a JSON summary")
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        summary = validate(arguments.archive, arguments.current_app_version)
    except (OSError, ValidationError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    if arguments.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "VALID "
            f"{summary['packageID']}@{summary['contentVersion']} "
            f"({summary['views']} View, {summary['rooms']} Room, "
            f"{summary['experiences']} Experience)"
        )
        for warning in summary["warnings"]:
            print("WARNING: " + warning, file=sys.stderr)
        if summary["externalReferences"]:
            print(
                "NOTE: references resolved by the installed catalog: "
                + ", ".join(summary["externalReferences"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
