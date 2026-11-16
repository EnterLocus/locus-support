"""Validation shared by Room View-ground footprint producers and readers."""

from __future__ import annotations

import math
from typing import Any


CAPABILITY = "locus.room.view-ground-footprint.v1"
HEIGHT_CAPABILITY = "locus.room.view-ground-footprint-height.v1"
MINIMUM_APP = (1, 4, 5)
MAXIMUM_POLYGONS = 32
MAXIMUM_VERTICES_PER_POLYGON = 128
MAXIMUM_TOTAL_VERTICES = 512
MAXIMUM_COORDINATE_METERS = 200
GEOMETRY_EPSILON = 1e-9
MINIMUM_TWICE_AREA = 1e-6


class FootprintValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FootprintValidationError(message)


def _point(value: Any, context: str) -> tuple[float, float]:
    _require(isinstance(value, list) and len(value) == 2,
             context + " must contain exactly two coordinates")
    x, z = value
    for coordinate, axis in ((x, "x"), (z, "z")):
        _require(
            type(coordinate) in (int, float) and math.isfinite(coordinate)
            and abs(coordinate) <= MAXIMUM_COORDINATE_METERS,
            context + "." + axis + " must be a finite number within [-200, 200]",
        )
    return (x, z)


def _orientation(first: tuple[float, float], second: tuple[float, float],
                 third: tuple[float, float]) -> float:
    return ((second[0] - first[0]) * (third[1] - first[1])
            - (second[1] - first[1]) * (third[0] - first[0]))


def _on_segment(first: tuple[float, float], second: tuple[float, float],
                point: tuple[float, float]) -> bool:
    return (min(first[0], second[0]) - GEOMETRY_EPSILON <= point[0]
            <= max(first[0], second[0]) + GEOMETRY_EPSILON
            and min(first[1], second[1]) - GEOMETRY_EPSILON <= point[1]
            <= max(first[1], second[1]) + GEOMETRY_EPSILON)


def _segments_intersect(first_start: tuple[float, float], first_end: tuple[float, float],
                        second_start: tuple[float, float], second_end: tuple[float, float]) -> bool:
    first_second_start = _orientation(first_start, first_end, second_start)
    first_second_end = _orientation(first_start, first_end, second_end)
    second_first_start = _orientation(second_start, second_end, first_start)
    second_first_end = _orientation(second_start, second_end, first_end)
    if ((first_second_start > GEOMETRY_EPSILON
         and first_second_end < -GEOMETRY_EPSILON
         or first_second_start < -GEOMETRY_EPSILON
         and first_second_end > GEOMETRY_EPSILON)
            and (second_first_start > GEOMETRY_EPSILON
                 and second_first_end < -GEOMETRY_EPSILON
                 or second_first_start < -GEOMETRY_EPSILON
                 and second_first_end > GEOMETRY_EPSILON)):
        return True
    return ((abs(first_second_start) <= GEOMETRY_EPSILON
             and _on_segment(first_start, first_end, second_start))
            or (abs(first_second_end) <= GEOMETRY_EPSILON
                and _on_segment(first_start, first_end, second_end))
            or (abs(second_first_start) <= GEOMETRY_EPSILON
                and _on_segment(second_start, second_end, first_start))
            or (abs(second_first_end) <= GEOMETRY_EPSILON
                and _on_segment(second_start, second_end, first_end)))


def _validate_polygon(value: Any, context: str) -> int:
    _require(isinstance(value, list) and 3 <= len(value) <= MAXIMUM_VERTICES_PER_POLYGON,
             context + " must contain 3..128 vertices")
    points = [_point(vertex, context + "[%d]" % index)
              for index, vertex in enumerate(value)]
    _require(len(set(points)) == len(points),
             context + " must not repeat vertices or contain zero-length edges")
    area_twice = math.fsum(
        point[0] * points[(index + 1) % len(points)][1]
        - point[1] * points[(index + 1) % len(points)][0]
        for index, point in enumerate(points)
    )
    _require(abs(area_twice) > MINIMUM_TWICE_AREA,
             context + " must have nonzero area")
    for first_index in range(len(points)):
        first_end = (first_index + 1) % len(points)
        for second_index in range(first_index + 1, len(points)):
            second_end = (second_index + 1) % len(points)
            if (first_index in (second_index, second_end)
                    or first_end in (second_index, second_end)):
                continue
            _require(
                not _segments_intersect(
                    points[first_index], points[first_end],
                    points[second_index], points[second_end]),
                context + " has a self-intersection or non-adjacent edge touch",
            )
    return len(points)


def validate(value: Any, context: str = "viewGroundFootprint") -> None:
    """Validate the author-defined union of simple X/Z ground polygons.

    ``bottomHeightsMeters`` is optional so existing footprints retain their
    historical whole-vertical-volume behavior. When authored, each height is
    the model-local lower Y bound for the polygon at the same array index.
    """
    _require(isinstance(value, dict), context + " must be an object")
    _require(set(value) in ({"polygons"}, {"polygons", "bottomHeightsMeters"}),
             context + " must contain polygons and optional bottomHeightsMeters")
    polygons = value["polygons"]
    _require(isinstance(polygons, list) and 1 <= len(polygons) <= MAXIMUM_POLYGONS,
             context + ".polygons must contain 1..32 polygons")
    vertices = sum(
        _validate_polygon(polygon, context + ".polygons[%d]" % index)
        for index, polygon in enumerate(polygons)
    )
    _require(vertices <= MAXIMUM_TOTAL_VERTICES,
             context + ".polygons exceeds the 512 total-vertex limit")
    if "bottomHeightsMeters" in value:
        heights = value["bottomHeightsMeters"]
        _require(isinstance(heights, list) and len(heights) == len(polygons),
                 context + ".bottomHeightsMeters must contain one height per polygon")
        for index, height in enumerate(heights):
            _require(
                type(height) in (int, float) and math.isfinite(height)
                and -MAXIMUM_COORDINATE_METERS <= height <= MAXIMUM_COORDINATE_METERS,
                context + ".bottomHeightsMeters[%d] must be a finite number within [-200, 200]" % index,
            )
