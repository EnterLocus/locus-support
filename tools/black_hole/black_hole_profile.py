# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""The `blackHole` profile of a Package v2 Destination (`locus.view.black-hole.v1`).

Portable data only: field names, ranges and image formats that Locus 1.3.4
and later accepts, plus the lens-table encoding. The tutorial at
https://enterlocus.com/make-a-black-hole-view/ and `README.md` in this folder
explain each field; `bake_view.py` writes a profile that passes these checks
and `validate_view.py` applies them to a packed archive.
"""

import math

CAPABILITY = "locus.view.black-hole.v1"
MINIMUM_APP = (1, 3, 4)
LENS_DELTA = 1e-7
EXCLUDED = ("celestial", "nearOrbit", "sky", "media", "midground", "water", "fireflies", "clouds", "pointLights")

REQUIRED = {"version", "skyTexture", "lensTable", "discMap", "discTexture", "yawDegrees", "elevationDegrees",
            "observerRadius", "discMapMaxAngleDegrees", "disc", "doppler", "glow", "drift"}
OPTIONAL = {"glowTexture", "flares"}
DISC_FIELDS = {"inner", "outer", "spin", "iscoPeriodSeconds", "regenerationSeconds", "profileExponent",
               "peakTemperatureKelvin", "exposure", "textureLogSpan", "contrast"}
DRIFT_FIELDS = {"degreesPerSecond", "axis"}
DRIFT_AXES = ("up", "right", "view")
FLARE_FIELDS = {"intervalSeconds", "lifeSeconds", "brightness", "radiusRange", "width", "arcLength"}

RANGES = {
    "yawDegrees": (-180, 180), "elevationDegrees": (-60, 60), "observerRadius": (8, 200),
    "discMapMaxAngleDegrees": (1, 179), "doppler": (0, 1), "glow": (0, 2),
}
DISC_RANGES = {
    "inner": (2.5, 20), "iscoPeriodSeconds": (2, 600), "regenerationSeconds": (2, 120),
    "profileExponent": (1.5, 4), "peakTemperatureKelvin": (1500, 40000), "exposure": (0.01, 100),
    "textureLogSpan": (0.05, 5), "contrast": (0, 3),
}
FLARE_RANGES = {"intervalSeconds": (1, 600), "lifeSeconds": (0.5, 600), "brightness": (0, 50),
                "width": (0.05, 20), "arcLength": (0.1, 100)}
FLARE_RADIUS = (1.0, 4.0)
DRIFT_RANGE = (0, 2)

# Image shapes: (min width, max width) and the PNG (bit depth, colour type).
LENS_WIDTH = (256, 8192)
DISC_MAP_WIDTH = (512, 8192)
DISC_TEXTURE_SIZE = (256, 8192)
GLOW_MAX_WIDTH = 4096
SKY_MAX_WIDTH = 16384
PNG_RGB16, PNG_RGBA16, PNG_GRAY16 = (16, 2), (16, 6), (16, 0)

# Visitor controls (Edit View Motion): id -> (minimum, maximum, default or None for authored).
CONTROLS = {
    "driftSpeed": (0.0, 2.0, None), "flowSpeed": (0.25, 3.0, 1.0), "doppler": (0.0, 1.0, None),
    "glow": (0.0, 2.0, None), "flares": (0.0, 2.0, 1.0), "detail": (0.5, 2.0, 1.0), "brightness": (0.5, 2.0, 1.0),
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _in(value, bounds):
    return _number(value) and bounds[0] <= value <= bounds[1]


def _path(value):
    return isinstance(value, str) and value and not value.startswith("/") and ".." not in value.split("/")


def validate_definition(value, require):
    """Validate the profile; return {field: package path} of its images."""
    require(isinstance(value, dict), "blackHole must be an object")
    keys = set(value)
    require(REQUIRED <= keys and keys <= REQUIRED | OPTIONAL, "blackHole has missing or unknown fields")
    require(all(v is not None for v in value.values()), "blackHole fields must not be null")
    require(value["version"] == 1 and not isinstance(value["version"], bool), "blackHole.version must be 1")
    for field, bounds in RANGES.items():
        require(_in(value[field], bounds), "blackHole.%s must be %s-%s" % (field, bounds[0], bounds[1]))

    disc = value["disc"]
    require(isinstance(disc, dict) and set(disc) == DISC_FIELDS, "blackHole.disc has missing or unknown fields")
    for field, bounds in DISC_RANGES.items():
        require(_in(disc[field], bounds), "blackHole.disc.%s must be %s-%s" % (field, bounds[0], bounds[1]))
    require(_in(disc["outer"], (disc["inner"] + 1, 200)), "blackHole.disc.outer must be inner+1 to 200")
    require(disc["spin"] in (1, -1) and not isinstance(disc["spin"], bool), "blackHole.disc.spin must be 1 or -1")

    drift = value["drift"]
    require(isinstance(drift, dict) and set(drift) == DRIFT_FIELDS, "blackHole.drift has missing or unknown fields")
    require(_in(drift["degreesPerSecond"], DRIFT_RANGE), "blackHole.drift.degreesPerSecond must be 0-2")
    require(drift["axis"] in DRIFT_AXES, "blackHole.drift.axis must be up, right or view")

    if "flares" in value:
        flares = value["flares"]
        require(isinstance(flares, dict) and set(flares) == FLARE_FIELDS,
                "blackHole.flares has missing or unknown fields")
        for field, bounds in FLARE_RANGES.items():
            require(_in(flares[field], bounds), "blackHole.flares.%s must be %s-%s" % (field, bounds[0], bounds[1]))
        span = flares["radiusRange"]
        require(isinstance(span, list) and len(span) == 2 and all(_in(x, FLARE_RADIUS) for x in span)
                and span[0] <= span[1], "blackHole.flares.radiusRange must be two ascending values in 1-4")

    paths = {}
    for field in ("skyTexture", "lensTable", "discMap", "discTexture", "glowTexture"):
        if field in value:
            require(_path(value[field]), "blackHole.%s must be a relative package path" % field)
            paths[field] = value[field]
    require(len(set(paths.values())) == len(paths), "blackHole images must be distinct files")
    return paths


def validate_image(field, width, height, png_format, require):
    """Shape and PNG format of one profile image (png_format None for JPEG)."""
    if field == "skyTexture":
        require(width == 2 * height and width <= SKY_MAX_WIDTH,
                "blackHole.skyTexture must be 2:1 and at most 16384 pixels wide")
    elif field == "lensTable":
        require(png_format == PNG_RGB16 and height == 1 and LENS_WIDTH[0] <= width <= LENS_WIDTH[1],
                "blackHole.lensTable must be a 16-bit RGB PNG, 256-8192 wide and 1 high")
    elif field == "discMap":
        require(png_format == PNG_RGBA16 and width == 2 * height and DISC_MAP_WIDTH[0] <= width <= DISC_MAP_WIDTH[1],
                "blackHole.discMap must be a 2:1 16-bit RGBA PNG, 512-8192 wide")
    elif field == "discTexture":
        require(png_format == PNG_GRAY16 and all(DISC_TEXTURE_SIZE[0] <= x <= DISC_TEXTURE_SIZE[1]
                                                  for x in (width, height)),
                "blackHole.discTexture must be a 16-bit grayscale PNG, 256-8192 per side")
    elif field == "glowTexture":
        require(png_format == PNG_RGB16 and width == 2 * height and width <= GLOW_MAX_WIDTH,
                "blackHole.glowTexture must be a 2:1 16-bit RGB PNG at most 4096 wide")


def critical_alpha(observer_radius):
    return math.asin(3 * math.sqrt(3) * math.sqrt(1 - 2 / observer_radius) / observer_radius)


def lens_k(observer_radius):
    a_c = critical_alpha(observer_radius)
    return math.log((math.pi - a_c) / LENS_DELTA)


def encode_lens(phi):
    """phi (radians, 0..8pi) -> (R16, G16) hi/lo codes."""
    q = int(round(min(max(phi / (8 * math.pi), 0.0), 1.0) * (2 ** 32 - 1)))
    return q >> 16, q & 0xFFFF


def decode_lens(r16, g16):
    return 8 * math.pi * (r16 * 65536 + g16) / (2 ** 32 - 1)
