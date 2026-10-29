"""Strict Package-v2 contract for environment.sunPath."""

import math

MINIMUM_APP = (1, 3, 0)
CAPABILITY = "locus.view.sun-path.v1"
DISC_SIZE_RANGE = (0.001, 5)


DEFAULTS = {
    "startHour": 9,
    "dayDurationSeconds": 3600,
    "maxElevationDegrees": 60,
    "peakIlluminanceLux": 60000,
    "nightIlluminanceLux": 0,
}
RANGES = {
    "startHour": (0, 24),
    "dayDurationSeconds": (60, 86400),
    "maxElevationDegrees": (10, 85),
    "peakIlluminanceLux": (0, 120000),
    "nightIlluminanceLux": (0, 1000),
}


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _png_path(value):
    return (
        isinstance(value, str)
        and value
        and not value.startswith("/")
        and not any(ord(char) < 32 for char in value)
        and not any(part in ("", ".", "..") for part in value.split("/"))
        and value.lower().endswith(".png")
    )


def validate_definition(value, require, asset, field="environment.sunPath"):
    require(isinstance(value, dict), field + " must be an object")
    require(
        not set(value) - {"sunFreeSky", "disc"} - set(RANGES),
        field + " has unsupported fields",
    )
    require("sunFreeSky" in value and type(value["sunFreeSky"]) is bool and value["sunFreeSky"],
            field + ".sunFreeSky must be true")
    for key, (low, high) in RANGES.items():
        require(_number(value.get(key, DEFAULTS[key]), low, high), field + "." + key + " is out of range")
    if "disc" in value:
        validate_disc(value["disc"], require, asset, field + ".disc")
    return value


def validate_disc(disc, require, asset, field="environment.sunPath.disc"):
    require(isinstance(disc, dict), field + " must be an object")
    require(
        not set(disc) - {"enabled", "skyMask", "angularSizeDegrees", "intensity", "color"},
        field + " has unsupported fields",
    )
    require(type(disc.get("enabled", True)) is bool, field + ".enabled must be a boolean")
    require("skyMask" in disc and _png_path(disc["skyMask"]), field + ".skyMask has invalid PNG path")
    asset(disc["skyMask"], field + ".skyMask", grayscale=True)
    require(_number(disc.get("angularSizeDegrees", 0.53), *DISC_SIZE_RANGE),
            field + ".angularSizeDegrees is out of range")
    require(_number(disc.get("intensity", 1), 0, 20), field + ".intensity is out of range")
    if "color" in disc:
        color = disc["color"]
        require(
            isinstance(color, list) and len(color) == 3
            and all(_number(channel, 0, 1) for channel in color),
            field + ".color is invalid",
        )
    return disc
