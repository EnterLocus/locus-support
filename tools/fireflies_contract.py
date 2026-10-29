"""Strict Package-v2 contract for View-owned drifting fireflies."""

import math

MINIMUM_APP = (1, 3, 0)
CAPABILITY = "locus.view.fireflies.v1"


def _number(value, lower, upper):
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper


def _vector(value, count, lower, upper):
    return isinstance(value, list) and len(value) == count and all(
        _number(item, lower, upper) for item in value
    )


def _keys(value, required, optional, field, require):
    require(isinstance(value, dict), field + " must be an object")
    require(not set(value) - required - optional, field + " has unsupported fields")
    require(not required - set(value), field + " is missing required fields")


def validate_definition(value, require, field="fireflies"):
    """Validate authored data. Fireflies have no package asset references."""
    _keys(value, {"volumes"}, set(), field, require)
    volumes = value["volumes"]
    require(isinstance(volumes, list) and 1 <= len(volumes) <= 4,
            field + ".volumes must contain 1...4 entries")
    seen = set()
    total = 0
    for index, volume in enumerate(volumes):
        base = "%s.volumes[%d]" % (field, index)
        _keys(volume, {"id", "centerMeters", "sizeMeters", "count"},
              {"color", "sizeMillimeters", "blink", "driftMetersPerSecond"}, base, require)
        identifier = volume["id"]
        require(isinstance(identifier, str) and identifier.strip() and identifier not in seen,
                base + ".id is invalid")
        seen.add(identifier)
        require(_vector(volume["centerMeters"], 3, -100, 100),
                base + ".centerMeters is invalid")
        require(_vector(volume["sizeMeters"], 3, 0.1, 100),
                base + ".sizeMeters is invalid")
        count = volume["count"]
        require(type(count) is int and 1 <= count <= 400,
                base + ".count is invalid")
        total += count
        require(total <= 400, field + ".volumes total count exceeds 400")
        require(_vector(volume.get("color", [0.75, 1, 0.35]), 3, 0, 1),
                base + ".color is invalid")
        require(_number(volume.get("sizeMillimeters", 6), 1, 20),
                base + ".sizeMillimeters is invalid")
        blink = volume.get("blink", {})
        _keys(blink, set(), {"periodSeconds", "duty", "jitter"}, base + ".blink", require)
        require(_number(blink.get("periodSeconds", 2.5), 1.5, 20),
                base + ".blink.periodSeconds is invalid")
        require(_number(blink.get("duty", 0.35), 0.05, 0.8),
                base + ".blink.duty is invalid")
        require(_number(blink.get("jitter", 0.5), 0, 1),
                base + ".blink.jitter is invalid")
        require(_number(volume.get("driftMetersPerSecond", 0.15), 0, 0.5),
                base + ".driftMetersPerSecond is invalid")
    return value
