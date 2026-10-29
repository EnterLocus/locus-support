"""Portable `locus-point-lights` v1 View-table validation."""
import math


CAPABILITY = "locus.view.point-lights.v1"
MINIMUM_APP = (1, 2, 5)
TABLE_FILENAME = "point-lights.json"
MAXIMUM_BYTES = 1_048_576


def validate_definition(value, require):
    require(isinstance(value, dict) and set(value) == {"table"},
            "invalid pointLights fields")
    require(value["table"] == TABLE_FILENAME,
            "pointLights.table must be point-lights.json")
    return value["table"]


def validate_table(value, require):
    require(isinstance(value, dict)
            and set(value) == {"format", "version", "groups"},
            "invalid point-lights table fields")
    require(value["format"] == "locus-point-lights" and type(value["version"]) is int
            and value["version"] == 1,
            "unsupported point-lights table version")
    groups = value["groups"]
    require(isinstance(groups, list) and 1 <= len(groups) <= 64,
            "point-lights group limit")
    group_ids = set()
    total = 0
    for group in groups:
        require(isinstance(group, dict)
                and set(group) == {"id", "color", "behavior", "lights"},
                "invalid point-lights group fields")
        identifier = group["id"]
        require(isinstance(identifier, str) and 0 < len(identifier.encode("utf-8")) <= 80
                and identifier not in group_ids,
                "invalid point-lights group id")
        group_ids.add(identifier)
        color = group["color"]
        require(isinstance(color, list) and len(color) == 3 and all(_number(v, 0, 1) for v in color),
                "point-lights color must have three finite values between 0 and 1")
        _validate_behavior(group["behavior"], require)
        lights = group["lights"]
        require(isinstance(lights, list), "point-lights lights must be an array")
        total += len(lights)
        for row in lights:
            require(isinstance(row, list) and len(row) == 4
                    and _number(row[0], 0, 1, upper_open=True)
                    and _number(row[1], 0, 1)
                    and _number(row[2], .001, .5)
                    and _number(row[3], 0, 4),
                    "invalid point-lights row")
    require(1 <= total <= 4000, "point-lights light limit")


def _validate_behavior(value, require):
    require(isinstance(value, dict) and isinstance(value.get("type"), str),
            "invalid point-lights behavior")
    if value["type"] == "blink":
        require(set(value) == {"type", "periodSeconds", "phaseSeconds", "minimum", "softness"},
                "invalid blink fields")
        period = value["periodSeconds"]
        phase = value["phaseSeconds"]
        require(_number(period, 1, 20) and _number(phase, 0, period, upper_open=True)
                and _number(value["minimum"], 0, 1) and _number(value["softness"], .2, 4),
                "invalid blink behavior")
    elif value["type"] == "twinkle":
        require(set(value) == {"type", "amplitude", "speed"}, "invalid twinkle fields")
        require(_number(value["amplitude"], 0, .3) and _number(value["speed"], .05, 2),
                "invalid twinkle behavior")
    else:
        require(False, "unsupported point-lights behavior")


def _number(value, lower, upper, upper_open=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and lower <= value < upper if upper_open else
            type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper)
