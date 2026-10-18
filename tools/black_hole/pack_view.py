#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Pack a baked Package v2 View source folder into an archive Locus can import.

The source folder keeps the on-disk Package v2 layout: a root
`locusplace.json` plus `catalog/`. You may omit the generated `files` and
`contentHash` fields while editing; this command recalculates both from the
payload bytes, writes an ordinary `.zip` (or `.locusplace`), and validates the
result with validate_view.py before publishing it.

    python3 pack_view.py ring-source black-hole-ring.locusplace
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
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_view import (  # noqa: E402
    ValidationError, calculate_content_hash, collision_key, decode_json, exact_keys, safe_path, validate)

AUTHOR_FIELDS = {"formatVersion", "packageID", "contentVersion", "minimumAppVersion", "contents"}
GENERATED_FIELDS = {"files", "contentHash"}
# Runtime media is already compressed, so it is stored byte for byte.
STORED_SUFFIXES = {".usdz", ".jpg", ".jpeg", ".png", ".exr", ".m4a", ".mp3"}
SAFE_COMPRESSION_RATIO = 150  # below the validators' 200:1 guard
IGNORED_NAMES = {".DS_Store"}
BUFFER_BYTES = 1024 * 1024


class PackError(ValueError):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(BUFFER_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_files(source):
    """Sorted (archive path, file) pairs for everything except locusplace.json."""
    if source.is_symlink() or not source.is_dir():
        raise PackError(f"source must be a real directory: {source}")
    files, seen = [], set()
    for root, directories, filenames in os.walk(source, followlinks=False):
        root_path = Path(root)
        for name in directories:
            if (root_path / name).is_symlink():
                raise PackError(f"source contains a symlink: {root_path / name}")
        for name in filenames:
            if name in IGNORED_NAMES:
                continue
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
                files.append((relative, path))
    manifest = source / "locusplace.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise PackError(f"source is missing a regular locusplace.json: {source}")
    return sorted(files)


def authored_manifest(source):
    manifest = decode_json((source / "locusplace.json").read_bytes(), "locusplace.json")
    exact_keys(manifest, required=AUTHOR_FIELDS, optional=GENERATED_FIELDS, context="editable locusplace.json")
    return {field: manifest[field] for field in AUTHOR_FIELDS}


def build_manifest(source):
    """The final `locusplace.json` (as a dict and as the exact bytes written) for a source folder."""
    payload = payload_files(source)
    records = [{"path": name, "byteCount": path.stat().st_size, "sha256": sha256_file(path)}
               for name, path in payload]
    manifest = authored_manifest(source)
    manifest["files"] = records
    manifest["contentHash"] = calculate_content_hash(records)
    data = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    return manifest, data, payload


def zip_info(path, stored=False):
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def write_member(archive, name, source):
    stored = source.suffix.lower() in STORED_SUFFIXES
    if not stored:
        # Highly repetitive data could deflate past the validators' 200:1
        # zip-bomb guard; store it instead.
        data = source.read_bytes()
        stored = len(data) > SAFE_COMPRESSION_RATIO * max(1, len(zlib.compress(data, 6)))
    with source.open("rb") as input_file, archive.open(zip_info(name, stored), "w") as output:
        shutil.copyfileobj(input_file, output, length=BUFFER_BYTES)


def pack(source, output, *, current_app_version="1.3.4"):
    source = Path(source).resolve()
    output = Path(output).absolute()
    if output.suffix.lower() not in {".zip", ".locusplace"}:
        raise PackError("output must end in .zip or .locusplace")
    if output.exists():
        raise PackError(f"refusing to overwrite {output}")
    parent = output.parent.resolve()
    if source == parent or source in parent.parents:
        raise PackError("output must be outside the editable source directory")
    if not output.parent.is_dir():
        raise PackError(f"output directory does not exist: {output.parent}")

    _, manifest_bytes, payload = build_manifest(source)
    temporary = output.parent / f".{output.name}.packing-{uuid.uuid4().hex}"
    try:
        with zipfile.ZipFile(temporary, "x", allowZip64=True) as archive:
            archive.writestr(zip_info("locusplace.json"), manifest_bytes)
            for name, path in payload:
                write_member(archive, name, path)
        summary = validate(temporary, current_app_version)
        try:
            # A hard link publishes atomically and fails if the output appeared meanwhile.
            os.link(temporary, output)
        except FileExistsError as error:
            raise PackError(f"refusing to overwrite {output}") from error
        return summary
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Package v2 source folder (from bake_view.py)")
    parser.add_argument("output", type=Path, help="archive to create, ending in .zip or .locusplace")
    parser.add_argument("--current-app-version", default="1.3.4",
                        help="the Locus version you will import into (default 1.3.4)")
    args = parser.parse_args(argv)
    try:
        summary = pack(args.source, args.output, current_app_version=args.current_app_version)
    except (OSError, PackError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    print(f"VALID: {summary['packageID']} {summary['contentVersion']} ({summary['views']} View) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
