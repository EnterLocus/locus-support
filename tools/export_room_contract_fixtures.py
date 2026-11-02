#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export deterministic Room contract fixtures from public Python sources.

Usage:

    python3 tools/export_room_contract_fixtures.py /absolute/path/to/output

The output directory must be new or empty. Each contract case produces a flat
compatibility ZIP and a Package v2 archive plus ``manifest.json`` containing
their SHA-256 values and the importer, entry, and checker expectations.

Fixtures are generated from ``tests/room_fixtures.py``. Its only binary input
is the pinned public thumbnail member at
``examples/atrium-loft-room.zip#thumbnail.jpg``. No generated archive belongs
in Git; regenerate a fresh directory for a consumer or test run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import room_contract_cases  # noqa: E402
import room_fixtures  # noqa: E402


THUMBNAIL_SOURCE = "examples/atrium-loft-room.zip#thumbnail.jpg"
MANIFEST_NAME = "manifest.json"
TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _content_hash(records: Iterable[dict]) -> str:
    canonical = bytearray()
    for record in sorted(records, key=lambda item: item["path"]):
        for item in (record["path"], str(record["byteCount"]), record["sha256"]):
            canonical.extend(item.encode("utf-8"))
            canonical.append(0)
    return hashlib.sha256(canonical).hexdigest()


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _write_zip(output: Path, files: Dict[str, bytes]) -> None:
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(files.items()):
            archive.writestr(_zip_info(path), data)


def _flat_files(room: room_fixtures.Room) -> Dict[str, bytes]:
    return room.flat_files()


def _v2_files(room: room_fixtures.Room, package_id: str) -> Dict[str, bytes]:
    payload = room.v2_payload()
    records = [{
        "path": path,
        "byteCount": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    } for path, data in sorted(payload.items())]
    envelope = {
        "formatVersion": 1,
        "packageID": package_id,
        "contentVersion": "1.0.0",
        "minimumAppVersion": "1.2.1",
        "contents": {
            "destinationIDs": [],
            "spaceIDs": [room_fixtures.SPACE_ID],
            "experienceIDs": [],
        },
        "files": records,
        "contentHash": _content_hash(records),
    }
    files = dict(payload)
    files["locusplace.json"] = _json(envelope)
    return files


def _archive_record(output: Path, archive_format: str) -> dict:
    data = output.read_bytes()
    return {
        "format": archive_format,
        "path": output.name,
        "byteCount": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _case_archives(case: room_contract_cases.ContractCase, output: Path) -> List[dict]:
    room = case.room()
    flat = output / (case.identifier + ".flat.zip")
    v2 = output / (case.identifier + ".locusplace")
    _write_zip(flat, _flat_files(room))
    _write_zip(v2, _v2_files(room, "fixtures.room-contract." + case.identifier))
    return [_archive_record(flat, "flat"), _archive_record(v2, "package-v2")]


def build(output: Path) -> Path:
    """Create all source-generated fixture archives and return the manifest."""
    if output.exists() and not output.is_dir():
        raise ValueError("output must be a directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    ids = [case.identifier for case in room_contract_cases.CASES]
    if len(ids) != len(set(ids)):
        raise ValueError("Room contract case IDs must be unique")
    cases = []
    for case in room_contract_cases.CASES:
        cases.append({
            "id": case.identifier,
            "description": case.description,
            "annotations": case.annotation(),
            "archives": _case_archives(case, output),
        })
    manifest = {
        "formatVersion": 1,
        "annotationStatus": "expected-app-behavior",
        "fixtureSource": "tests/room_fixtures.py",
        "thumbnailSource": THUMBNAIL_SOURCE,
        "cases": cases,
    }
    path = output / MANIFEST_NAME
    path.write_bytes(_json(manifest))
    return path


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new or empty output directory")
    arguments = parser.parse_args(argv)
    try:
        manifest = build(arguments.output)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("error: " + str(error), file=sys.stderr)
        return 2
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
