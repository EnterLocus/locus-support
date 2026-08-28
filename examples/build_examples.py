#!/usr/bin/env python3
"""Build deterministic, self-contained .locusplace v1 example archives."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import zlib
import zipfile
from pathlib import Path


PROVENANCE = {
    "formatVersion": 1,
    "creatorOrAgency": "Locus Example Studio",
    "sourcePageURL": "https://example.com/locusplace-source",
    "originalAssetURL": "https://example.com/locusplace-asset",
    "license": {
        "identifier": "CC0-1.0",
        "name": "CC0 1.0 Universal",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
    },
    "requestedCredit": "Locus Example Studio",
    "modificationNotes": "Generated locally as a tiny Package-v2 import fixture.",
    "aiGenerated": False,
}


def json_bytes(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def panorama_png(width: int = 16, height: int = 8) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(
                (
                    30 + (x * 170 // max(width - 1, 1)),
                    60 + (y * 120 // max(height - 1, 1)),
                    180,
                    255,
                )
            )
        rows.append(bytes(row))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
        )
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows), level=9))
        + png_chunk(b"IEND", b"")
    )


def usdz_bytes() -> bytes:
    usda = b"""#usda 1.0
(
    defaultPrim = "Root"
    upAxis = "Y"
    metersPerUnit = 1
)
def Xform "Root" {
    def Cube "Shell" {
        double size = 2
    }
}
"""
    from io import BytesIO

    output = BytesIO()
    with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
        info = zipfile.ZipInfo("root.usda")
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        # The first member's local header is 30 bytes plus its 9-byte name.
        # A valid extra field of 25 bytes aligns file data to a 64-byte offset.
        info.extra = struct.pack("<HH", 0xFFFF, 21) + bytes(21)
        archive.writestr(info, usda)
    return output.getvalue()


def destination_payload() -> dict[str, bytes]:
    destination_id = "destination.example-view"
    base = f"catalog/destinations/{destination_id}"
    return {
        f"{base}/destination.json": json_bytes(
            {
                "formatVersion": 2,
                "id": destination_id,
                "title": "Example View",
                "panorama": {
                    "path": "panorama.png",
                    "projection": "equirectangular",
                    "width": 16,
                    "height": 8,
                    "initialYawDegrees": 0,
                },
                "caption": "A generated gradient used only for import validation.",
                "provenance": "provenance.json",
            }
        ),
        f"{base}/panorama.png": panorama_png(),
        f"{base}/provenance.json": json_bytes(PROVENANCE),
    }


def room_payload() -> dict[str, bytes]:
    space_id = "space.example-room"
    base = f"catalog/spaces/{space_id}"
    return {
        f"{base}/space.json": json_bytes(
            {
                "formatVersion": 2,
                "id": space_id,
                "title": "Example Room",
                "scene": "scene.usdz",
                "seatedOrigin": {
                    "translationMeters": [0, 0, 0],
                    "orientationXYZW": [0, 0, 0, 1],
                },
                "safeHeadVolume": {
                    "centerMeters": [0, 1.25, 0],
                    "sizeMeters": [1.2, 1.0, 1.0],
                },
                "destinationOpenings": [
                    {
                        "id": "front",
                        "transform": {
                            "translationMeters": [0, 1.2, -2],
                            "orientationXYZW": [0, 0, 0, 1],
                        },
                        "widthMeters": 4,
                        "heightMeters": 2.5,
                    }
                ],
                "collision": {"mode": "embedded"},
                "teleportCatalog": {
                    "path": "teleport-points.json",
                    "houseID": space_id,
                },
                "quality": {
                    "status": "unverified",
                    "triangleCount": 12,
                    "materialCount": 0,
                    "entityCount": 2,
                    "maxTextureDimension": 0,
                },
                "provenance": "provenance.json",
            }
        ),
        f"{base}/scene.usdz": usdz_bytes(),
        f"{base}/teleport-points.json": json_bytes(
            {
                "houses": {
                    space_id: [
                        {
                            "id": "seat.center",
                            "title": "Center Seat",
                            "anchorXZ": [0.5, 0.5],
                            "sourceFloorOffset": 0,
                            "eyeHeight": 1.15,
                            "yawRadians": 0,
                        }
                    ]
                }
            }
        ),
        f"{base}/provenance.json": json_bytes(PROVENANCE),
    }


def experience_payload() -> dict[str, bytes]:
    experience_id = "experience.example-combined"
    base = f"catalog/experiences/{experience_id}"
    return {
        f"{base}/experience.json": json_bytes(
            {
                "formatVersion": 2,
                "id": experience_id,
                "title": "Example Combined Place",
                "destinationID": "destination.example-view",
                "spaceID": "space.example-room",
                "supportedModes": ["virtual-space"],
                "composition": {
                    "destinationOpeningID": "front",
                    "destinationYawDegrees": 0,
                    "destinationPitchDegrees": 0,
                    "destinationExposureOffsetEV": 0,
                },
            }
        )
    }


def content_hash(records: list[dict]) -> str:
    canonical = bytearray()
    for record in sorted(records, key=lambda item: item["path"]):
        canonical.extend(record["path"].encode("utf-8"))
        canonical.append(0)
        canonical.extend(str(record["byteCount"]).encode("ascii"))
        canonical.append(0)
        canonical.extend(record["sha256"].encode("ascii"))
        canonical.append(0)
    return hashlib.sha256(canonical).hexdigest()


def file_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_archive(
    output: Path,
    *,
    package_id: str,
    destination_ids: list[str],
    space_ids: list[str],
    experience_ids: list[str],
    payload: dict[str, bytes],
) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    records = [
        {
            "path": path,
            "byteCount": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for path, data in sorted(payload.items())
    ]
    envelope = {
        "formatVersion": 1,
        "packageID": package_id,
        "contentVersion": "1.0.0",
        "minimumAppVersion": "1.0.0",
        "contents": {
            "destinationIDs": destination_ids,
            "spaceIDs": space_ids,
            "experienceIDs": experience_ids,
        },
        "files": records,
        "contentHash": content_hash(records),
    }
    with zipfile.ZipFile(output, "x", allowZip64=True) as archive:
        archive.writestr(file_info("locusplace.json"), json_bytes(envelope))
        for path, data in sorted(payload.items()):
            archive.writestr(file_info(path), data)


def build_examples(output_directory: Path) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_directory / "view-only.locusplace",
        output_directory / "room-only.locusplace",
        output_directory / "combined.locusplace",
    ]
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite an existing example archive")

    view = destination_payload()
    room = room_payload()
    experience = experience_payload()
    build_archive(
        outputs[0],
        package_id="place.example-view-only",
        destination_ids=["destination.example-view"],
        space_ids=[],
        experience_ids=[],
        payload=view,
    )
    build_archive(
        outputs[1],
        package_id="place.example-room-only",
        destination_ids=[],
        space_ids=["space.example-room"],
        experience_ids=[],
        payload=room,
    )
    build_archive(
        outputs[2],
        package_id="place.example-combined",
        destination_ids=["destination.example-view"],
        space_ids=["space.example-room"],
        experience_ids=["experience.example-combined"],
        payload={**view, **room, **experience},
    )
    return outputs


def main() -> int:
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("output_directory", type=Path)
    options = arguments.parse_args()
    for output in build_examples(options.output_directory):
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
