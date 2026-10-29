"""A View's procedural night sky (`sky`), first supported by Locus 1.2.4.

See docs/package-spec-v2.md "`sky`" for the field contract. This module owns
the shape-only check of the manifest object and the Library capabilities it
requires; the archive-context checks (the mask exists in the payload, is a
2:1 grayscale PNG, fits the image budget) live in `validate_locusplace.py`,
the same split as `panorama_media` / `gpu_texture_sidecar`.

Mirrors `PackageV2Store.validate(_ sky:)`, `ProceduralSkyDefaults`,
`ProceduralSkyAuroraParameters` and `ProceduralSkyStarCatalogFile` in the viewer
(viewer/LocusViewer/Models/PackageV2.swift,
viewer/LocusViewer/Rendering/ProceduralSky/ProceduralSkyConfiguration.swift,
viewer/LocusViewer/Rendering/ProceduralSky/ProceduralSkyAuroraParameters.swift,
viewer/LocusViewer/Rendering/ProceduralSky/ProceduralSkyStarCatalogFile.swift).
The defaults and ranges below and the Swift ones are both checked against
viewer/LocusViewerTests/Fixtures/ProceduralSkyAuroraContract.json.
Python 3.9 compatible.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, List

STARS_CAPABILITY = "locus.view.sky.stars.v1"
AURORA_CAPABILITY = "locus.view.sky.aurora.v1"
MILKY_WAY_MAP_CAPABILITY = "locus.view.sky.milky-way-map.v1"
MILKY_WAY_MAP_MINIMUM_APP = (1, 3, 0)
DEFAULT_MODE_CAPABILITY = "locus.view.sky.default-mode.v1"
MINIMUM_APP = (1, 2, 4)
MINIMUM_APP_STRING = "1.2.4"

PALETTES = ("classic", "storm", "low-latitude")
SEED_RANGE = (0, 2_147_483_647)
# `sky.stars` (docs/package-spec-v2.md "`sky.stars`"): every field optional,
# defaults below; unknown keys, booleans and out-of-range values are errors
# here (authoring), nothing is clamped.
STARS_DEFAULTS = {
    "seed": 19,
    "twinkle": 1.0,
    "brightness": 1.0,
    "limitingMagnitude": 6.5,
    "brightStarSize": 1.0,
    "colorSaturation": 1.0,
    "azimuthDegrees": 0.0,
    "milkyWay": {
        "style": "realistic", "brightness": 1.0,
        "centerAzimuthDegrees": -150.0, "centerElevationDegrees": 44.0, "tiltDegrees": 0.0,
    },
    "clusters": [
        {"type": "pleiades", "azimuthDegrees": 105.0, "elevationDegrees": 50.0},
        {"type": "hyades", "azimuthDegrees": 98.3, "elevationDegrees": 39.2},
    ],
    "brightStars": {"minimumCount": 4, "minimumElevationDegrees": 20.0, "requireNegativeMagnitude": True},
    "twilight": {"azimuthDegrees": -110.0, "strength": 1.0, "height": 1.0, "color": [0.050, 0.028, 0.018]},
}
# Optional fields with no default: `realSky` (orient the layer as the real
# sky) and `catalog` (a star catalog file instead of the procedural catalog).
STARS_OPTIONAL_KEYS = ("realSky", "catalog")
# `sky.moon` (docs/package-spec-v2.md "`sky.moon`"): the Moon of the sky, a
# sibling of `sky.stars` and `sky.aurora`. Optional as a whole (absent: no Moon
# in the author's sky); every field optional once it is present.
MOON_DEFAULTS = {
    "azimuthDegrees": 150.0, "elevationDegrees": 25.0, "illumination": 0.5,
    "brightness": 1.0, "maximumIllumination": 0.5, "sizeScale": 2.0,
}
MOON_RANGES = {
    "azimuthDegrees": (-180.0, 180.0),
    "elevationDegrees": (0.0, 85.0),
    "illumination": (0.0, 1.0),
    "brightness": (0.0, 2.0),
    "maximumIllumination": (0.0, 1.0),
    "sizeScale": (1.0, 3.0),
    "drawnDiameterDegrees": (0.5172, 24.0),
}
MILKY_WAY_STYLES = ("realistic", "vivid")
STARS_MILKY_WAY_RANGES = {
    "brightness": (0.0, 2.0),
    "centerAzimuthDegrees": (-180.0, 180.0),
    "centerElevationDegrees": (-90.0, 90.0),
    "tiltDegrees": (-180.0, 180.0),
}
# The free placement of the galactic frame; `realSky` fixes it, so these must
# be absent with it.
STARS_MILKY_WAY_PLACEMENT = ("centerAzimuthDegrees", "centerElevationDegrees", "tiltDegrees")
# The procedural catalog's fields; a `catalog` file replaces that catalog, so
# these must be absent with it.
STARS_PROCEDURAL_CATALOG_KEYS = ("seed", "clusters", "brightStars")
REAL_SKY_LATITUDE_RANGE = (-90.0, 90.0)
# Local sidereal time in hours, half-open: 0 <= x < 24.
REAL_SKY_SIDEREAL_TIME_RANGE = (0.0, 24.0)
STARS_CLUSTER_TYPES = ("pleiades", "hyades")
STARS_CLUSTER_MAX = 4
STARS_CLUSTER_RANGES = {"azimuthDegrees": (-180.0, 180.0), "elevationDegrees": (5.0, 85.0)}
STARS_BRIGHT_COUNT_RANGE = (0, 12)
STARS_BRIGHT_RANGES = {"minimumElevationDegrees": (0.0, 80.0)}
STARS_TWILIGHT_RANGES = {"azimuthDegrees": (-180.0, 180.0), "strength": (0.0, 2.0), "height": (0.5, 3.0)}
STARS_TWILIGHT_COLOR_RANGE = (0.0, 0.2)
STARS_RANGES = {
    "twinkle": (0.0, 1.5),
    "brightness": (0.25, 2.0),
    "limitingMagnitude": (4.5, 7.0),
    "brightStarSize": (0.0, 2.0),
    "colorSaturation": (0.0, 1.5),
    "azimuthDegrees": (-180.0, 180.0),
}

# Star catalog file (docs/package-spec-v2.md "Star catalog file").
STAR_CATALOG_FORMAT = "locus-star-catalog"
STAR_CATALOG_VERSION = 1
STAR_CATALOG_FRAMES = ("equatorial", "horizontal")
STAR_CATALOG_MAX_BYTES = 1024 * 1024
STAR_CATALOG_MAX_SOURCE_CHARACTERS = 500
STAR_CATALOG_STAR_COUNT_RANGE = (1, 20_000)
# Per frame: (first angle range, second angle range). Right ascension is
# half-open, 0 <= x < 360; every other bound is inclusive.
STAR_CATALOG_ANGLE_RANGES = {
    "equatorial": ((0.0, 360.0), (-90.0, 90.0)),
    "horizontal": ((-180.0, 180.0), (-90.0, 90.0)),
}
STAR_CATALOG_MAGNITUDE_RANGE = (-2.0, 8.0)
STAR_CATALOG_BV_RANGE = (-0.5, 2.5)

# `sky.aurora` (docs/package-spec-v2.md "`sky.aurora`"): every field optional,
# defaults below; unknown keys, booleans and out-of-range values are errors,
# nothing is clamped. `substorms.periodSeconds` may also be exactly 0
# (no substorms).
AURORA_MAX_ARCS = 4
AURORA_RANGES = {"northAzimuthDegrees": (-180.0, 180.0), "intensity": (0.0, 2.0)}
AURORA_SUBSTORM_RANGES = {
    "periodSeconds": (120.0, 3600.0),
    "firstOnsetSeconds": (0.0, 3600.0),
    "strength": (0.0, 1.5),
    "raySpeedup": (0.0, 2.0),
}
AURORA_PERIOD_OFF = 0
AURORA_ARC_RANGES = {
    "elevationDegrees": (2.0, 178.0),
    "brightness": (0.0, 2.0),
    "thicknessKm": (0.8, 12.0),
    "raySpeedKmPerSecond": (0.0, 8.0),
    "rayWidthKm": (2.0, 40.0),
    "rayContrast": (0.0, 15.0),
    "waviness": (0.0, 2.0),
}
AURORA_DEFAULTS = {
    "northAzimuthDegrees": 0.0,
    "palette": "classic",
    "intensity": 1.0,
    "substorms": {"periodSeconds": 420.0, "firstOnsetSeconds": 60.0, "strength": 1.0, "raySpeedup": 0.5},
    "arcs": [
        {"elevationDegrees": 34.0, "brightness": 1.0, "thicknessKm": 2.25, "raySpeedKmPerSecond": 1.5,
         "rayWidthKm": 6.0, "rayContrast": 9.0, "waviness": 1.0},
        {"elevationDegrees": 9.2, "brightness": 1.24, "thicknessKm": 8.0, "raySpeedKmPerSecond": 2.0,
         "rayWidthKm": 20.0, "rayContrast": 2.5, "waviness": 1.0},
        {"elevationDegrees": 145.5, "brightness": 0.24, "thicknessKm": 2.5, "raySpeedKmPerSecond": 1.5,
         "rayWidthKm": 8.0, "rayContrast": 7.0, "waviness": 1.0},
    ],
}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_definition(value: Any, require: Callable[[bool, str], None]) -> str:
    """Shape-only check of `sky`. Returns the declared mask path; whether
    that file exists and is a 2:1 grayscale PNG is the caller's job (it needs
    the open archive)."""
    require(isinstance(value, dict), "sky must be an object")
    require(not (set(value) - {"mask", "defaultMode", "stars", "aurora", "moon"}), "unknown sky fields")
    mask = value.get("mask")
    require(isinstance(mask, str) and bool(mask), "sky.mask must be a file path")
    default_mode = value.get("defaultMode")
    require(default_mode is None or default_mode in ("real", "free"),
            "sky.defaultMode must be real or free")
    stars = value.get("stars")
    aurora = value.get("aurora")
    moon = value.get("moon")
    require(stars is not None or aurora is not None or moon is not None,
            "sky must declare stars, aurora, moon, or any combination")
    if stars is not None:
        validate_stars(stars, require)
    if aurora is not None:
        validate_aurora(aurora, require)
    if moon is not None:
        validate_moon(moon, require)
    return mask


def validate_stars(stars: Any, require: Callable[[bool, str], None]) -> None:
    """`sky.stars`, field by field, as `ProceduralSkyStarParameters.resolve`
    does in the viewer. An explicit null is an absent field, as in the
    viewer's decoder. Unknown keys are rejected here (authoring) while the
    app's readers ignore them, per the shared contract fixture."""
    require(isinstance(stars, dict), "sky.stars must be an object")
    require(not (set(stars) - set(STARS_DEFAULTS) - set(STARS_OPTIONAL_KEYS)), "unknown sky.stars fields")
    if stars.get("seed") is not None:
        seed = stars["seed"]
        require(
            type(seed) is int and SEED_RANGE[0] <= seed <= SEED_RANGE[1],
            "sky.stars.seed must be an integer 0...2147483647",
        )
    _check_ranges(stars, STARS_RANGES, "sky.stars", require)
    milky_way = stars.get("milkyWay")
    if milky_way is not None:
        require(isinstance(milky_way, dict), "sky.stars.milkyWay must be an object")
        require(not (set(milky_way) - (set(STARS_DEFAULTS["milkyWay"]) | {"diffuseMap"})), "unknown sky.stars.milkyWay fields")
        if milky_way.get("style") is not None:
            require(isinstance(milky_way["style"], str) and milky_way["style"] in MILKY_WAY_STYLES,
                    "sky.stars.milkyWay.style must be 'realistic' or 'vivid'")
        _check_ranges(milky_way, STARS_MILKY_WAY_RANGES, "sky.stars.milkyWay", require)
        if milky_way.get("diffuseMap") is not None:
            require(isinstance(milky_way["diffuseMap"], str) and bool(milky_way["diffuseMap"]), "sky.stars.milkyWay.diffuseMap must be a file path")
    real_sky = stars.get("realSky")
    if real_sky is not None:
        require(isinstance(real_sky, dict), "sky.stars.realSky must be an object")
        require(not (set(real_sky) - {"latitudeDegrees", "siderealTimeHours"}),
                "unknown sky.stars.realSky fields")
        for field in ("latitudeDegrees", "siderealTimeHours"):
            require(real_sky.get(field) is not None, "sky.stars.realSky.%s is required" % field)
        _check_ranges(real_sky, {"latitudeDegrees": REAL_SKY_LATITUDE_RANGE}, "sky.stars.realSky", require)
        hours = real_sky["siderealTimeHours"]
        lower, upper = REAL_SKY_SIDEREAL_TIME_RANGE
        require(_finite_number(hours) and lower <= hours < upper,
                "sky.stars.realSky.siderealTimeHours must be finite and within %g...%g (24 excluded)" % (lower, upper))
        for field in STARS_MILKY_WAY_PLACEMENT:
            require(not isinstance(milky_way, dict) or milky_way.get(field) is None,
                    "sky.stars.milkyWay.%s must be absent with sky.stars.realSky" % field)
    catalog = stars.get("catalog")
    if catalog is not None:
        require(isinstance(catalog, str) and bool(catalog), "sky.stars.catalog must be a file path")
        for field in STARS_PROCEDURAL_CATALOG_KEYS:
            require(stars.get(field) is None, "sky.stars.%s must be absent with sky.stars.catalog" % field)
    clusters = stars.get("clusters")
    if clusters is not None:
        require(isinstance(clusters, list) and len(clusters) <= STARS_CLUSTER_MAX,
                "sky.stars.clusters must be an array of 0...%d clusters" % STARS_CLUSTER_MAX)
        for index, cluster in enumerate(clusters):
            path = "sky.stars.clusters[%d]" % index
            require(isinstance(cluster, dict), path + " must be an object")
            require(not (set(cluster) - ({"type"} | set(STARS_CLUSTER_RANGES))), "unknown %s fields" % path)
            require(isinstance(cluster.get("type"), str) and cluster["type"] in STARS_CLUSTER_TYPES,
                    "%s.type must be 'pleiades' or 'hyades'" % path)
            _check_ranges(cluster, STARS_CLUSTER_RANGES, path, require)
    bright = stars.get("brightStars")
    if bright is not None:
        require(isinstance(bright, dict), "sky.stars.brightStars must be an object")
        require(not (set(bright) - {"minimumCount", "minimumElevationDegrees", "requireNegativeMagnitude"}),
                "unknown sky.stars.brightStars fields")
        count = bright.get("minimumCount")
        if count is not None:
            require(type(count) is int and STARS_BRIGHT_COUNT_RANGE[0] <= count <= STARS_BRIGHT_COUNT_RANGE[1],
                    "sky.stars.brightStars.minimumCount must be an integer 0...12")
        _check_ranges(bright, STARS_BRIGHT_RANGES, "sky.stars.brightStars", require)
        if bright.get("requireNegativeMagnitude") is not None:
            require(isinstance(bright["requireNegativeMagnitude"], bool),
                    "sky.stars.brightStars.requireNegativeMagnitude must be a boolean")
    twilight = stars.get("twilight")
    if twilight is not None:
        require(isinstance(twilight, dict), "sky.stars.twilight must be an object")
        require(not (set(twilight) - (set(STARS_TWILIGHT_RANGES) | {"color"})),
                "unknown sky.stars.twilight fields")
        _check_ranges(twilight, STARS_TWILIGHT_RANGES, "sky.stars.twilight", require)
        color = twilight.get("color")
        if color is not None:
            lower, upper = STARS_TWILIGHT_COLOR_RANGE
            require(isinstance(color, list) and len(color) == 3
                    and all(_finite_number(c) and lower <= c <= upper for c in color),
                    "sky.stars.twilight.color must be 3 finite numbers within %g...%g" % (lower, upper))


def _check_ranges(value: Any, ranges: Any, path: str, require: Callable[[bool, str], None]) -> None:
    for field, (lower, upper) in ranges.items():
        if value.get(field) is not None:
            require(
                _finite_number(value[field]) and lower <= value[field] <= upper,
                "%s.%s must be finite and within %g...%g" % (path, field, lower, upper),
            )


def validate_moon(moon: Any, require: Callable[[bool, str], None]) -> None:
    """`sky.moon`, field by field, as `ProceduralSkyMoonParameters.resolve` does
    in the viewer. An explicit null is an absent field. Unknown keys are
    rejected here (authoring) while the app's readers ignore them, per the
    shared contract fixture."""
    require(isinstance(moon, dict), "sky.moon must be an object")
    require(not (set(moon) - set(MOON_RANGES)), "unknown sky.moon fields")
    _check_ranges(moon, MOON_RANGES, "sky.moon", require)


def validate_aurora(aurora: Any, require: Callable[[bool, str], None]) -> None:
    """`sky.aurora`, field by field, as `ProceduralSkyAuroraParameters.resolve`
    does in the viewer. An explicit null is an absent field. Unknown keys are
    rejected here (authoring: catch typos) while the app's readers ignore them
    (forward compatibility), per the shared contract fixture."""
    require(isinstance(aurora, dict), "sky.aurora must be an object")
    require(not (set(aurora) - (set(AURORA_RANGES) | {"palette", "substorms", "arcs"})),
            "unknown sky.aurora fields")
    if aurora.get("palette") is not None:
        require(isinstance(aurora["palette"], str) and aurora["palette"] in PALETTES,
                "sky.aurora.palette must be 'classic', 'storm', or 'low-latitude'")
    _check_ranges(aurora, AURORA_RANGES, "sky.aurora", require)
    substorms = aurora.get("substorms")
    if substorms is not None:
        require(isinstance(substorms, dict), "sky.aurora.substorms must be an object")
        require(not (set(substorms) - set(AURORA_SUBSTORM_RANGES)),
                "unknown sky.aurora.substorms fields")
        period = substorms.get("periodSeconds")
        if period is not None and _finite_number(period) and period == AURORA_PERIOD_OFF:
            substorms = {k: v for k, v in substorms.items() if k != "periodSeconds"}
        _check_ranges(substorms, AURORA_SUBSTORM_RANGES, "sky.aurora.substorms", require)
    arcs = aurora.get("arcs")
    if arcs is not None:
        require(isinstance(arcs, list) and 1 <= len(arcs) <= AURORA_MAX_ARCS,
                "sky.aurora.arcs must be an array of 1...%d arcs" % AURORA_MAX_ARCS)
        for index, arc in enumerate(arcs):
            path = "sky.aurora.arcs[%d]" % index
            require(isinstance(arc, dict), path + " must be an object")
            require(not (set(arc) - set(AURORA_ARC_RANGES)), "unknown %s fields" % path)
            _check_ranges(arc, AURORA_ARC_RANGES, path, require)


def milky_way_map_path(sky: Any) -> Any:
    stars = sky.get("stars") if isinstance(sky, dict) else None
    galaxy = stars.get("milkyWay") if isinstance(stars, dict) else None
    return galaxy.get("diffuseMap") if isinstance(galaxy, dict) else None


def star_catalog_path(sky: Any) -> Any:
    """The declared `sky.stars.catalog` path of a shape-valid `sky`, or None."""
    stars = sky.get("stars") if isinstance(sky, dict) else None
    return stars.get("catalog") if isinstance(stars, dict) else None


def real_sky_declared(sky: Any) -> bool:
    stars = sky.get("stars") if isinstance(sky, dict) else None
    return isinstance(stars, dict) and stars.get("realSky") is not None


def validate_star_catalog(
    data: Any, require: Callable[[bool, str], None], real_sky_present: bool
) -> None:
    """A parsed star catalog file, as `ProceduralSkyStarCatalogFile.parse`
    does in the viewer (plus: unknown top-level keys are rejected here, as
    in the other authoring validators). `real_sky_present` is whether the
    View declares `sky.stars.realSky`, which an `equatorial` catalog needs.
    Raises through `require` at the first problem."""
    require(isinstance(data, dict), "star catalog must be a JSON object")
    require(not (set(data) - {"format", "version", "frame", "source", "stars"}),
            "unknown star catalog fields")
    require(data.get("format") == STAR_CATALOG_FORMAT, "star catalog format must be %r" % STAR_CATALOG_FORMAT)
    require(type(data.get("version")) is int and data["version"] == STAR_CATALOG_VERSION,
            "star catalog version must be %d" % STAR_CATALOG_VERSION)
    frame = data.get("frame")
    require(isinstance(frame, str) and frame in STAR_CATALOG_FRAMES,
            "star catalog frame must be 'equatorial' or 'horizontal'")
    if data.get("source") is not None:
        require(isinstance(data["source"], str) and len(data["source"]) <= STAR_CATALOG_MAX_SOURCE_CHARACTERS,
                "star catalog source must be text of at most %d characters" % STAR_CATALOG_MAX_SOURCE_CHARACTERS)
    require(not (frame == "equatorial" and not real_sky_present),
            "an equatorial star catalog requires sky.stars.realSky")
    stars = data.get("stars")
    low, high = STAR_CATALOG_STAR_COUNT_RANGE
    require(isinstance(stars, list) and low <= len(stars) <= high,
            "star catalog stars must be an array of %d...%d rows" % (low, high))
    (first_low, first_high), (second_low, second_high) = STAR_CATALOG_ANGLE_RANGES[frame]
    first_name, second_name = (
        ("right ascension", "declination") if frame == "equatorial" else ("azimuth", "elevation"))
    for index, row in enumerate(stars):
        path = "star catalog stars[%d]" % index
        require(isinstance(row, list) and len(row) == 4 and all(_finite_number(v) for v in row),
                "%s must be exactly four finite numbers" % path)
        first, second, magnitude, bv = row
        # Right ascension is half-open: 360 is 0 again.
        first_ok = first_low <= first < first_high if frame == "equatorial" else first_low <= first <= first_high
        require(first_ok, "%s %s must be within %g...%g" % (path, first_name, first_low, first_high))
        require(second_low <= second <= second_high,
                "%s %s must be within %g...%g" % (path, second_name, second_low, second_high))
        require(STAR_CATALOG_MAGNITUDE_RANGE[0] <= magnitude <= STAR_CATALOG_MAGNITUDE_RANGE[1],
                "%s V must be within %g...%g" % (path, *STAR_CATALOG_MAGNITUDE_RANGE))
        require(STAR_CATALOG_BV_RANGE[0] <= bv <= STAR_CATALOG_BV_RANGE[1],
                "%s B-V must be within %g...%g" % (path, *STAR_CATALOG_BV_RANGE))


def parse_star_catalog(raw: bytes, require: Callable[[bool, str], None]) -> Any:
    """The JSON of a star catalog file: at most 1 MB, UTF-8, no duplicate
    keys, no NaN or Infinity. Shape and ranges are `validate_star_catalog`."""
    require(len(raw) <= STAR_CATALOG_MAX_BYTES,
            "star catalog exceeds %d bytes" % STAR_CATALOG_MAX_BYTES)

    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "star catalog has a duplicate key %r" % key)
            value[key] = item
        return value

    def reject_constant(name):
        require(False, "star catalog contains the non-standard number %s" % name)

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (UnicodeDecodeError, ValueError) as error:
        require(False, "star catalog is not valid UTF-8 JSON: %s" % error)


def capabilities(value: Any) -> List[str]:
    """The Library capabilities a valid `sky` requires: one per declared
    `stars` and `aurora`, independent of each other. An explicit Free default
    requires a capability because older readers silently select Real. `moon` has none: a reader
    that predates it ignores it and shows the View without a Moon
    (docs/package-spec-v2.md "`sky.moon`")."""
    result = []
    if isinstance(value, dict):
        if value.get("stars") is not None:
            result.append(STARS_CAPABILITY)
        if milky_way_map_path(value) is not None:
            result.append(MILKY_WAY_MAP_CAPABILITY)
        if value.get("aurora") is not None:
            result.append(AURORA_CAPABILITY)
        if value.get("defaultMode") == "free":
            result.append(DEFAULT_MODE_CAPABILITY)
    return result
