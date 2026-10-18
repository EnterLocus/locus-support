#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Validate a packed Package v2 black-hole View before importing it into Locus.

Checks the archive envelope exactly as Locus does (safe paths, file inventory,
byte counts, SHA-256 and `contentHash`), then each View: `destination.json`,
the panorama, thumbnail and lighting images, provenance, and the `blackHole`
profile with its five images. It is a focused creator check for
`locus.view.black-hole.v1` packages, not a full validator for every Locus
package profile; Locus still validates the archive again when you import it.

    python3 validate_view.py my-black-hole.locusplace
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import stat
import sys
import unicodedata
import urllib.parse
import zipfile
import zlib
from pathlib import Path, PurePosixPath

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import black_hole_profile as V  # noqa: E402
from imaging import png_header  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

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
IDENTIFIER_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
IDENTIFIER_MAX = 128
SHA256_CHARS = frozenset("0123456789abcdef")
AUTHORING_SOURCE_EXTENSIONS = frozenset({"blend", "blend1", "blend2", "fbx", "obj", "mtl", "gltf", "glb"})
COLLECTIONS = {
    "destinations": ("destinationIDs", "destination.json"),
    "spaces": ("spaceIDs", "space.json"),
    "experiences": ("experienceIDs", "experience.json"),
}


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def is_finite_number(value):
    return type(value) in {int, float} and math.isfinite(value)


def _no_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_json(data, path):
    require(len(data) <= JSON_BYTES, f"{path} exceeds the JSON byte budget")

    def reject_nonstandard_number(value):
        raise ValidationError(f"{path} contains non-standard number {value}")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                           parse_constant=reject_nonstandard_number)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{path} is not valid UTF-8 JSON: {error}") from error
    require(isinstance(value, dict), f"{path} root must be an object")
    return value


def exact_keys(value, *, required, optional=frozenset(), context):
    keys = set(value)
    unknown = keys - set(required) - set(optional)
    missing = set(required) - keys
    if unknown:
        raise ValidationError(f"{context} has unknown field {sorted(unknown)[0]}")
    if missing:
        raise ValidationError(f"{context} is missing field {sorted(missing)[0]}")


def valid_identifier(value):
    return (isinstance(value, str) and bool(value) and len(value) <= IDENTIFIER_MAX
            and value[0].isascii() and value[0].isalnum()
            and all(character in IDENTIFIER_CHARS for character in value))


def parse_version(value, field):
    require(isinstance(value, str), f"{field} must be a semantic version")
    parts = value.split(".")
    require(len(parts) == 3 and all(part and part.isascii() and part.isdigit() for part in parts),
            f"{field} must contain exactly three numeric components")
    return tuple(int(part) for part in parts)


def canonical_sha256(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= SHA256_CHARS


def safe_path(raw, *, allow_manifest, directory=False):
    """A ZIP member path inside the package namespace (`locusplace.json` or `catalog/...`)."""
    require(isinstance(raw, str), "ZIP paths must be strings")
    value = raw[:-1] if directory and raw.endswith("/") else raw
    components = value.split("/")
    require(value, f"unsafe archive path: {raw!r}")
    require(unicodedata.normalize("NFC", value) == value, f"non-NFC path: {raw}")
    require(len(value.encode("utf-8")) <= PATH_BYTES, f"path is too long: {raw}")
    require(not value.startswith("/") and "\\" not in value, f"unsafe archive path: {raw}")
    require(not any(ord(character) < 32 or ord(character) == 127 for character in value),
            f"control character in path: {raw!r}")
    require(all(component not in {"", ".", ".."} and len(component.encode("utf-8")) <= COMPONENT_BYTES
                for component in components), f"unsafe archive path: {raw}")
    require((allow_manifest and value == "locusplace.json") or components[0] == "catalog",
            f"path is outside the .locusplace namespace: {raw}")
    return value


def collision_key(path):
    return unicodedata.normalize("NFC", path).casefold()


def calculate_content_hash(records):
    """SHA-256 over every file record sorted by path: path NUL byteCount NUL sha256 NUL."""
    canonical = bytearray()
    for record in sorted(records, key=lambda item: item["path"]):
        canonical.extend(record["path"].encode("utf-8"))
        canonical.append(0)
        canonical.extend(str(record["byteCount"]).encode("ascii"))
        canonical.append(0)
        canonical.extend(record["sha256"].encode("ascii"))
        canonical.append(0)
    return hashlib.sha256(canonical).hexdigest()


def validate_envelope(data, current_app_version):
    manifest = decode_json(data, "locusplace.json")
    exact_keys(manifest, required={"formatVersion", "packageID", "contentVersion", "minimumAppVersion",
                                   "contents", "files", "contentHash"}, context="locusplace.json")
    require(type(manifest["formatVersion"]) is int and manifest["formatVersion"] == 1,
            "unsupported .locusplace formatVersion")
    require(valid_identifier(manifest["packageID"]), "invalid packageID")
    parse_version(manifest["contentVersion"], "contentVersion")
    minimum = parse_version(manifest["minimumAppVersion"], "minimumAppVersion")
    current = parse_version(current_app_version, "currentAppVersion")
    require(minimum <= current, f"package requires Locus {manifest['minimumAppVersion']}")

    contents = manifest["contents"]
    require(isinstance(contents, dict), "contents must be an object")
    exact_keys(contents, required={"destinationIDs", "spaceIDs", "experienceIDs"}, context="contents")
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
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"files[{index}] must be an object")
        exact_keys(record, required={"path", "byteCount", "sha256"}, context=f"files[{index}]")
        path = safe_path(record["path"], allow_manifest=False)
        key = collision_key(path)
        require(key not in seen, f"duplicate or colliding file path: {path}")
        seen.add(key)
        require(type(record["byteCount"]) is int and record["byteCount"] >= 0, f"invalid byteCount for {path}")
        require(canonical_sha256(record["sha256"]), f"invalid SHA-256 for {path}")
    require(canonical_sha256(manifest["contentHash"]), "invalid contentHash")
    require(calculate_content_hash(records) == manifest["contentHash"], "contentHash mismatch")
    return manifest


# ---------------------------------------------------------------- images

def image_info(data, path):
    """(width, height, png (bit depth, colour type) or None for JPEG); decodes the full payload."""
    header = png_header(data)
    if header is not None:
        width, height, depth, colour, interlace = header
        if depth == 16:
            # Pillow cannot hold 16-bit colour; inflate and size-check the rows instead.
            channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour)
            require(channels is not None and interlace == 0, f"unsupported 16-bit PNG layout: {path}")
            idat, offset = b"", 8
            while offset < len(data):
                length = int.from_bytes(data[offset:offset + 4], "big")
                if data[offset + 4:offset + 8] == b"IDAT":
                    idat += data[offset + 8:offset + 8 + length]
                offset += 12 + length
            try:
                raw = zlib.decompress(idat)
            except zlib.error as error:
                raise ValidationError(f"PNG pixel payload is corrupt: {path}") from error
            require(len(raw) == height * (width * channels * 2 + 1), f"PNG pixel payload is incomplete: {path}")
        else:
            _decode_with_pillow(data, path, "PNG")
        return width, height, (depth, colour)
    if data[:2] == b"\xff\xd8":
        require(data.endswith(b"\xff\xd9"), f"JPEG has trailing bytes or is incomplete: {path}")
        width, height = _decode_with_pillow(data, path, "JPEG")
        return width, height, None
    raise ValidationError(f"unsupported image content (use JPEG or PNG): {path}")


def _decode_with_pillow(data, path, expected):
    try:
        with Image.open(io.BytesIO(data)) as image:
            require(image.format == expected, f"unsupported image content: {path}")
            image.load()
            return image.size
    except (OSError, SyntaxError, ValueError) as error:
        raise ValidationError(f"image cannot be decoded: {path}: {error}") from error


class _PixelBudget:
    def __init__(self):
        self.total = 0

    def add(self, dimensions, path, maximum_dimension=IMAGE_DIMENSION):
        width, height = dimensions
        pixels = width * height
        require(width > 0 and height > 0 and width <= maximum_dimension and height <= maximum_dimension
                and pixels <= IMAGE_PIXELS and self.total + pixels <= TOTAL_IMAGE_PIXELS,
                f"image budget exceeded: {path}")
        self.total += pixels


# ---------------------------------------------------------------- provenance

def require_https(value, field):
    require(isinstance(value, str), f"{field} must be an HTTPS URL")
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme.lower() == "https" and bool(parsed.hostname) and parsed.username is None
            and parsed.password is None and not parsed.fragment,
            f"{field} must be an HTTPS URL without credentials or fragment")


def require_text(value, field, maximum):
    require(isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8")) <= maximum,
            f"{field} is missing or too long")


def validate_provenance(value, path):
    exact_keys(value, required={"formatVersion", "creatorOrAgency", "requestedCredit", "modificationNotes",
                                "aiGenerated"},
               optional={"sourcePageURL", "originalAssetURL", "license", "rights", "aiProvider", "importSource"},
               context=path)
    require(type(value["formatVersion"]) is int and value["formatVersion"] == 1, f"{path}.formatVersion must be 1")
    require_text(value["creatorOrAgency"], f"{path}.creatorOrAgency", 200)
    require_text(value["requestedCredit"], f"{path}.requestedCredit", 1_000)
    require_text(value["modificationNotes"], f"{path}.modificationNotes", 2_000)
    require(type(value["aiGenerated"]) is bool, f"{path}.aiGenerated must be boolean")
    require(("license" in value) != ("rights" in value), f"{path} must contain exactly one of license or rights")
    if "license" in value:
        licence = value["license"]
        require(isinstance(licence, dict), f"{path}.license must be an object")
        exact_keys(licence, required={"identifier", "name", "url"}, context=f"{path}.license")
        require_text(licence["identifier"], f"{path}.license.identifier", 100)
        require_text(licence["name"], f"{path}.license.name", 200)
        require_https(licence["url"], f"{path}.license.url")
    else:
        rights = value["rights"]
        require(isinstance(rights, dict), f"{path}.rights must be an object")
        exact_keys(rights, required={"statement", "url"}, context=f"{path}.rights")
        require_text(rights["statement"], f"{path}.rights.statement", 1_000)
        require_https(rights["url"], f"{path}.rights.url")
    for field in ("sourcePageURL", "originalAssetURL"):
        if field in value:
            require_https(value[field], f"{path}.{field}")
    if value["aiGenerated"]:
        require_text(value.get("aiProvider"), f"{path}.aiProvider", 200)
    else:
        require("aiProvider" not in value, f"{path}.aiProvider requires aiGenerated=true")
    require("importSource" not in value, f"{path}.importSource is reserved for direct Locus imports")


# ---------------------------------------------------------------- payload

def _asset(base, relative, infos, field, referenced):
    require(isinstance(relative, str), f"{base}.{field} must be a path")
    require(relative and not relative.startswith("/") and "\\" not in relative, f"{base}.{field} has an unsafe path")
    require(all(component not in {"", ".", ".."} for component in relative.split("/")),
            f"{base}.{field} has an unsafe path")
    path = f"{base}/{relative}"
    require(path in infos and not infos[path].is_dir(), f"{base}.{field} is missing: {relative}")
    referenced.add(path)
    return path


def validate_destination(archive, infos, manifest, base, destination, referenced, budget):
    for field in ("depthLayers", "splat", "audio"):
        require(destination.get(field) is None, f"unsupported public-import Destination field: {field}")
    panorama = destination.get("panorama")
    require(isinstance(panorama, dict), f"{base}/destination.json.panorama is required")
    require(panorama.get("projection") == "equirectangular", "unsupported panorama projection")
    width, height = panorama.get("width"), panorama.get("height")
    require(type(width) is int and type(height) is int and width > 0 and width == 2 * height,
            f"{base} panorama dimensions must be positive 2:1")
    initial_yaw = panorama.get("initialYawDegrees")
    require(initial_yaw is None or is_finite_number(initial_yaw), f"{base}.panorama.initialYawDegrees must be finite")
    panorama_path = _asset(base, panorama.get("path"), infos, "panorama.path", referenced)
    w, h, _ = image_info(archive.read(panorama_path), panorama_path)
    require((w, h) == (width, height), f"{panorama_path} dimensions do not match manifest")
    budget.add((w, h), panorama_path)

    black_hole = destination.get("blackHole")
    require(black_hole is not None, f"{base} has no blackHole profile; this tool validates black-hole Views only")
    require(parse_version(manifest["minimumAppVersion"], "minimumAppVersion") >= V.MINIMUM_APP,
            "blackHole requires minimumAppVersion >= 1.3.4")
    require(all(destination.get(field) is None for field in V.EXCLUDED),
            "blackHole cannot coexist with other dynamic View profiles")
    require((destination.get("environment") or {}).get("sunPath") is None,
            "blackHole cannot coexist with environment.sunPath")
    for field, raw in V.validate_definition(black_hole, require).items():
        asset = _asset(base, raw, infos, "blackHole." + field, referenced)
        w, h, png_format = image_info(archive.read(asset), asset)
        require(field == "skyTexture" or png_format is not None, "blackHole.%s must be a PNG" % field)
        V.validate_image(field, w, h, png_format, require)
        budget.add((w, h), asset, maximum_dimension=V.SKY_MAX_WIDTH)

    for field in ("sourceImage", "thumbnail"):
        if field in destination:
            asset = _asset(base, destination[field], infos, field, referenced)
            w, h, _ = image_info(archive.read(asset), asset)
            budget.add((w, h), asset)

    environment = destination.get("environment")
    if environment is not None:
        require(isinstance(environment, dict), f"{base}.environment must be an object")
        for field in ("skyGainEV", "exposureEV", "horizonPitchDegrees"):
            value = environment.get(field)
            require(value is None or is_finite_number(value), f"environment.{field} must be finite")
        if "colorGrade" in environment:
            grade = environment["colorGrade"]
            require(isinstance(grade, dict), "environment.colorGrade must be an object")
            exact_keys(grade, required={"contrast", "saturation"}, context="environment.colorGrade")
            for field, lower, upper in (("contrast", 0.5, 2.0), ("saturation", 0.0, 2.0)):
                require(is_finite_number(grade[field]) and lower <= grade[field] <= upper,
                        f"environment.colorGrade.{field} must be between {lower:g} and {upper:g}")
        if "directSun" in environment:
            sun = environment["directSun"]
            require(isinstance(sun, dict), "environment.directSun must be an object")
            exact_keys(sun, required={"enabled", "illuminanceLux"}, optional={"azimuthDegrees", "elevationDegrees"},
                       context="environment.directSun")
            require(type(sun["enabled"]) is bool, "environment.directSun.enabled must be a boolean")
            require(is_finite_number(sun["illuminanceLux"]) and sun["illuminanceLux"] >= 0,
                    "environment.directSun.illuminanceLux must be finite and non-negative")
            for field in ("azimuthDegrees", "elevationDegrees"):
                require(sun.get(field) is None or is_finite_number(sun.get(field)),
                        f"environment.directSun.{field} must be finite")
        if "imageBasedLight" in environment:
            asset = _asset(base, environment["imageBasedLight"], infos, "environment.imageBasedLight", referenced)
            require(asset != panorama_path, "environment.imageBasedLight must not reuse the visible panorama")
            w, h, _ = image_info(archive.read(asset), asset)
            budget.add((w, h), asset)
            require(w == 2 * h, f"{asset} dimensions must be positive 2:1")

    provenance_path = _asset(base, destination.get("provenance"), infos, "provenance", referenced)
    require(infos[provenance_path].file_size <= PROVENANCE_BYTES, f"provenance budget exceeded: {provenance_path}")
    validate_provenance(decode_json(archive.read(provenance_path), provenance_path), provenance_path)


def validate(path, current_app_version="1.3.4"):
    """Validate one `.locusplace` / `.zip` archive; return a short summary dict."""
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
        seen, infos, total, manifest_info = set(), {}, 0, None
        for info in entries:
            require(stat.S_IFMT(info.external_attr >> 16) != stat.S_IFLNK,
                    f"symbolic link is not allowed: {info.filename}")
            value = safe_path(info.filename, allow_manifest=True, directory=info.is_dir())
            if not info.is_dir() and value != "locusplace.json":
                extension = PurePosixPath(value).suffix.lower().lstrip(".")
                require(extension not in AUTHORING_SOURCE_EXTENSIONS,
                        f"authoring source files are not allowed in a runtime ZIP: {value}")
            key = collision_key(value)
            require(key not in seen, f"duplicate or colliding ZIP path: {info.filename}")
            seen.add(key)
            if info.is_dir():
                continue
            require(not (info.flag_bits & 0x1), f"encrypted entry is not allowed: {value}")
            require(info.compress_size > 0 or info.file_size == 0, f"suspicious compression ratio: {value}")
            require(info.file_size == 0 or info.file_size <= info.compress_size * COMPRESSION_RATIO,
                    f"suspicious compression ratio: {value}")
            if value == "locusplace.json":
                manifest_info = info
                require(info.file_size <= MANIFEST_BYTES, "locusplace.json is too large")
            else:
                require(info.file_size <= FILE_BYTES, f"file exceeds byte budget: {value}")
                total += info.file_size
                require(total <= TOTAL_BYTES, "archive exceeds expanded byte budget")
            infos[value] = info
        require(manifest_info is not None, "locusplace.json is missing")
        manifest = validate_envelope(archive.read(manifest_info), current_app_version)
        declarations = {record["path"]: record for record in manifest["files"]}
        payload = {name: info for name, info in infos.items() if name != "locusplace.json"}
        require(set(payload) == set(declarations), "archive files do not exactly match locusplace.json")
        json_cache = {}
        for member in sorted(payload):
            info, record = payload[member], declarations[member]
            require(info.file_size == record["byteCount"], f"declared byteCount mismatch: {member}")
            digest = hashlib.sha256()
            with archive.open(info) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            require(digest.hexdigest() == record["sha256"], f"SHA-256 mismatch: {member}")
            if member.lower().endswith(".json"):
                json_cache[member] = decode_json(archive.read(info), member)

        contents = manifest["contents"]
        require(not contents["spaceIDs"] and not contents["experienceIDs"],
                "this tool validates View-only packages; check Rooms and Experiences with Locus")
        declared = set(contents["destinationIDs"])
        for member in payload:
            parts = member.split("/")
            require(len(parts) >= 4 and parts[0] == "catalog" and parts[1] == "destinations" and parts[2] in declared,
                    f"unknown or undeclared payload path: {member}")
        referenced, budget = set(), _PixelBudget()
        for destination_id in sorted(declared):
            base = f"catalog/destinations/{destination_id}"
            manifest_path = f"{base}/destination.json"
            require(manifest_path in json_cache, f"missing Package-v2 manifest: {manifest_path}")
            destination = json_cache[manifest_path]
            require(type(destination.get("formatVersion")) is int and destination["formatVersion"] == 2,
                    f"{manifest_path} must use Package-v2")
            require(destination.get("id") == destination_id, f"{manifest_path} has mismatched ID")
            require_text(destination.get("title"), f"{manifest_path}.title", 10_000)
            referenced.add(manifest_path)
            validate_destination(archive, payload, manifest, base, destination, referenced, budget)
        unreferenced = sorted(set(payload) - referenced)
        require(not unreferenced, "runtime ZIP contains a file not referenced by Package-v2 metadata: "
                + (unreferenced[0] if unreferenced else ""))
    return {"packageID": manifest["packageID"], "contentVersion": manifest["contentVersion"],
            "views": len(declared), "minimumAppVersion": manifest["minimumAppVersion"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--current-app-version", default="1.3.4",
                        help="the Locus version you will import into (default 1.3.4)")
    args = parser.parse_args(argv)
    try:
        summary = validate(args.archive, args.current_app_version)
    except (OSError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    print(f"VALID: {summary['packageID']} {summary['contentVersion']} ({summary['views']} View, "
          f"needs Locus {summary['minimumAppVersion']} or later)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
