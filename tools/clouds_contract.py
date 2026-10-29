"""Strict Package-v2 contract for motion of painted panorama clouds."""

import math

MINIMUM_APP = (1, 3, 0)
CAPABILITY = "locus.view.clouds.v1"
DEFAULTS = {
    "altitudeMeters": 1800,
    "seaDepthMeters": 0,
    "windMetersPerSecond": 4,
    "windTowardDegrees": 0,
    "cycleSeconds": 20,
    "evolution": 1.5,
    "breathing": 0.04,
}
RANGES = {
    "horizonDegrees": (-10, 10),
    "altitudeMeters": (200, 12000),
    "seaDepthMeters": (0, 5000),
    "windMetersPerSecond": (0, 30),
    "windTowardDegrees": (-360, 360),
    "cycleSeconds": (5, 120),
    "evolution": (0, 5),
    "breathing": (0, 0.15),
}


def validate_definition(value, require, asset, field="clouds"):
    require(isinstance(value, dict), field + " must be an object")
    require(
        not set(value) - {"mask", "fill"} - set(RANGES),
        field + " has unsupported fields",
    )
    require({"mask", "fill"} <= set(value), field + " requires mask and fill")
    dimensions = []
    for key in ("mask", "fill"):
        path = value[key]
        require(
            isinstance(path, str)
            and path
            and not path.startswith("/")
            and not any(part in ("", ".", "..") for part in path.split("/"))
            and path.lower().endswith(".png"),
            field + "." + key + " has invalid PNG path",
        )
        dimensions.append(asset(path, field + "." + key, grayscale=key == "mask"))
    if all(dimension is not None for dimension in dimensions):
        require(dimensions[0] == dimensions[1], field + " mask and fill sizes differ")
    for key, (low, high) in RANGES.items():
        if key in value:
            number = value[key]
            require(
                type(number) in (int, float)
                and low <= number <= high
                and math.isfinite(number),
                field + "." + key + " is out of range",
            )
    return value


def validate_images(value, directory):
    """Validate standalone authoring inputs; the actual packer verifies closure."""
    from pathlib import Path
    from PIL import Image
    import struct

    root = Path(directory).resolve()

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def asset(relative, field, grayscale=False):
        path = (root / relative).resolve()
        require(root in path.parents and path.is_file(), field + " escapes the source or is missing")
        with path.open("rb") as source:
            header = source.read(29)
        require(len(header) == 29 and header[:8] == b"\x89PNG\r\n\x1a\n", field + " must be PNG")
        width, height, depth, color = struct.unpack(">IIBB", header[16:26])
        require(depth == 8 and color == (0 if grayscale else 2), field + " has invalid 8-bit PNG color type")
        require(0 < width <= 4096 and width == height * 2, field + " must be 2:1 and at most 4096 wide")
        with Image.open(path) as image:
            image.load()
            require(image.size == (width, height), field + " has invalid image data")
        return width, height

    return validate_definition(value, require, asset)


def mask_overlap_fraction(cloud_bytes, sky_bytes):
    """Fraction of the white cloud mask replaced by a procedural-sky mask."""
    import io
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(cloud_bytes)) as image:
        clouds = image.convert("L")
        clouds.thumbnail((2048, 1024), Image.Resampling.LANCZOS)
        weight = np.asarray(clouds, dtype=np.float32) / 255
    with Image.open(io.BytesIO(sky_bytes)) as image:
        sky = image.convert("L").resize(clouds.size, Image.Resampling.BILINEAR)
        replacement = np.asarray(sky, dtype=np.float32) / 255
    total = float(weight.sum())
    return float((weight * replacement).sum()) / total if total > 0 else 0
