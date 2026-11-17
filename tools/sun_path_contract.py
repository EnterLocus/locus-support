"""Strict Package-v2 contract for environment.sunPath."""

import math

MINIMUM_APP = (1, 3, 0)
CAPABILITY = "locus.view.sun-path.v1"
DISC_SIZE_RANGE = (0.001, 5)

# The opt-in day/night extension (#1243): `daySky` renders a clear-sky
# atmosphere through `sky.mask` at every hour and `panoramaGrade` tints the
# painted panorama with the sun's elevation. Earlier readers reject both
# unknown sunPath fields, so the extension carries its own capability and floor.
DAY_NIGHT_MINIMUM_APP = (1, 4, 9)
DAY_NIGHT_CAPABILITY = "locus.view.sun-path.day-night.v1"
DAY_NIGHT_FIELDS = ("daySky", "panoramaGrade", "light")
SKY_FIELDS = ("daySky", "panoramaGrade")
DAY_SKY_RANGES = {"haze": (0, 1), "exposure": (0.25, 4)}
DAY_SKY_DEFAULTS = {"haze": 0.3, "exposure": 1}
GRADE_STOP_COUNT = (2, 16)
GRADE_ELEVATION_RANGE = (-90, 90)
GRADE_COLOR_RANGE = (0, 4)
LIGHT_COLOR_RANGE = (0, 16)
LIGHT_AMBIENT_EV_RANGE = (-6, 6)
# v1 is tested only on a masked procedural sky without these Destination
# declarations; each can be admitted later with its own evidence.
DAY_NIGHT_EXCLUSIONS = ("clouds", "media", "water")

# A second, full-frame night panorama (#2096). The root `panorama` remains
# the daylight source; this path is the authored night source that the runtime
# blends in over the path elevations below. It deliberately inherits the v1
# day/night composition exclusions until each combination is separately proven.
PANORAMA_BLEND_CAPABILITY = "locus.view.sun-path.panorama-blend.v1"
PANORAMA_BLEND_MINIMUM_APP = (1, 4, 10)
PANORAMA_BLEND_FIELDS = ("panoramaBlend",)
PANORAMA_BLEND_ELEVATION_RANGE = (-18, 10)
PANORAMA_BLEND_GRADE_RANGE = (0, 4)
PANORAMA_BLEND_DEFAULTS = {
    "dayElevationDegrees": -1,
    "nightElevationDegrees": -12,
    "nightGrade": [1, 1, 1],
}


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
        not set(value) - {"sunFreeSky", "disc"} - set(DAY_NIGHT_FIELDS) - set(PANORAMA_BLEND_FIELDS) - set(RANGES),
        field + " has unsupported fields",
    )
    require("sunFreeSky" in value and type(value["sunFreeSky"]) is bool and value["sunFreeSky"],
            field + ".sunFreeSky must be true")
    for key, (low, high) in RANGES.items():
        require(_number(value.get(key, DEFAULTS[key]), low, high), field + "." + key + " is out of range")
    if "disc" in value:
        validate_disc(value["disc"], require, asset, field + ".disc")
    if "daySky" in value:
        validate_day_sky(value["daySky"], require, field + ".daySky")
    if "panoramaGrade" in value:
        validate_panorama_grade(value["panoramaGrade"], require, field + ".panoramaGrade")
    if "light" in value:
        validate_light(value["light"], require, field + ".light")
    if "panoramaBlend" in value:
        validate_panorama_blend(value["panoramaBlend"], require, field + ".panoramaBlend")
    return value


def uses_day_night(value):
    """Whether a sunPath object declares the day/night extension."""
    return isinstance(value, dict) and any(key in value for key in DAY_NIGHT_FIELDS + PANORAMA_BLEND_FIELDS)


def uses_panorama_blend(value):
    return isinstance(value, dict) and "panoramaBlend" in value


def minimum_app(value):
    if uses_panorama_blend(value):
        return PANORAMA_BLEND_MINIMUM_APP
    return DAY_NIGHT_MINIMUM_APP if uses_day_night(value) else MINIMUM_APP


def capabilities(value):
    result = [CAPABILITY] + ([DAY_NIGHT_CAPABILITY] if uses_day_night(value) else [])
    if uses_panorama_blend(value):
        result.append(PANORAMA_BLEND_CAPABILITY)
    return result


def validate_panorama_blend(value, require, field="environment.sunPath.panoramaBlend"):
    require(isinstance(value, dict), field + " must be an object")
    require("path" in value and not set(value) - {"path", "dayElevationDegrees", "nightElevationDegrees", "nightGrade"},
            field + " has unsupported fields")
    path = value["path"]
    require(isinstance(path, str) and _image_path(path), field + ".path has invalid JPEG/PNG path")
    day = value.get("dayElevationDegrees", PANORAMA_BLEND_DEFAULTS["dayElevationDegrees"])
    night = value.get("nightElevationDegrees", PANORAMA_BLEND_DEFAULTS["nightElevationDegrees"])
    require(_number(day, *PANORAMA_BLEND_ELEVATION_RANGE), field + ".dayElevationDegrees is out of range")
    require(_number(night, *PANORAMA_BLEND_ELEVATION_RANGE) and night < day,
            field + ".nightElevationDegrees must be below dayElevationDegrees")
    grade = value.get("nightGrade", PANORAMA_BLEND_DEFAULTS["nightGrade"])
    require(isinstance(grade, list) and len(grade) == 3
            and all(_number(channel, *PANORAMA_BLEND_GRADE_RANGE) for channel in grade),
            field + ".nightGrade is invalid")
    return value


def validate_day_sky(value, require, field="environment.sunPath.daySky"):
    require(isinstance(value, dict), field + " must be an object")
    require(not set(value) - set(DAY_SKY_RANGES), field + " has unsupported fields")
    for key, (low, high) in DAY_SKY_RANGES.items():
        require(_number(value.get(key, DAY_SKY_DEFAULTS[key]), low, high), field + "." + key + " is out of range")
    return value


def _validate_stops(stops, require, field, color_range, optional=()):
    """Stops shared by panoramaGrade and light."""
    require(isinstance(stops, list) and GRADE_STOP_COUNT[0] <= len(stops) <= GRADE_STOP_COUNT[1],
            field + ".stops must hold 2...16 stops")
    previous = None
    for index, stop in enumerate(stops):
        context = "%s.stops[%d]" % (field, index)
        require(isinstance(stop, dict) and {"elevationDegrees", "color"} <= set(stop)
                and not set(stop) - {"elevationDegrees", "color"} - set(optional),
                context + " must contain elevationDegrees and color" + "".join(", optional " + key for key in optional))
        elevation = stop["elevationDegrees"]
        require(_number(elevation, *GRADE_ELEVATION_RANGE), context + ".elevationDegrees is out of range")
        require(previous is None or elevation > previous, context + ".elevationDegrees must increase strictly")
        previous = elevation
        color = stop["color"]
        require(isinstance(color, list) and len(color) == 3
                and all(_number(channel, *color_range) for channel in color),
                context + ".color must be three numbers %g...%g" % color_range)
    return stops


def validate_panorama_grade(value, require, field="environment.sunPath.panoramaGrade"):
    require(isinstance(value, dict), field + " must be an object")
    require(set(value) == {"stops"}, field + " must contain exactly stops")
    _validate_stops(value["stops"], require, field, GRADE_COLOR_RANGE)
    return value


def validate_light(value, require, field="environment.sunPath.light"):
    """One authored sun: drives the Room sun and IBL, and with
    `midground: true` also the View's 3D midground."""
    require(isinstance(value, dict), field + " must be an object")
    require("stops" in value and not set(value) - {"stops", "midground"}, field + " must contain stops and optional midground")
    require(type(value.get("midground", False)) is bool, field + ".midground must be a boolean")
    stops = _validate_stops(value["stops"], require, field, LIGHT_COLOR_RANGE, optional=("ambientEV",))
    for index, stop in enumerate(stops):
        require(_number(stop.get("ambientEV", 0), *LIGHT_AMBIENT_EV_RANGE),
                "%s.stops[%d].ambientEV is out of range" % (field, index))
    return value


def validate_day_night_destination(destination, require, minimum=None):
    """Destination-level rules for a sunPath declaring daySky/panoramaGrade."""
    value = (destination.get("environment") or {}).get("sunPath")
    if not uses_day_night(value):
        return
    fields = "sunPath.daySky/panoramaGrade/light"
    if minimum is not None:
        require(minimum >= DAY_NIGHT_MINIMUM_APP, fields + " requires minimumAppVersion >= 1.4.9")
        if uses_panorama_blend(value):
            require(minimum >= PANORAMA_BLEND_MINIMUM_APP,
                    "sunPath.panoramaBlend requires minimumAppVersion >= 1.4.10")
    sky = destination.get("sky")
    if any(key in value for key in SKY_FIELDS):
        require(isinstance(sky, dict) and "mask" in sky, "sunPath.daySky/panoramaGrade require sky with its mask")
    midground = destination.get("midground")
    if isinstance(value.get("light"), dict) and value["light"].get("midground") is True:
        require(isinstance(midground, dict) and midground.get("path") is not None,
                "sunPath.light.midground requires midground.path")
    if uses_panorama_blend(value):
        require(isinstance(value.get("daySky"), dict), "sunPath.panoramaBlend requires sunPath.daySky")
        require(isinstance(sky, dict) and "mask" in sky,
                "sunPath.panoramaBlend requires root sky with its mask")
        if destination.get("shore") is not None and minimum is not None:
            from shore_contract import PANORAMA_BLEND_MINIMUM_APP as SHORE_PANORAMA_BLEND_MINIMUM_APP
            require(minimum >= SHORE_PANORAMA_BLEND_MINIMUM_APP,
                    "sunPath.panoramaBlend with shore requires minimumAppVersion >= 1.4.11")
    media = destination.get("media")
    for key in DAY_NIGHT_EXCLUSIONS:
        if key == "water" and destination.get("water") is not None:
            if minimum is not None:
                from water_contract import DAY_NIGHT_MINIMUM_APP as WATER_DAY_NIGHT_MINIMUM_APP
                require(minimum >= WATER_DAY_NIGHT_MINIMUM_APP,
                        "sunPath.daySky/panoramaGrade/light with water requires minimumAppVersion >= 1.5.1")
            continue
        if key == "media" and isinstance(media, dict) and "dayNight" in media:
            # The only admitted media/full-day composition is the explicit
            # per-video lighting/emission pair bound to panoramaBlend's night
            # source. Older media has no night state and remains excluded.
            require(uses_panorama_blend(value),
                    "media.dayNight requires sunPath.panoramaBlend")
            continue
        require(destination.get(key) is None, fields + " cannot coexist with " + key)
    if isinstance(media, dict) and "dayNight" in media:
        require(uses_panorama_blend(value),
                "media.dayNight requires sunPath.panoramaBlend")
    for key in ("water", "flowingWater"):
        require(not (isinstance(midground, dict) and midground.get(key) is not None),
                fields + " cannot coexist with midground." + key)
    require(not (isinstance(sky, dict) and sky.get("aurora") is not None), fields + " cannot coexist with sky.aurora")


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


def _image_path(value):
    return _png_path(value) or (
        isinstance(value, str) and value.lower().endswith((".jpg", ".jpeg"))
        and not value.startswith("/") and not any(ord(char) < 32 for char in value)
        and not any(part in ("", ".", "..") for part in value.split("/"))
    )
