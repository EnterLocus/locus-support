#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Provider-neutral equirectangular skybox preparation tools.

The commands operate only on local images.  They deliberately do not call a
generation service, change image tone, or infer missing detail.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


FACE_BASES = {
    "px": {"forward": [1, 0, 0], "right": [0, 0, 1], "down": [0, -1, 0]},
    "nx": {"forward": [-1, 0, 0], "right": [0, 0, -1], "down": [0, -1, 0]},
    "pz": {"forward": [0, 0, 1], "right": [-1, 0, 0], "down": [0, -1, 0]},
    "nz": {"forward": [0, 0, -1], "right": [1, 0, 0], "down": [0, -1, 0]},
    "py": {"forward": [0, 1, 0], "right": [1, 0, 0], "down": [0, 0, -1]},
    "ny": {"forward": [0, -1, 0], "right": [1, 0, 0], "down": [0, 0, 1]},
}
FACES = tuple(FACE_BASES)


def image_array(path):
    """Read a local image into an RGB uint8 array."""
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def save_array(path, pixels):
    image = Image.fromarray(np.asarray(pixels, dtype=np.uint8), "RGB")
    if Path(path).suffix.lower() in (".jpg", ".jpeg"):
        image.save(path, quality=100, subsampling=0)
    else:
        image.save(path)


def dimensions(pixels):
    return {"width": int(pixels.shape[1]), "height": int(pixels.shape[0])}


def bilinear_equirect(pixels, u, v):
    """Sample an equirectangular image with X wrapping and Y clamping."""
    height, width = pixels.shape[:2]
    x = np.mod(u * width - 0.5, width)
    y = np.clip(v * height - 0.5, 0, height - 1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = (x0 + 1) % width
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]
    top = pixels[y0, x0] * (1.0 - wx) + pixels[y0, x1] * wx
    bottom = pixels[y1, x0] * (1.0 - wx) + pixels[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def bilinear_square(pixels, x, y):
    """Bilinear sampling of a square face, clamped at its stored context edge."""
    side = pixels.shape[0]
    x = np.clip(x, 0, side - 1)
    y = np.clip(y, 0, side - 1)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, side - 1)
    y1 = np.minimum(y0 + 1, side - 1)
    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]
    top = pixels[y0, x0] * (1.0 - wx) + pixels[y0, x1] * wx
    bottom = pixels[y1, x0] * (1.0 - wx) + pixels[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def direction_from_uv(u, v):
    """Package-v2 convention: u=.5 faces -Z and u increases toward +X."""
    yaw = (u - 0.5) * (2.0 * math.pi)
    polar = v * math.pi
    sin_polar = np.sin(polar)
    x = sin_polar * np.sin(yaw)
    z = -sin_polar * np.cos(yaw)
    y = np.broadcast_to(np.cos(polar), x.shape)
    return np.stack((x, y, z), axis=-1)


def uv_from_direction(direction):
    direction = direction / np.linalg.norm(direction, axis=-1, keepdims=True)
    u = np.mod(0.5 + np.arctan2(direction[..., 0], -direction[..., 2]) / (2.0 * math.pi), 1.0)
    v = np.arccos(np.clip(direction[..., 1], -1.0, 1.0)) / math.pi
    return u, v


def base_arrays(face):
    base = FACE_BASES[face]
    return (np.asarray(base["forward"], dtype=np.float64),
            np.asarray(base["right"], dtype=np.float64),
            np.asarray(base["down"], dtype=np.float64))


def face_directions(face, stored_size, core_size):
    rows, columns = np.indices((stored_size, stored_size), dtype=np.float64)
    # The 90-degree core spans tangent coordinates [-1, 1], and the expanded
    # stored image keeps exactly that tangent-plane pixel scale.
    x = 2.0 * (columns + 0.5 - stored_size / 2.0) / core_size
    y = 2.0 * (rows + 0.5 - stored_size / 2.0) / core_size
    forward, right, down = base_arrays(face)
    direction = forward + x[..., None] * right + y[..., None] * down
    return direction / np.linalg.norm(direction, axis=-1, keepdims=True)


def perspective_directions(forward, size, field_of_view=30.0):
    """Directions for a square perspective review camera with half-pixel centers."""
    forward = np.asarray(forward, dtype=np.float64)
    forward /= np.linalg.norm(forward)
    up = np.array([0.0, 1.0, 0.0])
    if abs(np.dot(forward, up)) > 0.98:
        up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    down = np.cross(forward, right)
    rows, columns = np.indices((size, size), dtype=np.float64)
    scale = math.tan(math.radians(field_of_view) / 2.0)
    x = 2.0 * (columns + 0.5 - size / 2.0) / size * scale
    y = 2.0 * (rows + 0.5 - size / 2.0) / size * scale
    direction = forward + x[..., None] * right + y[..., None] * down
    return direction / np.linalg.norm(direction, axis=-1, keepdims=True)


def geometry(core_size, overlap):
    if core_size <= 0:
        raise ValueError("--core-size must be positive")
    if not 0 <= overlap < 45:
        raise ValueError("--overlap must be at least 0 and less than 45 degrees")
    stored = int(round(core_size * math.tan(math.radians(45.0 + overlap))))
    return {
        "coreSize": core_size,
        "overlapDegrees": overlap,
        "storedSize": stored,
        "fieldOfViewDegrees": 2.0 * math.degrees(math.atan(stored / float(core_size))),
        "pixelScale": {"tangentPlaneUnitsPerPixel": 2.0 / core_size},
        "halfPixelCenters": True,
        "bases": FACE_BASES,
    }


def write_metadata(outdir, data):
    (outdir / "metadata.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_roll(args):
    pixels = image_array(args.input)
    shift = int(round(pixels.shape[1] * args.degrees / 360.0))
    save_array(args.output, np.roll(pixels, shift, axis=1))
    return {"input": dimensions(pixels), "output": dimensions(pixels), "degrees": args.degrees, "pixelShift": shift}


def command_split(args):
    source = image_array(args.input)
    if source.shape[1] != 2 * source.shape[0]:
        raise ValueError("split requires an exact 2:1 equirectangular input")
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    data = geometry(args.core_size, args.overlap)
    for face in FACES:
        u, v = uv_from_direction(face_directions(face, data["storedSize"], args.core_size))
        save_array(outdir / (face + ".png"), np.rint(bilinear_equirect(source, u, v)))
    data.update({
        "format": "locus-skybox-cube-v1",
        "source": dimensions(source),
        "faceFiles": {face: face + ".png" for face in FACES},
        "coordinateConvention": "u=.5 is -Z; u increases toward +X; v=0 is +Y",
    })
    write_metadata(outdir, data)
    return {"outdir": str(outdir), "storedSize": data["storedSize"], "coreSize": args.core_size}


def read_faces(facesdir, normalize):
    facesdir = Path(facesdir)
    metadata_path = facesdir / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError("facesdir must contain metadata.json from split")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = geometry(int(metadata["coreSize"]), float(metadata["overlapDegrees"]))
    for key in ("storedSize", "coreSize"):
        if metadata.get(key) != expected[key]:
            raise ValueError("metadata geometry does not match its core size and overlap")
    if metadata.get("bases") != FACE_BASES:
        raise ValueError("metadata cube bases do not match the Locus skybox contract")
    loaded, provenance = {}, {}
    files = metadata.get("faceFiles", {})
    for face in FACES:
        file_name = files.get(face, face + ".png")
        path = facesdir / file_name
        if not path.is_file():
            raise ValueError("missing required face: " + face)
        pixels = image_array(path)
        original = dimensions(pixels)
        if pixels.shape[0] != pixels.shape[1]:
            raise ValueError("face %s must be square, got %sx%s" % (face, pixels.shape[1], pixels.shape[0]))
        if pixels.shape[0] != metadata["storedSize"]:
            if not normalize:
                raise ValueError("face %s is %s; expected square %s (use --normalize-faces explicitly)" %
                                 (face, pixels.shape[0], metadata["storedSize"]))
            pixels = np.asarray(Image.fromarray(pixels).resize(
                (metadata["storedSize"], metadata["storedSize"]), Image.Resampling.LANCZOS), dtype=np.uint8)
        loaded[face] = pixels
        provenance[face] = {
            "input": original,
            "output": dimensions(pixels),
            "normalized": pixels.shape[0] != original["width"],
            "scale": float(pixels.shape[0]) / original["width"],
        }
    return metadata, loaded, provenance


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def merged_pixels(faces, core_size, stored_size, overlap, blend, width, height):
    result = np.empty((height, width, 3), dtype=np.uint8)
    coverage = math.radians(45.0 + overlap)
    blend_radians = math.radians(blend)
    for start in range(0, height, 64):
        count = min(64, height - start)
        rows = np.arange(start, start + count, dtype=np.float64)[:, None]
        cols = np.arange(width, dtype=np.float64)[None, :]
        direction = direction_from_uv((cols + 0.5) / width, (rows + 0.5) / height)
        total = np.zeros((count, width, 3), dtype=np.float64)
        weights = np.zeros((count, width, 1), dtype=np.float64)
        for face in FACES:
            forward, right, down = base_arrays(face)
            depth = np.sum(direction * forward, axis=-1)
            x = np.sum(direction * right, axis=-1) / np.maximum(depth, 1e-12)
            y = np.sum(direction * down, axis=-1) / np.maximum(depth, 1e-12)
            angle = np.maximum(np.arctan(np.abs(x)), np.arctan(np.abs(y)))
            valid = (depth > 0) & (angle <= coverage)
            if blend_radians == 0:
                # A deterministic no-blend choice, with the central face selected by max depth.
                all_depths = np.stack([np.sum(direction * base_arrays(f)[0], axis=-1) for f in FACES])
                weight = (np.argmax(all_depths, axis=0) == FACES.index(face)).astype(np.float64)
            else:
                weight = smoothstep((math.radians(45.0) + blend_radians - angle) / (2.0 * blend_radians))
            weight = (weight * valid)[..., None]
            sx = x * core_size / 2.0 + stored_size / 2.0 - 0.5
            sy = y * core_size / 2.0 + stored_size / 2.0 - 0.5
            total += bilinear_square(faces[face], sx, sy) * weight
            weights += weight
        if np.any(weights[..., 0] <= 0):
            raise ValueError("face coverage leaves pixels uncovered; check metadata geometry")
        result[start:start + count] = np.rint(total / weights).clip(0, 255).astype(np.uint8)
    return result


def command_merge(args):
    if args.width <= 0 or args.width % 2:
        raise ValueError("--width must be a positive even equirectangular width")
    if args.blend < 0:
        raise ValueError("--blend is an angular half-width in degrees and cannot be negative")
    metadata, faces, provenance = read_faces(args.facesdir, args.normalize_faces)
    if args.blend > metadata["overlapDegrees"]:
        raise ValueError("--blend cannot exceed the stored overlap degrees")
    height = args.width // 2
    output = merged_pixels(faces, metadata["coreSize"], metadata["storedSize"],
                           metadata["overlapDegrees"], args.blend, args.width, height)
    save_array(args.output, output)
    report = {
        "format": "locus-skybox-merge-v1",
        "output": dimensions(output),
        "blendAngularHalfWidthDegrees": args.blend,
        "sourceGeometry": {key: metadata[key] for key in ("coreSize", "overlapDegrees", "storedSize")},
        "dimensionProvenance": provenance,
        "automaticToneCorrection": False,
    }
    write_path = Path(args.output).with_suffix(Path(args.output).suffix + ".merge.json")
    write_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def command_audit(args):
    source = image_array(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    horizontal = np.mean(np.abs(source[:, 1:].astype(np.float64) - source[:, :-1].astype(np.float64)))
    seam = np.mean(np.abs(source[:, 0].astype(np.float64) - source[:, -1].astype(np.float64)))
    ratio = float(seam / max(horizontal, 1e-9))
    # Alongside the scalar seam jump, keep mean bands on both sides.  These are
    # useful when a broad exposure shift is visually obvious but a single-pixel
    # edge difference is not.  Neither metric is an acceptance verdict.
    band = max(1, min(source.shape[1] // 16, 64))
    left_band = source[:, :band].astype(np.float64).mean(axis=(0, 1))
    right_band = source[:, -band:].astype(np.float64).mean(axis=(0, 1))
    if args.review_size <= 0:
        raise ValueError("--review-size must be positive")
    report = {
        "input": dimensions(source),
        "isEquirectangular2to1": source.shape[1] == 2 * source.shape[0],
        "wrapJumpRatio": ratio,
        "wrapJumpRatioDiagnosticOnly": True,
        "wrapEdgeBandMeanRGB": {"left": left_band.round(3).tolist(), "right": right_band.round(3).tolist()},
        "wrapEdgeBandDifferenceRGB": np.abs(left_band - right_band).round(3).tolist(),
        "poles": {"top": "+Y (v=0)", "bottom": "-Y (v=1)"},
        "seamDirections": {"u=0/1": "yaw -180/+180", "u=0.25": "-X", "u=0.5": "-Z", "u=0.75": "+X"},
        "note": "A wrap jump is a diagnostic, not an acceptance verdict.",
        "nativeReview": {"size": args.review_size, "faceViews": [], "edgeViews": []},
    }
    views = outdir / "views"
    views.mkdir(exist_ok=True)
    preview_size = 256
    previews = {}
    for face in FACES:
        u, v = uv_from_direction(face_directions(face, preview_size, preview_size))
        previews[face] = np.rint(bilinear_equirect(source, u, v)).astype(np.uint8)
        u, v = uv_from_direction(face_directions(face, args.review_size, args.review_size))
        file_name = "cube-" + face + ".png"
        save_array(views / file_name, np.rint(bilinear_equirect(source, u, v)))
        report["nativeReview"]["faceViews"].append("views/" + file_name)
    # All twelve cube edges get their own edge-centred camera.  These are
    # intentionally separate files: a contact-sheet thumbnail cannot prove a
    # join is visually clean at the native review size.
    edge_pairs = (("px", "py"), ("px", "ny"), ("px", "pz"), ("px", "nz"),
                  ("nx", "py"), ("nx", "ny"), ("nx", "pz"), ("nx", "nz"),
                  ("py", "pz"), ("py", "nz"), ("ny", "pz"), ("ny", "nz"))
    for first, second in edge_pairs:
        forward = base_arrays(first)[0] + base_arrays(second)[0]
        u, v = uv_from_direction(perspective_directions(forward, args.review_size))
        file_name = "edge-" + first + "-" + second + ".png"
        save_array(views / file_name, np.rint(bilinear_equirect(source, u, v)))
        report["nativeReview"]["edgeViews"].append("views/" + file_name)
    panorama = Image.fromarray(source).resize((512, 256), Image.Resampling.LANCZOS)
    # A rolled crop puts the u=0/1 seam in the middle instead of at an image
    # edge, where broad sky exposure bands are easier to inspect by eye.
    quarter = max(1, source.shape[1] // 4)
    wrap_crop = np.concatenate((source[:, -quarter:], source[:, :quarter]), axis=1)
    wrapped = Image.fromarray(wrap_crop).resize((768, 192), Image.Resampling.LANCZOS)
    sheet = Image.new("RGB", (3 * 256, 1090), "white")
    sheet.paste(panorama, (128, 26))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 4), "Original: u=0/1 seam; top +Y; bottom -Y; u=.5 -Z", fill="black")
    sheet.paste(wrapped, (0, 292))
    draw.text((8, 266), "Rolled wrap crop: seam centered for visual exposure-band inspection", fill="black")
    labels = {
        "px": "+X; R +Z; D -Y", "nx": "-X; R -Z; D -Y",
        "pz": "+Z; R -X; D -Y", "nz": "-Z; R +X; D -Y",
        "py": "+Y; R +X; D -Z", "ny": "-Y; R +X; D +Z",
    }
    for index, face in enumerate(FACES):
        x, y = (index % 3) * 256, 510 + (index // 3) * 282
        sheet.paste(Image.fromarray(previews[face]), (x, y))
        draw.text((x + 6, y + 260), face + "  " + labels[face], fill="black")
    sheet.save(outdir / "contact-sheet.png")
    (outdir / "audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def low_pass(pixels):
    return np.asarray(Image.fromarray(pixels).convert("L").resize((96, 48), Image.Resampling.LANCZOS), dtype=np.float64)


def command_compare(args):
    candidate, reference = image_array(args.candidate), image_array(args.reference)
    left, right = low_pass(candidate).ravel(), low_pass(reference).ravel()
    left -= left.mean()
    right -= right.mean()
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    report = {
        "candidate": dimensions(candidate),
        "reference": dimensions(reference),
        "exactDimensionsMatch": dimensions(candidate) == dimensions(reference),
        "lowPassLayoutNCC": None if denominator == 0 else float(np.dot(left, right) / denominator),
        "lowPassSize": {"width": 96, "height": 48},
        "detailClaim": "This metric compares low-pass layout only; it does not establish generated or preserved fine detail.",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return report


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    roll = commands.add_parser("roll", help="cyclically roll an equirectangular image")
    roll.add_argument("input", type=Path); roll.add_argument("output", type=Path)
    roll.add_argument("--degrees", type=float, default=180.0); roll.set_defaults(handler=command_roll)
    split = commands.add_parser("split", help="split equirectangular input into cube faces")
    split.add_argument("input", type=Path); split.add_argument("outdir", type=Path)
    split.add_argument("--core-size", type=int, default=1024); split.add_argument("--overlap", type=float, default=6.0)
    split.set_defaults(handler=command_split)
    merge = commands.add_parser("merge", help="merge six metadata-bound cube faces into equirectangular output")
    merge.add_argument("facesdir", type=Path); merge.add_argument("output", type=Path)
    merge.add_argument("--width", type=int, default=12288); merge.add_argument("--blend", type=float, default=0.25)
    merge.add_argument("--normalize-faces", action="store_true", help="explicitly resize model-returned square faces to metadata size")
    merge.set_defaults(handler=command_merge)
    audit = commands.add_parser("audit", help="write an equirectangular diagnostic report and contact sheet")
    audit.add_argument("input", type=Path); audit.add_argument("outdir", type=Path)
    audit.add_argument("--review-size", type=int, default=1024,
                       help="native square pixel size for individual face and edge reviews")
    audit.set_defaults(handler=command_audit)
    compare = commands.add_parser("compare", help="compare low-pass layout without claiming detail fidelity")
    compare.add_argument("candidate", type=Path); compare.add_argument("reference", type=Path); compare.add_argument("--report", type=Path)
    compare.set_defaults(handler=command_compare)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser().error(str(error))


if __name__ == "__main__":
    main()
