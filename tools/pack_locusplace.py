#!/usr/bin/env python3
"""Pack an editable Locus place directory into a validated ZIP archive.

The source directory keeps the public on-disk format: a root
``locusplace.json`` plus ``catalog/``. Authors may omit the generated ``files``
and ``contentHash`` fields while editing; this command recalculates both from
the payload bytes, writes an ordinary ``.zip`` (or branded ``.locusplace``),
and runs the repository validator before publishing the result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path

from validate_locusplace import (
    ValidationError,
    calculate_content_hash,
    collision_key,
    decode_json,
    exact_keys,
    safe_path,
    validate,
)


AUTHOR_FIELDS = {
    "formatVersion",
    "packageID",
    "contentVersion",
    "minimumAppVersion",
    "contents",
}
GENERATED_FIELDS = {"files", "contentHash"}
BUFFER_BYTES = 1024 * 1024


class PackError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(BUFFER_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def payload_files(source: Path) -> list[tuple[str, Path]]:
    if source.is_symlink() or not source.is_dir():
        raise PackError(f"source must be a real directory: {source}")

    files: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for root, directories, filenames in os.walk(source, followlinks=False):
        root_path = Path(root)
        for name in directories:
            directory = root_path / name
            if directory.is_symlink():
                raise PackError(f"source contains a symlink: {directory}")
        for name in filenames:
            path = root_path / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise PackError(f"source contains a symlink: {path}")
            if not stat.S_ISREG(mode):
                raise PackError(f"source contains a non-regular file: {path}")
            relative = path.relative_to(source).as_posix()
            safe_path(relative, allow_manifest=True)
            key = collision_key(relative)
            if key in seen:
                raise PackError(f"source contains colliding paths: {relative}")
            seen.add(key)
            if relative != "locusplace.json":
                safe_path(relative, allow_manifest=False)
                files.append((relative, path))

    manifest = source / "locusplace.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise PackError(f"source is missing a regular locusplace.json: {source}")
    return sorted(files)


def authored_manifest(source: Path) -> dict[str, object]:
    path = source / "locusplace.json"
    manifest = decode_json(path.read_bytes(), "locusplace.json")
    exact_keys(
        manifest,
        required=AUTHOR_FIELDS,
        optional=GENERATED_FIELDS,
        context="editable locusplace.json",
    )
    return {field: manifest[field] for field in AUTHOR_FIELDS}


def zip_info(path: str, *, stored: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def write_member(
    archive: zipfile.ZipFile, name: str, source: Path
) -> None:
    # Runtime media is already compressed. Store it byte-for-byte instead of
    # spending minutes recompressing 12K EXRs, JPEGs, or nested USDZ archives.
    already_compressed = {
        ".usdz", ".jpg", ".jpeg", ".png", ".exr", ".m4a", ".mp3"
    }
    info = zip_info(name, stored=source.suffix.lower() in already_compressed)
    with source.open("rb") as input_file, archive.open(info, "w") as output:
        shutil.copyfileobj(input_file, output, length=BUFFER_BYTES)


def publish_without_overwrite(temporary: Path, output: Path) -> None:
    """Atomically publish `temporary` only if `output` still does not exist."""
    try:
        # Both paths share a parent, so the hard link is same-filesystem and
        # becomes visible atomically. Unlike rename/replace, link fails with
        # EEXIST if another author or packer wins the destination race.
        os.link(temporary, output)
    except FileExistsError as error:
        raise PackError(f"refusing to overwrite {output}") from error


def pack(
    source: Path,
    output: Path,
    *,
    current_app_version: str = "1.0.0",
) -> dict[str, object]:
    source = source.resolve()
    output = output.absolute()
    resolved_output_parent = output.parent.resolve()
    if output.suffix.lower() not in {".zip", ".locusplace"}:
        raise PackError("output must end in .zip or .locusplace")
    if output.exists():
        raise PackError(f"refusing to overwrite {output}")
    if source == resolved_output_parent or source in resolved_output_parent.parents:
        raise PackError("output must be outside the editable source directory")
    if not output.parent.is_dir():
        raise PackError(f"output directory does not exist: {output.parent}")

    payload = payload_files(source)
    records = [
        {
            "path": name,
            "byteCount": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for name, path in payload
    ]
    manifest = authored_manifest(source)
    manifest["files"] = records
    manifest["contentHash"] = calculate_content_hash(records)
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")

    temporary = output.parent / f".{output.name}.packing-{uuid.uuid4().hex}"
    try:
        with zipfile.ZipFile(temporary, "x", allowZip64=True) as archive:
            archive.writestr(zip_info("locusplace.json"), manifest_bytes)
            for name, path in payload:
                write_member(archive, name, path)
        summary = validate(temporary, current_app_version)
        publish_without_overwrite(temporary, output)
        return summary
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--current-app-version", default="1.0.0")
    arguments = parser.parse_args(argv)
    try:
        summary = pack(
            arguments.source,
            arguments.output,
            current_app_version=arguments.current_app_version,
        )
    except (OSError, PackError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    print(
        "VALID: "
        f"{summary['packageID']} {summary['contentVersion']} "
        f"({summary['views']} View, {summary['rooms']} Room, "
        f"{summary['experiences']} Experience) -> {arguments.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
