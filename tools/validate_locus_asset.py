#!/usr/bin/env python3
"""Validate a public Locus Room or View ZIP without installing it."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ARCHIVE_BYTES = 1_073_741_824
FILE_BYTES = 805_306_368
TOTAL_BYTES = 2_147_483_648
JSON_BYTES = 1_048_576
PROVENANCE_BYTES = 65_536
ENTRY_COUNT = 4_096
COMPRESSION_RATIO = 200
COMPONENT_BYTES = 128
IMAGE_DIMENSION = 32_768
IMAGE_PIXELS = 150_000_000
MODEL_ENTRIES = 4_096
MODEL_EXPANDED_BYTES = 1_610_612_736
IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
ROOM_FILES = {
    "space.json",
    "provenance.json",
    "teleport-points.json",
    "scene.usdz",
    "thumbnail.jpg",
}
VIEW_REQUIRED_FILES = {
    "view.json",
    "provenance.json",
    "panorama.jpg",
    "thumbnail.jpg",
}
VIEW_OPTIONAL_FILES = {"lighting.jpg"}
USDZ_EXTENSIONS = {
    "usd", "usda", "usdc", "png", "jpg", "jpeg", "exr", "m4a", "wav", "mp3"
}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def finite(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_json(path: Path, name: str) -> dict[str, Any]:
    require(path.stat().st_size <= JSON_BYTES, f"{name} exceeds the JSON byte limit")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=lambda raw: (_ for _ in ()).throw(
                ValidationError(f"{name} contains non-standard number {raw}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{name} is not valid UTF-8 JSON: {error}") from error
    require(isinstance(value, dict), f"{name} root must be an object")
    return value


def exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    context: str,
) -> None:
    unknown = set(value) - required - optional
    missing = required - set(value)
    if unknown:
        raise ValidationError(f"{context} has unsupported field {sorted(unknown)[0]}")
    if missing:
        raise ValidationError(f"{context} is missing field {sorted(missing)[0]}")


def require_text(value: Any, field: str, maximum: int) -> None:
    require(
        isinstance(value, str)
        and bool(value.strip())
        and len(value.encode("utf-8")) <= maximum,
        f"{field} is missing or too long",
    )


def require_https(value: Any, field: str) -> None:
    require(isinstance(value, str), f"{field} must be an HTTPS URL")
    parsed = urllib.parse.urlsplit(value)
    require(
        parsed.scheme.lower() == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment,
        f"{field} must be an HTTPS URL without credentials or a fragment",
    )


def valid_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.encode("utf-8")) <= 128
        and value[0].isascii()
        and value[0].isalnum()
        and all(character in IDENTIFIER_CHARS for character in value)
    )


def safe_root_name(value: str) -> bool:
    return (
        bool(value)
        and "/" not in value
        and "\\" not in value
        and value not in {".", ".."}
        and value == unicodedata.normalize("NFC", value)
        and len(value.encode("utf-8")) <= COMPONENT_BYTES
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def extract_archive(source: Path, destination: Path) -> set[str]:
    require(source.is_file() and not source.is_symlink(), "source must be a regular ZIP file")
    require(source.stat().st_size <= ARCHIVE_BYTES, "ZIP exceeds the archive byte limit")
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as error:
        raise ValidationError(f"file is not a readable ZIP: {error}") from error
    with archive:
        infos = archive.infolist()
        require(len(infos) <= ENTRY_COUNT, "ZIP contains too many entries")
        seen: set[str] = set()
        total = 0
        for info in infos:
            require(not info.is_dir(), f"directories are not allowed: {info.filename}")
            require(not is_symlink(info), f"symbolic links are not allowed: {info.filename}")
            require(safe_root_name(info.filename), f"nested or unsafe entry: {info.filename}")
            key = unicodedata.normalize("NFC", info.filename).casefold()
            require(key not in seen, f"duplicate or colliding entry: {info.filename}")
            seen.add(key)
            require(info.file_size <= FILE_BYTES, f"file exceeds byte limit: {info.filename}")
            total += info.file_size
            require(total <= TOTAL_BYTES, "ZIP expands beyond the total byte limit")
            if info.file_size:
                require(info.compress_size > 0, f"invalid compression: {info.filename}")
                require(
                    info.file_size <= info.compress_size * COMPRESSION_RATIO,
                    f"suspicious compression ratio: {info.filename}",
                )
            target = destination / info.filename
            written = 0
            try:
                with archive.open(info) as input_file, target.open("xb") as output:
                    while chunk := input_file.read(1024 * 1024):
                        written += len(chunk)
                        require(written <= info.file_size, f"entry expanded past size: {info.filename}")
                        output.write(chunk)
            except (RuntimeError, zipfile.BadZipFile) as error:
                raise ValidationError(f"could not extract {info.filename}: {error}") from error
            require(written == info.file_size, f"entry size changed: {info.filename}")
        return {info.filename for info in infos}


def validate_provenance(path: Path) -> None:
    require(path.stat().st_size <= PROVENANCE_BYTES, "provenance.json exceeds its byte limit")
    value = decode_json(path, "provenance.json")
    exact_keys(
        value,
        required={
            "formatVersion", "creatorOrAgency", "license", "requestedCredit",
            "modificationNotes", "aiGenerated",
        },
        optional={"sourcePageURL", "originalAssetURL", "aiProvider"},
        context="provenance.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "provenance.json.formatVersion must be 1")
    require_text(value["creatorOrAgency"], "creatorOrAgency", 200)
    require_text(value["requestedCredit"], "requestedCredit", 1_000)
    require_text(value["modificationNotes"], "modificationNotes", 2_000)
    require(type(value["aiGenerated"]) is bool, "aiGenerated must be boolean")
    license_value = value["license"]
    require(isinstance(license_value, dict), "license must be an object")
    exact_keys(
        license_value,
        required={"identifier", "name", "url"},
        context="provenance.json.license",
    )
    require_text(license_value["identifier"], "license.identifier", 100)
    require_text(license_value["name"], "license.name", 200)
    require_https(license_value["url"], "license.url")
    for field in ("sourcePageURL", "originalAssetURL"):
        if field in value:
            require_https(value[field], field)
    if value["aiGenerated"]:
        require_text(value.get("aiProvider"), "aiProvider", 200)
    else:
        require("aiProvider" not in value, "aiProvider requires aiGenerated=true")


def require_number_list(value: Any, count: int, field: str) -> None:
    require(
        isinstance(value, list) and len(value) == count and all(finite(item) for item in value),
        f"{field} must contain {count} finite numbers",
    )


def validate_pose(value: Any, field: str) -> None:
    require(isinstance(value, dict), f"{field} must be an object")
    exact_keys(
        value,
        required={"translationMeters", "orientationXYZW"},
        context=field,
    )
    require_number_list(value["translationMeters"], 3, f"{field}.translationMeters")
    require_number_list(value["orientationXYZW"], 4, f"{field}.orientationXYZW")


def validate_image(path: Path, *, equirectangular: bool) -> tuple[int, int]:
    sips = shutil.which("sips")
    require(sips is not None, "macOS sips is required to validate images")
    try:
        metadata = subprocess.run(
            [sips, "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValidationError(f"image inspection timed out: {path.name}") from error
    require(metadata.returncode == 0, f"image cannot be decoded: {path.name}")
    properties = {}
    for line in metadata.stdout.splitlines():
        if ":" in line:
            key, raw = line.strip().split(":", 1)
            properties[key] = raw.strip()
    try:
        width = int(properties["pixelWidth"])
        height = int(properties["pixelHeight"])
    except (KeyError, ValueError) as error:
        raise ValidationError(f"image dimensions unavailable: {path.name}") from error
    require(
        0 < width <= IMAGE_DIMENSION
        and 0 < height <= IMAGE_DIMENSION
        and width * height <= IMAGE_PIXELS,
        f"image exceeds dimension or pixel limit: {path.name}",
    )
    if equirectangular:
        require(width == 2 * height, f"{path.name} must be a 2:1 equirectangular image")
    with tempfile.TemporaryDirectory(prefix="locus-image-") as directory:
        output = Path(directory) / "decoded.png"
        decoded = subprocess.run(
            [sips, "-s", "format", "png", "-z", "1", "2", str(path), "--out", str(output)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=False,
        )
        require(decoded.returncode == 0 and output.is_file() and output.stat().st_size > 0,
                f"image pixel payload cannot be decoded: {path.name}")
    return width, height


def safe_model_path(raw: str, directory: bool) -> bool:
    value = raw[:-1] if directory and raw.endswith("/") else raw
    components = value.split("/")
    return (
        bool(value)
        and value == unicodedata.normalize("NFC", value)
        and not value.startswith("/")
        and "\\" not in value
        and all(
            component not in {"", ".", ".."}
            and len(component.encode("utf-8")) <= COMPONENT_BYTES
            and not any(ord(character) < 32 or ord(character) == 127
                        for character in component)
            for component in components
        )
    )


def validate_usdz(path: Path) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ValidationError("scene.usdz is not a valid USDZ archive") from error
    with archive:
        infos = archive.infolist()
        require(0 < len(infos) <= MODEL_ENTRIES, "scene.usdz has too many entries")
        expanded = 0
        root_layer = False
        seen: set[str] = set()
        for info in infos:
            require(not is_symlink(info), f"USDZ symlink is not allowed: {info.filename}")
            require(safe_model_path(info.filename, info.is_dir()),
                    f"unsafe USDZ path: {info.filename}")
            key = unicodedata.normalize("NFC", info.filename.rstrip("/")).casefold()
            require(key not in seen, f"duplicate USDZ path: {info.filename}")
            seen.add(key)
            if info.is_dir():
                continue
            require(info.compress_type == zipfile.ZIP_STORED,
                    f"USDZ entry must be stored without compression: {info.filename}")
            expanded += info.file_size
            require(expanded <= MODEL_EXPANDED_BYTES, "scene.usdz exceeds expanded byte limit")
            extension = PurePosixPath(info.filename).suffix.lower().lstrip(".")
            require(extension in USDZ_EXTENSIONS, f"unsupported USDZ file: {info.filename}")
            if "/" not in info.filename and extension in {"usd", "usda", "usdc"}:
                root_layer = True
        require(root_layer, "scene.usdz has no root USD layer")

    checker = shutil.which("usdchecker")
    require(checker is not None, "usdchecker is required to validate scene.usdz")
    try:
        checked = subprocess.run(
            [checker, "--arkit", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValidationError("scene.usdz validation timed out") from error
    require(checked.returncode == 0, "scene.usdz fails RealityKit USD validation")


def validate_teleports(path: Path) -> set[str]:
    value = decode_json(path, "teleport-points.json")
    exact_keys(
        value,
        required={"formatVersion", "points"},
        context="teleport-points.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "teleport-points.json.formatVersion must be 1")
    points = value["points"]
    require(isinstance(points, list) and bool(points),
            "teleport-points.json must contain at least one seat")
    identifiers: set[str] = set()
    for index, point in enumerate(points):
        context = f"teleport-points.json.points[{index}]"
        require(isinstance(point, dict), f"{context} must be an object")
        exact_keys(
            point,
            required={
                "id", "title", "anchorXZ", "sourceFloorOffset", "eyeHeight",
                "yawRadians",
            },
            context=context,
        )
        require(valid_identifier(point["id"]), f"{context}.id is invalid")
        require(point["id"] not in identifiers, f"duplicate teleport id {point['id']}")
        identifiers.add(point["id"])
        require_text(point["title"], f"{context}.title", 200)
        require_number_list(point["anchorXZ"], 2, f"{context}.anchorXZ")
        require(all(0 <= number <= 1 for number in point["anchorXZ"]),
                f"{context}.anchorXZ must be normalized from 0 to 1")
        require(finite(point["sourceFloorOffset"]) and point["sourceFloorOffset"] >= 0,
                f"{context}.sourceFloorOffset is invalid")
        require(finite(point["eyeHeight"]) and point["eyeHeight"] > 0,
                f"{context}.eyeHeight is invalid")
        require(finite(point["yawRadians"]), f"{context}.yawRadians is invalid")
    return identifiers


def validate_spatial_adaptation(value: Any, teleport_ids: set[str]) -> None:
    require(isinstance(value, dict), "space.json.spatialAdaptation must be an object")
    exact_keys(
        value,
        required={"wallEntities", "roofEntities", "deskEntitiesByTeleportID"},
        context="space.json.spatialAdaptation",
    )
    walls = value["wallEntities"]
    roofs = value["roofEntities"]
    desks = value["deskEntitiesByTeleportID"]
    require(isinstance(walls, list) and all(isinstance(item, str) and item.strip() for item in walls),
            "wallEntities must contain non-empty names")
    require(isinstance(roofs, list) and all(isinstance(item, str) and item.strip() for item in roofs),
            "roofEntities must contain non-empty names")
    require(len(walls) == len(set(walls)), "wallEntities contains duplicates")
    require(len(roofs) == len(set(roofs)), "roofEntities contains duplicates")
    require(set(walls).isdisjoint(roofs), "wallEntities overlaps roofEntities")
    require(isinstance(desks, dict), "deskEntitiesByTeleportID must be an object")
    for teleport_id, entity in desks.items():
        require(teleport_id in teleport_ids and isinstance(entity, str) and entity.strip(),
                f"desk mapping is invalid for teleport {teleport_id}")


def validate_room(root: Path) -> dict[str, Any]:
    value = decode_json(root / "space.json", "space.json")
    exact_keys(
        value,
        required={
            "formatVersion", "displayName", "seatedOrigin", "safeHeadVolume",
            "viewOpenings",
        },
        optional={"caption", "previewCamera", "spatialAdaptation"},
        context="space.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "space.json.formatVersion must be 1")
    require_text(value["displayName"], "space.json.displayName", 200)
    if "caption" in value:
        require_text(value["caption"], "space.json.caption", 1_000)
    if "previewCamera" in value:
        camera = value["previewCamera"]
        require(isinstance(camera, dict), "space.json.previewCamera must be an object")
        exact_keys(
            camera,
            required={"yawDegrees", "pitchDegrees", "zoom"},
            context="space.json.previewCamera",
        )
        require(finite(camera["yawDegrees"]), "previewCamera.yawDegrees must be finite")
        require(finite(camera["pitchDegrees"]), "previewCamera.pitchDegrees must be finite")
        require(finite(camera["zoom"]) and camera["zoom"] > 0,
                "previewCamera.zoom must be positive")
    validate_pose(value["seatedOrigin"], "space.json.seatedOrigin")
    volume = value["safeHeadVolume"]
    require(isinstance(volume, dict), "space.json.safeHeadVolume must be an object")
    exact_keys(volume, required={"centerMeters", "sizeMeters"}, context="safeHeadVolume")
    require_number_list(volume["centerMeters"], 3, "safeHeadVolume.centerMeters")
    require_number_list(volume["sizeMeters"], 3, "safeHeadVolume.sizeMeters")
    require(all(number > 0 for number in volume["sizeMeters"]),
            "safeHeadVolume.sizeMeters must be positive")
    openings = value["viewOpenings"]
    require(isinstance(openings, list) and len(openings) == 1,
            "space.json.viewOpenings must contain exactly one opening")
    opening = openings[0]
    require(isinstance(opening, dict), "viewOpenings[0] must be an object")
    exact_keys(
        opening,
        required={"id", "transform", "widthMeters", "heightMeters"},
        context="viewOpenings[0]",
    )
    require(valid_identifier(opening["id"]), "viewOpenings[0].id is invalid")
    validate_pose(opening["transform"], "viewOpenings[0].transform")
    require(finite(opening["widthMeters"]) and opening["widthMeters"] > 0,
            "viewOpenings[0].widthMeters must be positive")
    require(finite(opening["heightMeters"]) and opening["heightMeters"] > 0,
            "viewOpenings[0].heightMeters must be positive")
    teleports = validate_teleports(root / "teleport-points.json")
    if "spatialAdaptation" in value:
        validate_spatial_adaptation(value["spatialAdaptation"], teleports)
    validate_provenance(root / "provenance.json")
    validate_image(root / "thumbnail.jpg", equirectangular=False)
    validate_usdz(root / "scene.usdz")
    return {"kind": "room", "displayName": value["displayName"], "seats": len(teleports)}


def validate_environment(value: Any) -> None:
    require(isinstance(value, dict), "view.json.environment must be an object")
    exact_keys(
        value,
        required=set(),
        optional={
            "skyGainEV", "exposureEV", "horizonPitchDegrees", "colorGrade", "directSun"
        },
        context="view.json.environment",
    )
    for field in ("skyGainEV", "exposureEV", "horizonPitchDegrees"):
        if field in value:
            require(finite(value[field]), f"environment.{field} must be finite")
    if "colorGrade" in value:
        grade = value["colorGrade"]
        require(isinstance(grade, dict), "environment.colorGrade must be an object")
        exact_keys(grade, required={"contrast", "saturation"}, context="colorGrade")
        require(finite(grade["contrast"]) and 0.5 <= grade["contrast"] <= 2,
                "colorGrade.contrast must be between 0.5 and 2")
        require(finite(grade["saturation"]) and 0 <= grade["saturation"] <= 2,
                "colorGrade.saturation must be between 0 and 2")
    if "directSun" in value:
        sun = value["directSun"]
        require(isinstance(sun, dict), "environment.directSun must be an object")
        exact_keys(
            sun,
            required={"enabled", "illuminanceLux"},
            optional={"azimuthDegrees", "elevationDegrees"},
            context="directSun",
        )
        require(type(sun["enabled"]) is bool, "directSun.enabled must be boolean")
        require(finite(sun["illuminanceLux"]) and sun["illuminanceLux"] >= 0,
                "directSun.illuminanceLux must be non-negative")
        for field in ("azimuthDegrees", "elevationDegrees"):
            if field in sun:
                require(finite(sun[field]), f"directSun.{field} must be finite")
        if sun["enabled"]:
            require("azimuthDegrees" in sun and "elevationDegrees" in sun,
                    "enabled directSun requires azimuthDegrees and elevationDegrees")


def validate_view(root: Path, files: set[str]) -> dict[str, Any]:
    value = decode_json(root / "view.json", "view.json")
    exact_keys(
        value,
        required={"formatVersion", "displayName", "panorama"},
        optional={"caption", "environment"},
        context="view.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "view.json.formatVersion must be 1")
    require_text(value["displayName"], "view.json.displayName", 200)
    panorama = value["panorama"]
    require(isinstance(panorama, dict), "view.json.panorama must be an object")
    exact_keys(
        panorama,
        required={"projection", "width", "height"},
        optional={"initialYawDegrees"},
        context="view.json.panorama",
    )
    require(panorama["projection"] == "equirectangular", "unsupported panorama projection")
    require(type(panorama["width"]) is int and type(panorama["height"]) is int,
            "panorama width and height must be integers")
    dimensions = validate_image(root / "panorama.jpg", equirectangular=True)
    require(dimensions == (panorama["width"], panorama["height"]),
            "panorama dimensions do not match view.json")
    if "initialYawDegrees" in panorama:
        require(finite(panorama["initialYawDegrees"]), "initialYawDegrees must be finite")
    if "environment" in value:
        validate_environment(value["environment"])
    validate_provenance(root / "provenance.json")
    validate_image(root / "thumbnail.jpg", equirectangular=False)
    if "lighting.jpg" in files:
        validate_image(root / "lighting.jpg", equirectangular=True)
    return {"kind": "view", "displayName": value["displayName"], "seats": 0}


def validate(path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="locus-asset-") as directory:
        root = Path(directory)
        files = extract_archive(path, root)
        if "space.json" in files and "view.json" not in files:
            missing = ROOM_FILES - files
            extra = files - ROOM_FILES
            if missing:
                raise ValidationError(f"Room ZIP is missing {sorted(missing)[0]}")
            if extra:
                raise ValidationError(f"Room ZIP contains unsupported file {sorted(extra)[0]}")
            return validate_room(root)
        if "view.json" in files and "space.json" not in files:
            missing = VIEW_REQUIRED_FILES - files
            extra = files - VIEW_REQUIRED_FILES - VIEW_OPTIONAL_FILES
            if missing:
                raise ValidationError(f"View ZIP is missing {sorted(missing)[0]}")
            if extra:
                raise ValidationError(f"View ZIP contains unsupported file {sorted(extra)[0]}")
            return validate_view(root, files)
        raise ValidationError("ZIP must contain either space.json or view.json, but not both")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        summary = validate(arguments.archive)
    except (OSError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            f"VALID: {summary['kind']} \"{summary['displayName']}\""
            + (f" ({summary['seats']} seats)" if summary["kind"] == "room" else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
