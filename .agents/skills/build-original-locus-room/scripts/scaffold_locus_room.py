#!/usr/bin/env python3
"""Create a reviewable flat Locus Room source directory from finished media."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path


class ScaffoldError(ValueError):
    pass


def finite_pair(values: list[float], field: str) -> list[float]:
    if len(values) != 2:
        raise ScaffoldError(f"{field} requires exactly two numbers")
    return values


def require_regular_file(path: Path, suffix: str, field: str) -> Path:
    if path.is_symlink():
        raise ScaffoldError(f"{field} must not be a symbolic link: {path}")
    resolved = path.resolve()
    if not resolved.is_file():
        raise ScaffoldError(f"{field} must be a regular file: {path}")
    if resolved.suffix.lower() != suffix:
        raise ScaffoldError(f"{field} must end in {suffix}: {path}")
    return resolved


def provenance(arguments: argparse.Namespace) -> dict[str, object]:
    license_values = [arguments.license_id, arguments.license_name, arguments.license_url]
    rights_values = [arguments.rights_statement, arguments.rights_url]
    has_license = any(license_values)
    has_rights = any(rights_values)
    if has_license == has_rights:
        raise ScaffoldError("provide exactly one complete license or rights statement")
    if has_license and not all(license_values):
        raise ScaffoldError("--license-id, --license-name, and --license-url are required together")
    if has_rights and not all(rights_values):
        raise ScaffoldError("--rights-statement and --rights-url are required together")

    value: dict[str, object] = {
        "formatVersion": 1,
        "creatorOrAgency": arguments.creator,
        "requestedCredit": arguments.requested_credit,
        "modificationNotes": arguments.modification_notes,
        "aiGenerated": arguments.ai_provider is not None,
    }
    if arguments.source_page_url:
        value["sourcePageURL"] = arguments.source_page_url
    if arguments.original_asset_url:
        value["originalAssetURL"] = arguments.original_asset_url
    if has_license:
        value["license"] = {
            "identifier": arguments.license_id,
            "name": arguments.license_name,
            "url": arguments.license_url,
        }
    else:
        value["rights"] = {
            "statement": arguments.rights_statement,
            "url": arguments.rights_url,
        }
    if arguments.ai_provider:
        value["aiProvider"] = arguments.ai_provider
    return value


def room_metadata(arguments: argparse.Namespace) -> dict[str, object]:
    room: dict[str, object] = {
        "formatVersion": 1,
        "displayName": arguments.display_name,
        "caption": arguments.caption,
        "previewCamera": {
            "yawDegrees": arguments.preview_yaw,
            "pitchDegrees": arguments.preview_pitch,
            "zoom": arguments.preview_zoom,
        },
        "seatedOrigin": {
            "translationMeters": [0, 0, 0],
            "orientationXYZW": [0, 0, 0, 1],
        },
        "safeHeadVolume": {
            "centerMeters": [0, arguments.safe_head_center_y, 0],
            "sizeMeters": arguments.safe_head_size,
        },
        "viewOpenings": [{
            "id": arguments.opening_id,
            "transform": {
                "translationMeters": arguments.opening_translation,
                "orientationXYZW": [0, 0, 0, 1],
            },
            "widthMeters": arguments.opening_width,
            "heightMeters": arguments.opening_height,
        }],
    }

    walls = arguments.wall_entity or []
    roofs = arguments.roof_entity or []
    desks = ({arguments.seat_id: arguments.desk_entity}
             if arguments.desk_entity else {})
    if walls or roofs or desks:
        room["spatialAdaptation"] = {
            "wallEntities": walls,
            "roofEntities": roofs,
            "deskEntitiesByTeleportID": desks,
        }

    if bool(arguments.light_body) != bool(arguments.light_anchor):
        raise ScaffoldError("--light-body and --light-anchor are required together")
    if arguments.baked_indirect_entity and not arguments.light_body:
        raise ScaffoldError("--baked-indirect-entity requires a declared light")
    if arguments.light_body:
        room["formatVersion"] = 3 if arguments.baked_indirect_entity else 2
        lighting: dict[str, object] = {
            "luminaireGroups": [{
                "id": arguments.light_id,
                "displayName": arguments.light_name,
                "entities": [arguments.light_body],
                "authoredColor": {
                    "mode": "temperature",
                    "kelvin": arguments.light_temperature,
                },
                "controls": {
                    "brightnessEVRange": [-4, 1],
                    "temperatureKelvinRange": [2000, 6500],
                    "supportsFullColor": False,
                },
                "proxy": {
                    "type": "spot",
                    "anchorEntity": arguments.light_anchor,
                    "intensityLumens": arguments.light_lumens,
                    "attenuationRadiusMeters": arguments.light_radius,
                    "colorTemperatureKelvin": arguments.light_temperature,
                    "innerAngleDegrees": arguments.light_inner_angle,
                    "outerAngleDegrees": arguments.light_outer_angle,
                    "castsShadow": False,
                },
            }]
        }
        if arguments.baked_indirect_entity:
            lighting["bakedIndirect"] = {
                "entities": [arguments.baked_indirect_entity]
            }
        room["lighting"] = lighting
    return room


def teleports(arguments: argparse.Namespace) -> dict[str, object]:
    anchor = finite_pair(arguments.seat_anchor, "--seat-anchor")
    if not all(0 <= value <= 1 for value in anchor):
        raise ScaffoldError("--seat-anchor values must be between 0 and 1")
    return {
        "formatVersion": 1,
        "points": [{
            "id": arguments.seat_id,
            "title": arguments.seat_title,
            "anchorXZ": anchor,
            "sourceFloorOffset": arguments.source_floor_offset,
            "eyeHeight": arguments.eye_height,
            "yawRadians": arguments.yaw_radians,
        }],
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scaffold(arguments: argparse.Namespace) -> Path:
    scene = require_regular_file(arguments.scene, ".usdz", "--scene")
    thumbnail = require_regular_file(arguments.thumbnail, ".jpg", "--thumbnail")
    destination = arguments.destination.absolute()
    if destination.exists():
        raise ScaffoldError(f"refusing to overwrite {destination}")
    if not destination.parent.is_dir():
        raise ScaffoldError(f"destination parent does not exist: {destination.parent}")

    temporary = destination.parent / f".{destination.name}.scaffolding-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        write_json(temporary / "space.json", room_metadata(arguments))
        write_json(temporary / "teleport-points.json", teleports(arguments))
        write_json(temporary / "provenance.json", provenance(arguments))
        shutil.copyfile(scene, temporary / "scene.usdz")
        shutil.copyfile(thumbnail, temporary / "thumbnail.jpg")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("destination", type=Path)
    value.add_argument("--scene", type=Path, required=True)
    value.add_argument("--thumbnail", type=Path, required=True)
    value.add_argument("--display-name", required=True)
    value.add_argument("--caption", required=True)
    value.add_argument("--creator", required=True)
    value.add_argument("--requested-credit", required=True)
    value.add_argument("--modification-notes", required=True)
    value.add_argument("--source-page-url")
    value.add_argument("--original-asset-url")
    value.add_argument(
        "--ai-provider",
        help="Generative AI provider only; omit DCC, renderer, and export tools",
    )
    value.add_argument("--license-id")
    value.add_argument("--license-name")
    value.add_argument("--license-url", help="Page for the named license")
    value.add_argument("--rights-statement")
    value.add_argument("--rights-url", help="Page that publishes the exact rights statement")

    value.add_argument("--seat-id", default="seat.primary")
    value.add_argument("--seat-title", default="Primary Seat")
    value.add_argument("--seat-anchor", type=float, nargs=2, default=[0.5, 0.5])
    value.add_argument("--source-floor-offset", type=float, default=0)
    value.add_argument("--eye-height", type=float, default=1.15)
    value.add_argument("--yaw-radians", type=float, default=0)
    value.add_argument("--safe-head-center-y", type=float, default=1.2)
    value.add_argument("--safe-head-size", type=float, nargs=3, default=[1.2, 0.8, 1.2])

    value.add_argument("--opening-id", default="surroundings")
    value.add_argument("--opening-translation", type=float, nargs=3, default=[0, 1.4, -2])
    value.add_argument("--opening-width", type=float, default=4)
    value.add_argument("--opening-height", type=float, default=2.5)
    value.add_argument("--preview-yaw", type=float, default=0)
    value.add_argument("--preview-pitch", type=float, default=-8)
    value.add_argument("--preview-zoom", type=float, default=0.8)

    value.add_argument("--wall-entity", action="append")
    value.add_argument("--roof-entity", action="append")
    value.add_argument("--desk-entity")
    value.add_argument("--light-id", default="primary-pendant")
    value.add_argument("--light-name", default="Primary Pendant")
    value.add_argument("--light-body")
    value.add_argument("--light-anchor")
    value.add_argument("--light-temperature", type=float, default=2700)
    value.add_argument("--light-lumens", type=float, default=900)
    value.add_argument("--light-radius", type=float, default=3.5)
    value.add_argument("--light-inner-angle", type=float, default=30)
    value.add_argument("--light-outer-angle", type=float, default=70)
    value.add_argument("--baked-indirect-entity")
    return value


def main(argv: list[str] | None = None) -> int:
    try:
        output = scaffold(parser().parse_args(argv))
    except (OSError, ScaffoldError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    print(f"CREATED: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
