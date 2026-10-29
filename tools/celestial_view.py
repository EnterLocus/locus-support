"""Portable one-body far-field View profile, first supported by Locus 1.2.4."""
import math

CAPABILITY = "locus.view.celestial.v1"
MINIMUM_APP = (1, 2, 4)
REQUIRED = {"version", "backgroundPanorama", "dayTexture", "yawDegrees",
            "elevationDegrees", "rotationPeriodSeconds"}
OPTIONAL = {"nightTexture", "cloudTexture", "axialTiltDegrees", "initialRotationDegrees",
            "sunAzimuthDegrees", "sunElevationDegrees", "nightGain",
            "atmosphereColor", "atmosphereStrength", "angularDiameterDegrees", "distanceMeters", "radiusMeters", "sunDisc",
            "cloudHeightRatio", "cloudDriftRatio", "cloudShadowStrength", "cloudEvolution", "cloudEvolutionPeriodSeconds",
            "advection", "oceanGlint", "polarRadiusRatio", "rings"}
RANGES = {"yawDegrees": (-360, 360), "elevationDegrees": (-90, 90),
          "angularDiameterDegrees": (1, 60), "distanceMeters": (400, 800), "radiusMeters": (1, 400), "rotationPeriodSeconds": (120, 86400),
          "axialTiltDegrees": (-180, 180), "initialRotationDegrees": (-360, 360),
          "sunAzimuthDegrees": (-360, 360), "sunElevationDegrees": (-90, 90),
          "nightGain": (0, 2), "atmosphereStrength": (0, 1),
          "cloudHeightRatio": (0, 0.03), "cloudDriftRatio": (0.5, 2), "cloudShadowStrength": (0, 1),
          "cloudEvolution": (0, 1), "cloudEvolutionPeriodSeconds": (60, 3600),
          "polarRadiusRatio": (0.85, 1)}
# Independent cloud shell (#1288): any field below requires this reader floor,
# since CelestialDefinition.init(from:) rejects unknown keys outright (no
# forward-compatible ignore for older readers).
CLOUD_SHELL_FIELDS = {"cloudHeightRatio", "cloudDriftRatio", "cloudShadowStrength", "cloudEvolution", "cloudEvolutionPeriodSeconds"}
CLOUD_SHELL_MINIMUM_APP = (1, 3, 0)


def validate_definition(value, require):
    require(isinstance(value, dict), "celestial must be an object")
    require(REQUIRED <= set(value) and set(value) <= REQUIRED | OPTIONAL,
            "invalid celestial fields")
    require(type(value["version"]) is int and value["version"] in (1, 2),
            "unsupported celestial version")
    for field, (low, high) in RANGES.items():
        if field in value:
            n = value[field]
            require(type(n) in (int, float) and math.isfinite(n) and low <= n <= high,
                    "celestial.%s must be finite and within range" % field)
    if value["version"] == 1:
        require("angularDiameterDegrees" in value and not ({"distanceMeters", "radiusMeters"} & set(value)),
                "celestial v1 requires angularDiameterDegrees and fixed distance")
    else:
        require(("angularDiameterDegrees" in value) != ("radiusMeters" in value),
                "celestial v2 requires exactly one size: angularDiameterDegrees or radiusMeters")
        require("radiusMeters" not in value or "distanceMeters" in value,
                "celestial.radiusMeters requires distanceMeters")
        distance, radius = resolved_geometry(value)
        require(radius <= distance * 0.5 and distance + radius <= 1100,
                "celestial geometry exceeds 60-degree diameter or 1100m far-field envelope")
    if "atmosphereColor" in value:
        color = value["atmosphereColor"]
        require(isinstance(color, list) and len(color) == 3 and all(
            type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in color),
            "celestial.atmosphereColor must be three finite values between 0 and 1")
    paths = {}
    for field in ("backgroundPanorama", "dayTexture", "nightTexture", "cloudTexture"):
        if field in value:
            path = value[field]
            require(isinstance(path, str) and path.lower().endswith((".jpg", ".jpeg", ".png")),
                    "celestial.%s must be a JPEG or PNG path" % field)
            paths[field] = path
    if "advection" in value:
        from celestial_advection import validate_definition as validate_advection
        # Not a 2:1 surface image: callers check its own header and closure.
        validate_advection(value["advection"], require, value)
    if {"polarRadiusRatio", "rings"} & set(value):
        from celestial_rings import validate_profile as validate_rings
        # The ring profile is not a 2:1 surface image either; same as above.
        validate_rings(value, require)
    if "sunDisc" in value:
        from sun_path_contract import validate_disc
        validate_disc(value["sunDisc"], require,
                      lambda path, field, **kwargs: paths.update({"sunDisc.skyMask": path}),
                      field="celestial.sunDisc")
    if "oceanGlint" in value:
        from ocean_glint import validate
        try:
            validate(value["oceanGlint"])
        except ValueError as error:
            require(False, str(error))
        paths["oceanGlint.mask"] = value["oceanGlint"]["mask"]
    return paths


SUN_CAPABILITY = "locus.view.celestial-sun.v1"
GEOMETRY_CAPABILITY = "locus.view.celestial.v2"
GEOMETRY_MINIMUM_APP = (1, 2, 5)


def minimum_app(value):
    if isinstance(value, dict) and {"polarRadiusRatio", "rings"} & set(value):
        from celestial_rings import MINIMUM_APP as RINGS_MINIMUM_APP
        return RINGS_MINIMUM_APP
    if isinstance(value, dict) and "advection" in value:
        from celestial_advection import MINIMUM_APP as ADVECTION_MINIMUM_APP
        return ADVECTION_MINIMUM_APP
    if isinstance(value, dict) and "oceanGlint" in value:
        from ocean_glint import MINIMUM_APP as GLINT_MINIMUM_APP
        return GLINT_MINIMUM_APP
    if isinstance(value, dict) and CLOUD_SHELL_FIELDS & set(value):
        return CLOUD_SHELL_MINIMUM_APP
    if isinstance(value, dict) and "sunDisc" in value:
        return (1, 3, 0)
    return GEOMETRY_MINIMUM_APP if isinstance(value, dict) and value.get("version") == 2 else MINIMUM_APP


def capability(value):
    return GEOMETRY_CAPABILITY if value["version"] == 2 else CAPABILITY


def resolved_geometry(value):
    """Distance to centre and independent radius, in View-frame metres.

    Call validate_definition before accepting untrusted authoring input.
    Legacy profiles retain the exact 700m/sine angular-size convention.
    """
    distance = value.get("distanceMeters", 700)
    radius = value.get("radiusMeters")
    if radius is None:
        radius = distance * math.sin(math.radians(value["angularDiameterDegrees"]) / 2)
    return distance, radius
