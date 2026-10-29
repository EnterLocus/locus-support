"""`celestial.polarRadiusRatio` and `celestial.rings`: an oblate, ringed body.

Portable data only. The body becomes a spheroid about its local spin axis and
may carry one flat annulus in its equatorial plane, shaded from a 1-pixel-tall
radial profile (sRGB colour, straight normal-incidence opacity). An author
tool (`make_celestial_rings.py`) writes that profile from radial bands. See
docs/package-spec-v2.md "Celestial oblate body and rings".
"""
import math

# Readers before 1.3.4 reject both unknown keys outright
# (CelestialDefinition.init(from:)), so either field sets the floor.
MINIMUM_APP = (1, 3, 4)
REQUIRED = {"version", "profileTexture", "innerRadiusRatio", "outerRadiusRatio"}
OPTIONAL = {"brightness", "unlitBrightness"}
DEFAULTS = {"brightness": 1, "unlitBrightness": 1}
RANGES = {"brightness": (0, 4), "unlitBrightness": (0, 2)}
POLAR_RANGE = (0.85, 1)
INNER_MINIMUM, GAP_MINIMUM, OUTER_MAXIMUM = 1.05, 0.05, 4
# Ring far-field envelope in View-frame metres (body limits are unchanged).
NEAR_LIMIT, FAR_LIMIT = 200, 1100
PROFILE_WIDTH = (64, 8192)
# Readers clamp alpha before taking the optical depth: alpha 1 would be an
# infinite depth and an infinitely dark shadow.
ALPHA_LIMIT = 0.999
CLOUD_SHELL_FIELDS = {"cloudHeightRatio", "cloudDriftRatio", "cloudShadowStrength",
                      "cloudEvolution", "cloudEvolutionPeriodSeconds"}
# The ringed body draws only its day texture with the shared daylight and rim.
EXCLUDED = {"nightTexture", "cloudTexture", "advection", "oceanGlint"} | CLOUD_SHELL_FIELDS


def finite(n):
    return type(n) in (int, float) and math.isfinite(n)


def optical_depth(alpha):
    """Normal optical depth from straight normal-incidence opacity."""
    return -math.log(1 - min(alpha, ALPHA_LIMIT))


def validate_definition(value, require, celestial=None):
    """Validate the `rings` object; returns its one asset path.

    With `celestial` (already validated geometry), also enforce the field
    exclusions and the ring's own far-field envelope.
    """
    require(isinstance(value, dict) and REQUIRED <= set(value) <= REQUIRED | OPTIONAL,
            "invalid celestial.rings fields")
    require(type(value["version"]) is int and value["version"] == 1,
            "unsupported celestial.rings version")
    inner, outer = value["innerRadiusRatio"], value["outerRadiusRatio"]
    require(finite(inner) and finite(outer) and inner >= INNER_MINIMUM
            and inner + GAP_MINIMUM <= outer + 1e-9 and outer <= OUTER_MAXIMUM,
            "celestial.rings radii must satisfy 1.05 <= inner, inner + 0.05 <= outer <= 4")
    for field, (low, high) in RANGES.items():
        if field in value:
            require(finite(value[field]) and low <= value[field] <= high,
                    "celestial.rings.%s must be finite and within range" % field)
    path = value["profileTexture"]
    require(isinstance(path, str) and path.lower().endswith(".png"),
            "celestial.rings.profileTexture must be a PNG path")
    if celestial is not None:
        require(not (EXCLUDED & set(celestial)),
                "celestial.rings excludes night, cloud, cloud-shell, advection and oceanGlint fields")
        from celestial_view import resolved_geometry
        distance, radius = resolved_geometry(celestial)
        extent = outer * radius
        require(distance - extent >= NEAR_LIMIT and distance + extent <= FAR_LIMIT,
                "celestial.rings exceeds the 200-1100m far-field envelope")
    return path


def validate_profile(celestial, require):
    """Celestial-level oblate/ring rules; returns the ring profile path or None.

    `polarRadiusRatio`'s range is checked with the other celestial ranges.
    """
    if "polarRadiusRatio" in celestial:
        require(not (CLOUD_SHELL_FIELDS & set(celestial)),
                "celestial.polarRadiusRatio excludes cloud-shell fields")
    if "rings" in celestial:
        return validate_definition(celestial["rings"], require, celestial)
    return None


def validate_profile_header(width, height, bit_depth, color_type, require):
    """The radial profile is one 8-bit RGBA PNG row, 64-8192 wide."""
    require(bit_depth == 8 and color_type == 6 and height == 1
            and PROFILE_WIDTH[0] <= width <= PROFILE_WIDTH[1],
            "celestial.rings.profileTexture must be an 8-bit RGBA PNG, 1 pixel tall and 64-8192 wide")
