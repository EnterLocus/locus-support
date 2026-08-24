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


ARCHIVE_BYTES = 1_073_741_824
ENTRY_COUNT = 4_096
MANIFEST_BYTES = 1_048_576
FILE_BYTES = 805_306_368
TOTAL_BYTES = 2_147_483_648
COMPRESSION_RATIO = 200
PATH_BYTES = 512
COMPONENT_BYTES = 128
JSON_BYTES = 1_048_576
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


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


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


def jpeg_dimensions(source: BinaryIO, file_size: int, path: str) -> tuple[int, int]:
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
            require(width > 0 and height > 0, f"malformed JPEG frame: {path}")
        if marker == 0xDA:
            require(width is not None, f"JPEG dimensions unavailable: {path}")
            previous_ff = False
            while chunk := source.read(64 * 1024):
                for index, byte in enumerate(chunk):
                    if previous_ff and byte == 0xD9:
                        require(
                            index == len(chunk) - 1 and not source.read(1),
                            f"JPEG has trailing bytes: {path}",
                        )
                        return width, height
                    previous_ff = byte == 0xFF
            raise ValidationError(f"JPEG pixel payload is incomplete: {path}")
    raise ValidationError(f"JPEG pixel payload is incomplete: {path}")


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


def validate_provenance(value: dict[str, Any], path: str) -> None:
    exact_keys(
        value,
        required={
            "formatVersion", "creatorOrAgency", "license", "requestedCredit",
            "modificationNotes", "aiGenerated",
        },
        optional={"sourcePageURL", "originalAssetURL", "aiProvider"},
        context=path,
    )
    require(type(value["formatVersion"]) is int and value["formatVersion"] == 1,
            f"{path}.formatVersion must be 1")
    require_text(value["creatorOrAgency"], f"{path}.creatorOrAgency", 200)
    require_text(value["requestedCredit"], f"{path}.requestedCredit", 1_000)
    require_text(value["modificationNotes"], f"{path}.modificationNotes", 2_000)
    require(type(value["aiGenerated"]) is bool, f"{path}.aiGenerated must be boolean")
    license_value = value["license"]
    require(isinstance(license_value, dict), f"{path}.license must be an object")
    exact_keys(
        license_value,
        required={"identifier", "name", "url"},
        context=f"{path}.license",
    )
    require_text(license_value["identifier"], f"{path}.license.identifier", 100)
    require_text(license_value["name"], f"{path}.license.name", 200)
    require_https(license_value["url"], f"{path}.license.url")
    for field in ("sourcePageURL", "originalAssetURL"):
        if field in value:
            require_https(value[field], f"{path}.{field}")
    if value["aiGenerated"]:
        require_text(value.get("aiProvider"), f"{path}.aiProvider", 200)
    else:
        require("aiProvider" not in value, f"{path}.aiProvider requires aiGenerated=true")


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


def validate_usdz(
    outer: zipfile.ZipFile, info: zipfile.ZipInfo, path: str
) -> dict[str, int]:
    require(info.file_size <= MODEL_BYTES, f"model budget exceeded: {path}")
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as temporary:
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


def validate_payload(
    archive: zipfile.ZipFile,
    infos: dict[str, zipfile.ZipInfo],
    manifest: dict[str, Any],
    json_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
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

    total_pixels = 0
    for destination_id, destination in packages["destinations"].items():
        base = f"catalog/destinations/{destination_id}"
        for field in (
            "sourceImage", "depthLayers", "midground", "splat", "audio"
        ):
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
        panorama_path = referenced_asset(base, panorama.get("path"), "panorama.path")
        dimensions = archive_image_dimensions(
            archive, infos[panorama_path], panorama_path, allow_exr=False)
        require(dimensions == (width, height), f"{panorama_path} dimensions do not match manifest")
        total_pixels = add_pixels(
            total_pixels, dimensions, panorama_path,
            maximum_dimension=IMAGE_DIMENSION, maximum_total=TOTAL_IMAGE_PIXELS,
        )
        provenance_path = referenced_asset(
            base, destination.get("provenance"), "provenance"
        )
        require(infos[provenance_path].file_size <= PROVENANCE_BYTES,
                f"provenance budget exceeded: {provenance_path}")
        validate_provenance(
            decoded_member(archive, infos[provenance_path], provenance_path),
            provenance_path,
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
            for field in ("visibleSkyHDR", "imageBasedLight"):
                if field in environment:
                    asset = referenced_asset(
                        base, environment[field], f"environment.{field}")
                    with archive.open(infos[asset]) as source:
                        dimensions = exr_stream_dimensions(
                            source, infos[asset].file_size, asset)
                        require_imageio_decode(source, asset, ".exr")
                    total_pixels = add_pixels(
                        total_pixels, dimensions, asset,
                        maximum_dimension=IMAGE_DIMENSION,
                        maximum_total=TOTAL_IMAGE_PIXELS,
                    )
                    require(
                        dimensions[0] == 2 * dimensions[1],
                        f"{asset} dimensions must be positive 2:1",
                    )
            if "hdrManifest" in environment:
                asset = referenced_asset(
                    base, environment["hdrManifest"], "environment.hdrManifest")
                require(
                    PurePosixPath(asset).suffix.lower() == ".json",
                    "environment.hdrManifest must reference a .json file",
                )
                decoded_member(archive, infos[asset], asset)
        for index, depth in enumerate(destination.get("depthLayers") or []):
            require(isinstance(depth, dict), f"{base}.depthLayers[{index}] must be an object")
            referenced_asset(base, depth.get("path"), f"depthLayers[{index}].path")
        midground = destination.get("midground")
        if midground is not None:
            require(isinstance(midground, dict), f"{base}.midground must be an object")
            referenced_asset(base, midground.get("path"), "midground.path")
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
        scene = referenced_asset(base, space.get("scene"), "scene")
        provenance = referenced_asset(base, space.get("provenance"), "provenance")
        require(infos[provenance].file_size <= PROVENANCE_BYTES,
                f"provenance budget exceeded: {provenance}")
        validate_provenance(
            decoded_member(archive, infos[provenance], provenance),
            provenance,
        )
        # A Space carries a picture too, and the shipping importer
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
        if teleport_catalog is not None:
            require(isinstance(teleport_catalog, dict),
                    f"{base}.teleportCatalog must be an object")
            catalog_asset = referenced_asset(
                base, teleport_catalog.get("path"), "teleportCatalog.path")
            teleport_ids = validate_teleport_catalog(
                decoded_member(archive, infos[catalog_asset], catalog_asset),
                teleport_catalog.get("houseID"),
                f"{base}.teleportCatalog",
            )
        if "spatialAdaptation" in space:
            validate_spatial_adaptation(
                space["spatialAdaptation"], teleport_ids,
                f"{base}.spatialAdaptation",
            )
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

    return {
        "packageID": manifest["packageID"],
        "contentVersion": manifest["contentVersion"],
        "views": len(packages["destinations"]),
        "rooms": len(packages["spaces"]),
        "experiences": len(packages["experiences"]),
        "externalReferences": sorted(external_references),
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


def validate(path: Path, current_app_version: str = "1.0.0") -> dict[str, Any]:
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
        if summary["externalReferences"]:
            print(
                "NOTE: references resolved by the installed catalog: "
                + ", ".join(summary["externalReferences"])
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
