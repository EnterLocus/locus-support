"""Strict Package-v2 contract for a View's computed surf and open sea (`shore`).

Mirrors `ShoreDefinition` in the viewer (viewer/LocusViewer/Models/ShoreDefinition.swift).
Every field except `light.follow`, `frame` and `bed` is required, unknown keys and
JSON null are invalid, and colours are linear RGB triples. The only package asset
is the optional `bed.path` image, checked by `validate_bed_image`.
"""

import math

MINIMUM_APP = (1, 4, 9)
CAPABILITY = "locus.view.water.surf.v1"
WET_BAND_MINIMUM_APP = (1, 4, 10)
WET_BAND_CAPABILITY = "locus.view.water.surf.wet-band.v1"
PANORAMA_BLEND_MINIMUM_APP = (1, 4, 11)
PANORAMA_BLEND_CAPABILITY = "locus.view.water.surf.panorama-blend.v1"
# `light.follow` (optional): the live light the surf follows. "none" is the default.
FOLLOW = ("none", "moon", "sun")

# Inclusive ranges, identical to ShoreDefinition.Range.
SWELL_HEIGHT = (0.35, 1.65)
SWELL_PERIOD = (0.85, 1.15)
WIND_CHOP = (0.0, 1.6)
CURL = (0.0, 1.6)
AZIMUTH_DEGREES = (-180.0, 180.0)
ELEVATION_DEGREES = (5.0, 75.0)
LIGHT_COLOR = (0.0, 2.0)
NIGHT = (0.0, 1.0)
SKY_COLOR = (0.0, 1.0)
WATER_COLOR = (0.0, 1.0)
ABSORPTION = (0.0, 10.0)
CLARITY = (0.5, 1.6)
SAND_COLOR = (0.0, 1.0)
FOAM = (0.25, 1.6)
SPARKLE = (0.0, 1.8)
EXPOSURE = (0.5, 2.0)
# `frame` (optional): where the shore frame sits in the View.
FRAME_HORIZONTAL = (-150.0, 150.0)
FRAME_HEIGHT = (-200.0, 0.5)
YAW_DEGREES = (-180.0, 180.0)
# `bed` (optional): the author's terrain, a 16-bit greyscale PNG.
BED_SIZE = (8.0, 4000.0)
BED_CENTER = (-4000.0, 4000.0)
BED_HEIGHT = (-200.0, 200.0)
BED_PIXELS = (2, 2048)

# Root keys a shore View may not declare alongside it: one computed sea per View.
EXCLUSIVE_WITH = ("water", "celestial", "nearOrbit", "blackHole")


def _number(value, bounds):
    return (type(value) in (int, float) and math.isfinite(value)
            and bounds[0] <= value <= bounds[1])


def _color(value, bounds):
    return isinstance(value, list) and len(value) == 3 and all(_number(item, bounds) for item in value)


def _pair(value, bounds):
    return isinstance(value, list) and len(value) == 2 and all(_number(item, bounds) for item in value)


def _object(value, fields, field, require, optional=()):
    require(isinstance(value, dict), field + " must be an object")
    unknown = sorted(set(value) - set(fields) - set(optional))
    require(not unknown, field + " has unsupported field " + (unknown[0] if unknown else ""))
    missing = [name for name in fields if name not in value]
    require(not missing, field + " is missing required field " + (missing[0] if missing else ""))
    for name in tuple(fields) + tuple(name for name in optional if name in value):
        require(value[name] is not None, field + "." + name + " must not be null")


def validate_definition(value, require, field="shore"):
    """Validate a `shore` declaration (the `bed` image itself is `validate_bed_image`'s)."""
    _object(value, ("version", "swell", "light", "sky", "water", "sand",
                    "foam", "sparkle", "exposure"), field, require, optional=("frame", "bed"))
    require(type(value["version"]) is int and value["version"] == 1, field + ".version must be 1")

    swell = value["swell"]
    _object(swell, ("height", "period", "windChop", "curl"), field + ".swell", require)
    for name, bounds in (("height", SWELL_HEIGHT), ("period", SWELL_PERIOD),
                         ("windChop", WIND_CHOP), ("curl", CURL)):
        require(_number(swell[name], bounds), "%s.swell.%s is out of range" % (field, name))

    light = value["light"]
    _object(light, ("azimuthDegrees", "elevationDegrees", "color", "night"), field + ".light", require,
            optional=("follow",))
    require(_number(light["azimuthDegrees"], AZIMUTH_DEGREES), field + ".light.azimuthDegrees is out of range")
    require(_number(light["elevationDegrees"], ELEVATION_DEGREES), field + ".light.elevationDegrees is out of range")
    require(_color(light["color"], LIGHT_COLOR), field + ".light.color is invalid")
    require(_number(light["night"], NIGHT), field + ".light.night is out of range")
    require(light.get("follow", "none") in FOLLOW, field + ".light.follow must be none, moon or sun")

    sky = value["sky"]
    _object(sky, ("zenith", "horizon"), field + ".sky", require)
    for name in ("zenith", "horizon"):
        require(_color(sky[name], SKY_COLOR), "%s.sky.%s is invalid" % (field, name))

    water = value["water"]
    _object(water, ("deep", "shallowScatter", "crestScatter", "absorption", "clarity"),
            field + ".water", require)
    for name in ("deep", "shallowScatter", "crestScatter"):
        require(_color(water[name], WATER_COLOR), "%s.water.%s is invalid" % (field, name))
    require(_color(water["absorption"], ABSORPTION), field + ".water.absorption is invalid")
    require(_number(water["clarity"], CLARITY), field + ".water.clarity is out of range")

    sand = value["sand"]
    _object(sand, ("dry", "wet"), field + ".sand", require, optional=("wetBand",))
    for name in ("dry", "wet"):
        require(_color(sand[name], SAND_COLOR), "%s.sand.%s is invalid" % (field, name))
    if "wetBand" in sand:
        require(type(sand["wetBand"]) is bool, field + ".sand.wetBand must be a boolean")

    for name, bounds in (("foam", FOAM), ("sparkle", SPARKLE), ("exposure", EXPOSURE)):
        require(_number(value[name], bounds), "%s.%s is out of range" % (field, name))

    if "frame" in value:
        frame = value["frame"]
        _object(frame, ("translationMeters", "yawDegrees"), field + ".frame", require)
        translation = frame["translationMeters"]
        require(isinstance(translation, list) and len(translation) == 3
                and _number(translation[0], FRAME_HORIZONTAL) and _number(translation[1], FRAME_HEIGHT)
                and _number(translation[2], FRAME_HORIZONTAL),
                field + ".frame.translationMeters is out of range")
        require(_number(frame["yawDegrees"], YAW_DEGREES), field + ".frame.yawDegrees is out of range")

    if "bed" in value:
        bed = value["bed"]
        _object(bed, ("path", "sizeMeters", "centerMeters", "heightRangeMeters"), field + ".bed", require)
        require(isinstance(bed["path"], str) and bed["path"].lower().endswith(".png"),
                field + ".bed.path must be a .png file")
        require(_pair(bed["sizeMeters"], BED_SIZE), field + ".bed.sizeMeters is out of range")
        require(_pair(bed["centerMeters"], BED_CENTER), field + ".bed.centerMeters is out of range")
        heights = bed["heightRangeMeters"]
        require(_pair(heights, BED_HEIGHT) and heights[0] < heights[1],
                field + ".bed.heightRangeMeters must be [low, high] with low < high")

def validate_bed_image(width, height, bit_depth, color_type, require, field="shore"):
    """`bed.path`'s PNG header: 16-bit greyscale, each side within BED_PIXELS."""
    require(bit_depth == 16 and color_type == 0, field + ".bed must be a 16-bit greyscale PNG")
    require(BED_PIXELS[0] <= width <= BED_PIXELS[1] and BED_PIXELS[0] <= height <= BED_PIXELS[1],
            field + ".bed must be 2...2048 pixels a side")


def validate_destination(destination, require, field="shore"):
    """Validate the declaration and its coexistence rules within one View."""
    validate_definition(destination["shore"], require, field)
    for key in EXCLUSIVE_WITH:
        require(destination.get(key) is None, "shore cannot coexist with " + key)
    require(not (destination.get("midground") or {}).get("water"),
            "shore cannot coexist with midground.water")
    follow = destination["shore"]["light"].get("follow", "none")
    environment = destination.get("environment") or {}
    if follow == "moon":
        require((destination.get("sky") or {}).get("moon") is not None,
                "shore.light.follow moon requires sky.moon")
    if follow == "sun":
        require(environment.get("sunPath") is not None or (environment.get("directSun") or {}).get("enabled") is True,
                "shore.light.follow sun requires environment.sunPath or an enabled directSun")


def has_ocean_region(water):
    """True when a root `water` block (View or Room) runs an FFT ocean region."""
    if not isinstance(water, dict):
        return False
    return any(isinstance(region, dict) and (region.get("surface") or {}).get("motion", "ocean") != "still"
               for region in water.get("regions") or [])


def has_wet_band(value):
    """Whether a shore explicitly selects the wet-band extension contract."""
    return isinstance(value, dict) and isinstance(value.get("sand"), dict) and "wetBand" in value["sand"]
