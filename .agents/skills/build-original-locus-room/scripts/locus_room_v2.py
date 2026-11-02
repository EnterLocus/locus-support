#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Derive Package v2 Room seats from an exported USDZ.

Run ``bounds`` with Blender's bundled Python (or another Python with ``pxr``)
to measure the *exported* USDZ.  The other commands work with Python 3.9+.

  bounds SCENE.usdz
  seats --bounds-json BOUNDS.json --seats SEATS.json --house-id SPACE_ID
  eye-points --bounds-json BOUNDS.json --teleports TELEPORTS.json
  convert-points OLD-TELEPORTS.json --house-id SPACE_ID

``seats`` accepts author-friendly floor or eye coordinates and calculates
``anchorXZ`` and ``sourceFloorOffset`` in the delivered model's coordinate
system.  ``convert-points`` changes a legacy flat ``points`` document into the
Package v2 ``houses`` document without changing individual records.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
DIGITS = 6
Bounds = Tuple[Tuple[float, float, float], Tuple[float, float, float]]


class HelperError(ValueError):
    """An input problem the Room author can repair."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise HelperError(f"{path} does not exist") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HelperError(f"{path} is not valid UTF-8 JSON: {error}") from error


def write_new(path: Optional[Path], value: Any) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if path is None:
        sys.stdout.write(text)
    elif path.exists():
        raise HelperError(f"refusing to overwrite {path}")
    else:
        path.write_text(text, encoding="utf-8")


def rounded(value: float) -> float:
    result = round(value, DIGITS)
    return 0.0 if result == 0 else result


def numbers(value: Any, count: int, context: str) -> List[float]:
    if (not isinstance(value, (list, tuple)) or len(value) != count or
            not all(type(item) in (int, float) and math.isfinite(item) for item in value)):
        raise HelperError(f"{context} must be {count} finite numbers")
    return [float(item) for item in value]


def number(value: Any, context: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise HelperError(f"{context} must be a finite number")
    return float(value)


def identifier(value: Any, context: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or len(value.encode()) > 128:
        raise HelperError(f"{context} must use letters, digits, '.', '_' or '-', and start with a letter or digit")
    return value


def checked_bounds(value: Any, context: str) -> Bounds:
    try:
        low, high = value
    except (TypeError, ValueError) as error:
        raise HelperError(f"{context} must contain [[minX, minY, minZ], [maxX, maxY, maxZ]]") from error
    minimum = tuple(numbers(low, 3, f"{context}.min"))
    maximum = tuple(numbers(high, 3, f"{context}.max"))
    for axis, (minimum_value, maximum_value) in enumerate(zip(minimum, maximum)):
        if maximum_value - minimum_value <= 1e-4:
            raise HelperError(f"{context} is degenerate on {'XYZ'[axis]}")
    return minimum, maximum


def scene_bounds(scene: Path) -> Bounds:
    try:
        from pxr import Usd, UsdGeom  # type: ignore
    except ImportError as error:  # pragma: no cover - host dependency
        raise HelperError(
            "pxr is unavailable. Run this with Blender's bundled Python or install usd-core; "
            "use a saved bounds JSON for later commands.") from error
    stage = Usd.Stage.Open(str(scene))
    if stage is None:
        raise HelperError(f"cannot open {scene}")
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.y:
        raise HelperError(f"{scene} is not +Y up")
    if not math.isclose(UsdGeom.GetStageMetersPerUnit(stage), 1.0, rel_tol=1e-6):
        raise HelperError(f"{scene} is not meter scale")
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    bounds = cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
    if bounds.IsEmpty():
        raise HelperError(f"{scene} has no renderable geometry")
    return checked_bounds((tuple(bounds.GetMin()), tuple(bounds.GetMax())), str(scene))


def load_bounds(arguments: argparse.Namespace) -> Bounds:
    if arguments.bounds_json:
        document = read_json(arguments.bounds_json)
        if isinstance(document, dict):
            document = [document.get("min"), document.get("max")]
        return checked_bounds(document, str(arguments.bounds_json))
    if arguments.scene:
        return scene_bounds(arguments.scene)
    raise HelperError("pass --scene or --bounds-json")


def blender_to_usd(point: List[float]) -> List[float]:
    """Blender Z-up coordinates as exported by Blender: (x, y, z) -> (x, z, -y)."""
    return [point[0], point[2], -point[1]]


def yaw_from_direction(x: float, z: float, context: str) -> float:
    if math.hypot(x, z) < 1e-6:
        raise HelperError(f"{context} has no horizontal facing direction")
    return math.atan2(x, -z)


def seat_record(value: Any, index: int, bounds: Bounds, frame: str) -> Dict[str, Any]:
    context = f"seats[{index}]"
    if not isinstance(value, dict):
        raise HelperError(f"{context} must be an object")
    convert = blender_to_usd if frame == "blender" else lambda point: point
    seat_id = identifier(value.get("id"), f"{context}.id")
    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        raise HelperError(f"{context}.title must be non-empty text")
    eye_height = number(value.get("eyeHeight"), f"{context}.eyeHeight")
    if eye_height <= 0:
        raise HelperError(f"{context}.eyeHeight must be positive")
    has_floor, has_eye = "floor" in value, "eye" in value
    if has_floor == has_eye:
        raise HelperError(f"{context} needs exactly one of floor or eye")
    if has_floor:
        floor = convert(numbers(value["floor"], 3, f"{context}.floor"))
    else:
        eye = convert(numbers(value["eye"], 3, f"{context}.eye"))
        floor = [eye[0], eye[1] - eye_height, eye[2]]
    facing = [key for key in ("yawRadians", "lookAt", "facing") if key in value]
    if len(facing) != 1:
        raise HelperError(f"{context} needs exactly one of yawRadians, lookAt or facing")
    if facing[0] == "yawRadians":
        yaw = number(value["yawRadians"], f"{context}.yawRadians")
    elif facing[0] == "lookAt":
        target = convert(numbers(value["lookAt"], 3, f"{context}.lookAt"))
        yaw = yaw_from_direction(target[0] - floor[0], target[2] - floor[2], context)
    else:
        direction = convert(numbers(value["facing"], 3, f"{context}.facing"))
        yaw = yaw_from_direction(direction[0], direction[2], context)
    minimum, maximum = bounds
    anchor = [(floor[0] - minimum[0]) / (maximum[0] - minimum[0]),
              (floor[2] - minimum[2]) / (maximum[2] - minimum[2])]
    if not all(0 <= item <= 1 for item in anchor):
        raise HelperError(f"{context} ({seat_id}) lies outside the delivered USDZ X/Z bounds")
    floor_offset = floor[1] - minimum[1]
    if floor_offset < -1e-6:
        raise HelperError(f"{context} ({seat_id}) is below the delivered USDZ floor")
    if floor[1] + eye_height > maximum[1] + 1e-6:
        print(f"warning: {seat_id} eye point is above the delivered USDZ bounds", file=sys.stderr)
    return {
        "id": seat_id, "title": title, "anchorXZ": [rounded(item) for item in anchor],
        "sourceFloorOffset": rounded(max(0.0, floor_offset)), "eyeHeight": rounded(eye_height),
        "yawRadians": rounded(math.atan2(math.sin(yaw), math.cos(yaw))),
    }


def seat_records(document: Any, bounds: Bounds, frame: str) -> List[Dict[str, Any]]:
    seats = document.get("seats") if isinstance(document, dict) else None
    if not isinstance(seats, list) or not seats:
        raise HelperError('seat specification needs a non-empty "seats" array')
    records = [seat_record(seat, index, bounds, frame) for index, seat in enumerate(seats)]
    if len({record["id"] for record in records}) != len(records):
        raise HelperError("seat IDs must be unique")
    return records


def flat_points(document: Any) -> List[Dict[str, Any]]:
    points = document.get("points") if isinstance(document, dict) else None
    if not isinstance(points, list) or not points:
        raise HelperError('expected a flat teleport document with a non-empty "points" array')
    result: List[Dict[str, Any]] = []
    seen = set()
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            raise HelperError(f"points[{index}] must be an object")
        point_id = identifier(point.get("id"), f"points[{index}].id")
        if point_id in seen:
            raise HelperError(f"duplicate teleport point ID {point_id}")
        seen.add(point_id)
        result.append(point)
    return result


def v2_points(document: Any, house_id: Optional[str]) -> List[Dict[str, Any]]:
    houses = document.get("houses") if isinstance(document, dict) else None
    if not isinstance(houses, dict) or not houses:
        raise HelperError('expected a Package v2 teleport document with "houses"')
    if house_id is None:
        if len(houses) != 1:
            raise HelperError("the teleport document has several houses; pass --house-id")
        house_id = next(iter(houses))
    points = houses.get(house_id)
    if not isinstance(points, list):
        raise HelperError(f"the teleport document has no house named {house_id}")
    return points


def eye_points(points: List[Dict[str, Any]], bounds: Bounds) -> List[Dict[str, Any]]:
    minimum, maximum = bounds
    result = []
    for index, point in enumerate(points):
        context = f"teleport point {index}"
        anchor = numbers(point.get("anchorXZ"), 2, f"{context}.anchorXZ")
        floor_offset = number(point.get("sourceFloorOffset"), f"{context}.sourceFloorOffset")
        eye_height = number(point.get("eyeHeight"), f"{context}.eyeHeight")
        yaw = number(point.get("yawRadians"), f"{context}.yawRadians")
        floor = [minimum[0] + anchor[0] * (maximum[0] - minimum[0]), minimum[1] + floor_offset,
                 minimum[2] + anchor[1] * (maximum[2] - minimum[2])]
        eye = [floor[0], floor[1] + eye_height, floor[2]]
        result.append({"id": point.get("id"), "title": point.get("title"),
                       "eye": [rounded(item) for item in eye],
                       "facing": [rounded(math.sin(yaw)), 0.0, rounded(-math.cos(yaw))]})
    return result


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = command_parser.add_subparsers(dest="command", required=True)
    bounds = commands.add_parser("bounds", help="print the delivered USDZ visual bounds")
    bounds.add_argument("scene", type=Path)
    def bounds_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("--scene", type=Path, help="delivered scene.usdz")
        command.add_argument("--bounds-json", type=Path, help="saved output from bounds")
    seats = commands.add_parser("seats", help="derive Package v2 teleport records")
    bounds_options(seats)
    seats.add_argument("--seats", required=True, type=Path, help="author seat specification JSON")
    seats.add_argument("--house-id", required=True)
    seats.add_argument("--frame", choices=("usd", "blender"), default="usd")
    seats.add_argument("--output", type=Path)
    eyes = commands.add_parser("eye-points", help="print review camera eye points")
    bounds_options(eyes)
    eyes.add_argument("--teleports", required=True, type=Path)
    eyes.add_argument("--house-id")
    convert = commands.add_parser("convert-points", help="convert flat points to Package v2 houses")
    convert.add_argument("teleports", type=Path)
    convert.add_argument("--house-id", required=True)
    convert.add_argument("--output", type=Path)
    return command_parser


def run(arguments: argparse.Namespace) -> None:
    if arguments.command == "bounds":
        minimum, maximum = scene_bounds(arguments.scene)
        write_new(None, {"min": [rounded(item) for item in minimum], "max": [rounded(item) for item in maximum],
                         "size": [rounded(upper - lower) for lower, upper in zip(minimum, maximum)]})
    elif arguments.command == "seats":
        house_id = identifier(arguments.house_id, "--house-id")
        points = seat_records(read_json(arguments.seats), load_bounds(arguments), arguments.frame)
        write_new(arguments.output, {"houses": {house_id: points}})
    elif arguments.command == "eye-points":
        document = read_json(arguments.teleports)
        points = flat_points(document) if isinstance(document, dict) and "points" in document else v2_points(document, arguments.house_id)
        write_new(None, eye_points(points, load_bounds(arguments)))
    elif arguments.command == "convert-points":
        house_id = identifier(arguments.house_id, "--house-id")
        write_new(arguments.output, {"houses": {house_id: flat_points(read_json(arguments.teleports))}})


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        run(arguments)
    except HelperError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
