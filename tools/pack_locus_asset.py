#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Pack and validate one flat public Locus Room or View directory."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path

from validate_locus_asset import ValidationError, validate


BUFFER_BYTES = 1024 * 1024


class PackError(ValueError):
    pass


def source_files(source: Path) -> list[tuple[str, Path]]:
    if source.is_symlink() or not source.is_dir():
        raise PackError(f"source must be a real directory: {source}")
    files: list[tuple[str, Path]] = []
    for item in source.iterdir():
        mode = item.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise PackError(f"source must contain only regular root files: {item.name}")
        files.append((item.name, item))
    return sorted(files)


def zip_info(path: str, stored: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    return info


def pack(source: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    output = output.absolute()
    if output.suffix.lower() != ".zip":
        raise PackError("output must end in .zip")
    if output.exists():
        raise PackError(f"refusing to overwrite {output}")
    if not output.parent.is_dir():
        raise PackError(f"output directory does not exist: {output.parent}")
    files = source_files(source)
    temporary = output.parent / f".{output.name}.packing-{uuid.uuid4().hex}"
    try:
        with zipfile.ZipFile(temporary, "x", allowZip64=True) as archive:
            for name, path in files:
                stored = path.suffix.lower() in {
                    ".usdz", ".jpg", ".jpeg", ".png", ".exr"
                }
                with path.open("rb") as input_file, archive.open(
                    zip_info(name, stored), "w"
                ) as output_file:
                    shutil.copyfileobj(input_file, output_file, length=BUFFER_BYTES)
        summary = validate(temporary)
        try:
            os.link(temporary, output)
        except FileExistsError as error:
            raise PackError(f"refusing to overwrite {output}") from error
        return summary
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        summary = pack(arguments.source, arguments.output)
    except (OSError, PackError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    print(f"VALID: {summary['kind']} \"{summary['displayName']}\" -> {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
