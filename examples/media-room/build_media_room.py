#!/usr/bin/env python3
"""Build the Example Media Room: a small Package v2 Room with two Room TVs.

The checked-in `locusplace.json`, `space.json` and `provenance.json` beside this
script are the authored metadata. This script generates everything else from
source: the USD scene (simple boxes, two flat 16:9 screen quads and a
procedural painting for the art TV's off state) and the seat file. It then
packs and validates the archive with the public tools. No network, provider,
paid generation or downloaded asset is involved.

Room TVs need Locus 1.4.9 or later, so the archive declares
`minimumAppVersion: "1.4.9"`.
"""

from __future__ import annotations

import argparse
import binascii
import io
import json
import math
import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPACE_ID = "space.example-media-room"
SOURCE = HERE / "catalog" / "spaces" / SPACE_ID

# name: (diffuse RGB, roughness, metallic)
MATERIALS = {
    "Oak_Floor": ((0.42, 0.28, 0.17), 0.6, 0.0),
    "Plaster": ((0.80, 0.77, 0.71), 0.9, 0.0),
    "Walnut": ((0.25, 0.15, 0.09), 0.55, 0.0),
    "Linen": ((0.55, 0.52, 0.47), 0.95, 0.0),
    "Leather": ((0.36, 0.20, 0.12), 0.6, 0.0),
    "TV_Bezel": ((0.03, 0.03, 0.035), 0.4, 0.5),
    "Bronze_Frame": ((0.30, 0.21, 0.12), 0.35, 0.8),
    # The living TV's off state: dark glass. Not emissive.
    "Screen_Dark_Glass": ((0.012, 0.012, 0.015), 0.12, 0.0),
}
# The art TV's off state is a painting (a texture), also not emissive.
ART_MATERIAL = "Screen_Painting"
ART_TEXTURE = "painting.png"

# Axis-aligned boxes in USD meters (+Y up, -Z forward): name, min, max, material.
BOXES = [
    ("Floor", (-3.1, -0.1, -2.5), (3.1, 0.0, 2.6), "Oak_Floor"),
    ("Left_Wall", (-3.1, 0.0, -2.5), (-3.0, 2.7, 2.6), "Plaster"),
    ("Back_Wall", (-3.0, 0.0, 2.5), (3.0, 2.7, 2.6), "Plaster"),
    ("Right_Wall", (3.0, 0.0, -2.5), (3.1, 2.7, 2.6), "Plaster"),
    ("Ceiling", (-3.1, 2.7, -2.5), (3.1, 2.8, 2.6), "Plaster"),
    ("Media_Console", (-3.0, 0.0, -1.0), (-2.55, 0.45, 1.0), "Walnut"),
    ("Sofa_Base", (-0.55, 0.0, -1.1), (0.35, 0.42, 1.1), "Linen"),
    ("Sofa_Back", (0.15, 0.42, -1.1), (0.35, 0.85, 1.1), "Linen"),
    ("Sofa_Arm_North", (-0.55, 0.42, -1.1), (0.15, 0.62, -0.92), "Linen"),
    ("Sofa_Arm_South", (-0.55, 0.42, 0.92), (0.15, 0.62, 1.1), "Linen"),
    ("Coffee_Table", (-1.7, 0.0, -0.45), (-1.0, 0.42, 0.45), "Walnut"),
    ("Reading_Chair_Seat", (1.45, 0.0, -0.05), (2.15, 0.42, 0.65), "Leather"),
    ("Reading_Chair_Back", (1.45, 0.42, -0.25), (2.15, 0.95, -0.05), "Leather"),
]

INCH = 0.0254


def screen_size(diagonal_inches: float) -> tuple[float, float]:
    """Width and height in meters of a 16:9 screen with this diagonal."""
    diagonal = diagonal_inches * INCH
    return diagonal * 16 / math.hypot(16, 9), diagonal * 9 / math.hypot(16, 9)


# Each screen: entity name, diagonal, center, the visitor's "right" and the
# screen normal (toward the seat that watches it), material, frame material.
SCREENS = [
    {
        # 75" on the left wall, facing the sofa 2.9 m away.
        "name": "TV_Screen_Living", "inches": 75, "center": (-2.956, 1.2, 0.0),
        "right": (0.0, 0.0, -1.0), "normal": (1.0, 0.0, 0.0),
        "material": "Screen_Dark_Glass", "frame": "TV_Frame_Living",
        "frameMaterial": "TV_Bezel", "border": 0.015,
    },
    {
        # 55" art TV on the back wall, facing the reading chair 2.3 m away.
        "name": "TV_Screen_Art", "inches": 55, "center": (1.8, 1.45, 2.456),
        "right": (-1.0, 0.0, 0.0), "normal": (0.0, 0.0, -1.0),
        "material": ART_MATERIAL, "frame": "TV_Frame_Art",
        "frameMaterial": "Bronze_Frame", "border": 0.03,
    },
]
FRAME_DEPTH = 0.04  # The screen sits 4 mm in front of its 40 mm frame.

# Seats: id, title, eye position (USD meters), facing yaw.
SEATS = [
    ("seat.sofa", "Sofa", (-0.05, 1.15, 0.0), -math.pi / 2),
    ("seat.reading-chair", "Reading Chair", (1.8, 1.15, 0.2), math.pi),
]


def number(value: float) -> str:
    return repr(round(float(value), 6))


def point(value) -> str:
    return "(" + ", ".join(number(v) for v in value) + ")"


def add(a, b, scale=1.0):
    return tuple(x + y * scale for x, y in zip(a, b))


def frame_box(screen: dict) -> tuple:
    width, height = screen_size(screen["inches"])
    border = screen["border"]
    back = add(screen["center"], screen["normal"], -0.004 - FRAME_DEPTH)
    front = add(screen["center"], screen["normal"], -0.004)
    corners = []
    for side in (-1, 1):
        for up in (-1, 1):
            offset = add(add((0, 0, 0), screen["right"], side * (width / 2 + border)),
                         (0, 1, 0), up * (height / 2 + border))
            corners += [add(back, offset), add(front, offset)]
    low = tuple(min(c[i] for c in corners) for i in range(3))
    high = tuple(max(c[i] for c in corners) for i in range(3))
    return (screen["frame"], low, high, screen["frameMaterial"])


def all_boxes() -> list[tuple]:
    return BOXES + [frame_box(screen) for screen in SCREENS]


def box_mesh(low, high) -> str:
    points = []
    for index in range(8):
        corner = [(high if (index >> shift) & 1 else low)[axis]
                  for axis, shift in ((0, 2), (1, 1), (2, 0))]
        points.append(point(corner))
    faces = [0, 1, 3, 2, 4, 6, 7, 5, 0, 4, 5, 1, 2, 3, 7, 6, 0, 2, 6, 4, 1, 5, 7, 3]
    return (
        f"int[] faceVertexCounts = [{', '.join(['4'] * 6)}]\n"
        f"int[] faceVertexIndices = [{', '.join(map(str, faces))}]\n"
        f"point3f[] points = [{', '.join(points)}]\n"
        'uniform token subdivisionScheme = "none"\n'
    )


def screen_mesh(screen: dict) -> str:
    """One quad, counter-clockwise seen from the seat: u runs to the
    watcher's right and v upward, so a texture appears upright."""
    width, height = screen_size(screen["inches"])
    corners = []
    for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
        corners.append(add(add(screen["center"], screen["right"], (u - 0.5) * width),
                           (0, 1, 0), (v - 0.5) * height))
    normal = point(screen["normal"])
    return (
        "int[] faceVertexCounts = [4]\n"
        "int[] faceVertexIndices = [0, 1, 2, 3]\n"
        f"point3f[] points = [{', '.join(point(c) for c in corners)}]\n"
        f"normal3f[] normals = [{', '.join([normal] * 4)}] (\n"
        '    interpolation = "vertex"\n)\n'
        "texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (\n"
        '    interpolation = "vertex"\n)\n'
        'uniform token subdivisionScheme = "none"\n'
    )


def prim(name: str, body: str, material: str) -> str:
    """Blender-style export: an Xform per object holding its one Mesh."""
    lines = [
        f'    def Xform "{name}"',
        "    {",
        f'        def Mesh "{name}_Geometry" (',
        '            prepend apiSchemas = ["MaterialBindingAPI"]',
        "        )",
        "        {",
    ]
    lines += ["            " + line for line in body.rstrip("\n").split("\n")]
    lines += [
        f"            rel material:binding = </root/_materials/{material}>",
        "        }",
        "    }",
    ]
    return "\n".join(lines) + "\n"


def material(name: str, diffuse, roughness: float, metallic: float) -> str:
    return (
        f'        def Material "{name}"\n'
        "        {\n"
        f"            token outputs:surface.connect = </root/_materials/{name}/Surface.outputs:surface>\n"
        '            def Shader "Surface"\n'
        "            {\n"
        '                uniform token info:id = "UsdPreviewSurface"\n'
        f"                color3f inputs:diffuseColor = {point(diffuse)}\n"
        f"                float inputs:roughness = {number(roughness)}\n"
        f"                float inputs:metallic = {number(metallic)}\n"
        "                token outputs:surface\n"
        "            }\n"
        "        }\n"
    )


def textured_material(name: str, texture: str) -> str:
    return (
        f'        def Material "{name}"\n'
        "        {\n"
        f"            token outputs:surface.connect = </root/_materials/{name}/Surface.outputs:surface>\n"
        '            def Shader "Surface"\n'
        "            {\n"
        '                uniform token info:id = "UsdPreviewSurface"\n'
        f"                color3f inputs:diffuseColor.connect = </root/_materials/{name}/Painting.outputs:rgb>\n"
        "                float inputs:roughness = 0.7\n"
        "                float inputs:metallic = 0\n"
        "                token outputs:surface\n"
        "            }\n"
        '            def Shader "Painting"\n'
        "            {\n"
        '                uniform token info:id = "UsdUVTexture"\n'
        f"                asset inputs:file = @{texture}@\n"
        f"                float2 inputs:st.connect = </root/_materials/{name}/UV.outputs:result>\n"
        '                token inputs:sourceColorSpace = "sRGB"\n'
        "                float3 outputs:rgb\n"
        "            }\n"
        '            def Shader "UV"\n'
        "            {\n"
        '                uniform token info:id = "UsdPrimvarReader_float2"\n'
        '                string inputs:varname = "st"\n'
        "                float2 outputs:result\n"
        "            }\n"
        "        }\n"
    )


def scene_usda() -> bytes:
    parts = [
        '#usda 1.0\n(\n    defaultPrim = "root"\n    metersPerUnit = 1\n'
        '    upAxis = "Y"\n)\n\ndef Xform "root"\n{\n'
    ]
    for name, low, high, material_name in all_boxes():
        parts.append(prim(name, box_mesh(low, high), material_name))
    for screen in SCREENS:
        parts.append(prim(screen["name"], screen_mesh(screen), screen["material"]))
    parts.append('    def Scope "_materials"\n    {\n')
    for name, (diffuse, roughness, metallic) in MATERIALS.items():
        parts.append(material(name, diffuse, roughness, metallic))
    parts.append(textured_material(ART_MATERIAL, ART_TEXTURE))
    parts.append("    }\n}\n")
    return "".join(parts).encode("utf-8")


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF))


def painting_png(width: int = 512, height: int = 288) -> bytes:
    """A procedural 16:9 landscape painting: dusk sky, low sun, two hills."""
    def mix(a, b, t):
        return tuple(x + (y - x) * t for x, y in zip(a, b))

    rows = []
    for y in range(height):
        v = y / (height - 1)
        row = bytearray([0])
        for x in range(width):
            u = x / (width - 1)
            color = mix((0.93, 0.66, 0.42), (0.33, 0.42, 0.60), max(0.0, 1 - v * 1.6))
            sun = math.hypot((u - 0.68) * 16 / 9, v - 0.52)
            if sun < 0.09:
                color = mix(color, (0.99, 0.88, 0.62), min(1.0, (0.09 - sun) * 40))
            far = 0.60 + 0.05 * math.sin(u * 7.0 + 1.3) + 0.03 * math.sin(u * 17.0)
            near = 0.74 + 0.07 * math.sin(u * 4.0 + 0.4) + 0.02 * math.sin(u * 23.0 + 2.0)
            if v > far:
                color = mix((0.45, 0.43, 0.52), (0.38, 0.36, 0.44), min(1.0, (v - far) * 4))
            if v > near:
                color = mix((0.24, 0.30, 0.25), (0.15, 0.19, 0.16), min(1.0, (v - near) * 3))
            grain = ((x * 7919 + y * 104729) % 23) / 23 * 0.025 - 0.0125
            row.extend(max(0, min(255, round((c + grain) * 255))) for c in color)
        rows.append(bytes(row))
    return (b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + png_chunk(b"IEND", b""))


def usdz_bytes(layers: dict[str, bytes]) -> bytes:
    """Store every member uncompressed with 64-byte aligned data, like usdzip."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in layers.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            padding = (-(output.tell() + 30 + len(name.encode()) + 4)) % 64
            info.extra = struct.pack("<HH", 0xFFFF, padding) + bytes(padding)
            archive.writestr(info, data)
    return output.getvalue()


def teleport_points() -> dict:
    """Seats normalized to the delivered model's bounds, as Locus reads them."""
    boxes = all_boxes()
    low = [min(box[1][axis] for box in boxes) for axis in range(3)]
    high = [max(box[2][axis] for box in boxes) for axis in range(3)]
    floor = 0.0
    points = []
    for seat_id, title, eye, yaw in SEATS:
        points.append({
            "id": seat_id,
            "title": title,
            "anchorXZ": [round((eye[0] - low[0]) / (high[0] - low[0]), 6),
                         round((eye[2] - low[2]) / (high[2] - low[2]), 6)],
            "sourceFloorOffset": round(floor - low[1], 6),
            "eyeHeight": round(eye[1] - floor, 6),
            "yawRadians": round(yaw, 6),
        })
    return {"houses": {SPACE_ID: points}}


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_editable(directory: Path) -> Path:
    """Write the editable Package v2 source directory the packer reads."""
    room = directory / "catalog" / "spaces" / SPACE_ID
    room.mkdir(parents=True)
    shutil.copyfile(HERE / "locusplace.json", directory / "locusplace.json")
    for name in ("space.json", "provenance.json"):
        shutil.copyfile(SOURCE / name, room / name)
    (room / "scene.usdz").write_bytes(
        usdz_bytes({"scene.usda": scene_usda(), ART_TEXTURE: painting_png()}))
    (room / "teleport-points.json").write_bytes(json_bytes(teleport_points()))
    space = json.loads((room / "space.json").read_text(encoding="utf-8"))
    declared = {tv["entityName"] for tv in space["tvs"]}
    if declared != {screen["name"] for screen in SCREENS}:
        raise ValueError("space.json tvs must name exactly the generated screens")
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path,
                        help="absent or empty directory for the editable source and archive")
    parser.add_argument("--current-app-version", default="1.4.9",
                        help="Locus version to validate against (Room TVs need 1.4.9 or later)")
    options = parser.parse_args()
    output = options.output_directory.absolute()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"refusing to write into a non-empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    editable = write_editable(output / "media-room")
    sys.path.insert(0, str(ROOT / "tools"))
    from pack_locusplace import pack

    archive = output / "media-room.locusplace"
    summary = pack(editable, archive, current_app_version=options.current_app_version)
    print(f"VALID: {summary['packageID']} {summary['contentVersion']} -> {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
