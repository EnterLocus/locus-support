"""`celestial.advection`: the body's day texture advected along a baked flow.

Portable data only. An author tool (`make_celestial_advection.py`) integrates
an authored steady flow (zonal jets plus vortices) offline and stores where
every surface point's colour came from after a few fixed ages; the app reads
that flipbook and keeps two staggered copies whose ages restart in turn, so
cloud bands drift, shear and spin without ever streaking out. See
docs/package-spec-v2.md "Celestial advection".
"""
import math

# Older readers reject the unknown `advection` key outright
# (CelestialDefinition.init(from:)), so the field itself sets the floor.
MINIMUM_APP = (1, 3, 2)
FIELDS = {"version", "flowTexture", "ageKeyframes", "maxAgeRotations",
          "displacementRangeDegrees", "regenerationRotations", "crossfade"}
RANGES = {"maxAgeRotations": (0.05, 4), "displacementRangeDegrees": (1, 90),
          "regenerationRotations": (0.1, 4), "crossfade": (0.05, 0.45)}
KEYFRAMES = (2, 16)
TILE_WIDTH = (64, 1024)
# Fields of the body profile that describe another, competing motion or
# surface model; the advected body draws only its day texture.
EXCLUDED = {"nightTexture", "cloudTexture", "cloudHeightRatio", "cloudDriftRatio",
            "cloudShadowStrength", "cloudEvolution", "cloudEvolutionPeriodSeconds"}


def oldest_age(value):
    """The largest age (rotations) either copy is ever shown at."""
    return (0.5 + value["crossfade"]) * value["regenerationRotations"]


def validate_definition(value, require, celestial=None):
    """Validate the `advection` object; returns its one asset path."""
    require(isinstance(value, dict) and set(value) == FIELDS, "invalid celestial.advection fields")
    require(type(value["version"]) is int and value["version"] == 1,
            "unsupported celestial.advection version")
    keyframes = value["ageKeyframes"]
    require(type(keyframes) is int and KEYFRAMES[0] <= keyframes <= KEYFRAMES[1],
            "celestial.advection.ageKeyframes must be an integer from 2 to 16")
    for field, (low, high) in RANGES.items():
        n = value[field]
        require(type(n) in (int, float) and math.isfinite(n) and low <= n <= high,
                "celestial.advection.%s must be finite and within range" % field)
    require(value["maxAgeRotations"] + 1e-9 >= oldest_age(value),
            "celestial.advection.maxAgeRotations must cover (0.5 + crossfade) * regenerationRotations")
    path = value["flowTexture"]
    require(isinstance(path, str) and path.lower().endswith(".png"),
            "celestial.advection.flowTexture must be a PNG path")
    if celestial is not None:
        require(not (EXCLUDED & set(celestial)),
                "celestial.advection excludes night, cloud texture and cloud-shell fields")
    return path


def validate_flow_header(value, width, height, bit_depth, color_type, require):
    """The flipbook is one 16-bit RGB PNG: ageKeyframes+1 stacked 2:1 tiles."""
    require(bit_depth == 16 and color_type == 2,
            "celestial.advection.flowTexture must be a 16-bit RGB PNG")
    require(TILE_WIDTH[0] <= width <= TILE_WIDTH[1] and width % 2 == 0
            and height == (value["ageKeyframes"] + 1) * width // 2,
            "celestial.advection.flowTexture must stack ageKeyframes+1 2:1 tiles, 64-1024 wide")
