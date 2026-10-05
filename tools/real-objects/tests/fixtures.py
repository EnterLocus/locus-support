# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Tiny generated USDZ fixtures for the tool tests (Python 3.9 compatible, no deps).

``make_mug_usdz`` writes a tapered 16-segment cylinder (64 triangles) with an optional
texture, so inspect/rescale tests run in a second without Blender or network.
"""
import math
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.usdz import write_usdz  # noqa: E402


def png_bytes(width, height, pixel):
    """RGBA PNG; ``pixel(x, y)`` returns an (r, g, b, a) tuple of 0-255 ints."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(bytes(pixel(x, y)))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


def texture_png(kind):
    if kind == "checker":
        return png_bytes(64, 64, lambda x, y: (230, 40, 40, 255) if (x // 8 + y // 8) % 2 else (20, 20, 200, 255))
    if kind == "flat":
        return png_bytes(64, 64, lambda x, y: (128, 128, 128, 255))
    if kind == "tiny":
        return png_bytes(8, 8, lambda x, y: (200, 0, 0, 255) if (x + y) % 2 else (0, 0, 200, 255))
    if kind == "alpha":
        return png_bytes(64, 64, lambda x, y: (200, 30, 30, 255 if x < 32 else 60) if (x // 8 + y // 8) % 2 else (30, 30, 200, 255 if x < 32 else 60))
    raise ValueError(kind)


def mug_layer(height=0.095, r_bottom=0.032, r_top=0.040, segments=16, up_axis="Y",
              meters_per_unit=1.0, texture="checker", texture_path="textures/mug.png",
              opacity=None, extra_mesh=False, skeleton=False, normal_map=False):
    """Return usda text. Geometry is authored along the up axis, base at 0."""
    points, uvs = [], []

    def at(radius, h, angle):
        a, b = radius * math.cos(angle), radius * math.sin(angle)
        return (a, h, b) if up_axis == "Y" else (a, b, h)

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        points.append(at(r_bottom, 0.0, angle))
        uvs.append((i / segments, 0.0))
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        points.append(at(r_top, height, angle))
        uvs.append((i / segments, 1.0))
    points.append(at(0.0, 0.0, 0.0))
    uvs.append((0.5, 0.0))
    points.append(at(0.0, height, 0.0))
    uvs.append((0.5, 1.0))
    bottom_center, top_center = 2 * segments, 2 * segments + 1
    indices = []
    for i in range(segments):
        j = (i + 1) % segments
        indices += [i, j, segments + j, i, segments + j, segments + i]
        indices += [bottom_center, j, i]
        indices += [top_center, segments + i, segments + j]
    counts = [3] * (len(indices) // 3)

    def fmt(seq):
        return ", ".join("(" + ", ".join("%.6f" % v for v in p) + ")" for p in seq)

    def mesh(name, offset_x=0.0):
        pts = [(p[0] + offset_x, p[1], p[2]) for p in points]
        return """
    def Mesh "%s" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {
        int[] faceVertexCounts = [%s]
        int[] faceVertexIndices = [%s]
        point3f[] points = [%s]
        texCoord2f[] primvars:st = [%s] (
            interpolation = "vertex"
        )
        rel material:binding = </Mug/Looks/Paint>
        uniform token subdivisionScheme = "none"
    }
""" % (name, ", ".join(map(str, counts)), ", ".join(map(str, indices)), fmt(pts), fmt(uvs))

    surface_inputs = ""
    textures = ""
    if texture != "none":
        surface_inputs += "            color3f inputs:diffuseColor.connect = </Mug/Looks/Paint/Tex.outputs:rgb>\n"
        textures = """
        def Shader "Tex"
        {
            uniform token info:id = "UsdUVTexture"
            asset inputs:file = @%s@
            float2 inputs:st.connect = </Mug/Looks/Paint/Uv.outputs:result>
            float3 outputs:rgb
            float outputs:a
        }

        def Shader "Uv"
        {
            uniform token info:id = "UsdPrimvarReader_float2"
            string inputs:varname = "st"
            float2 outputs:result
        }
""" % texture_path
        if texture == "alpha":
            surface_inputs += "            float inputs:opacity.connect = </Mug/Looks/Paint/Tex.outputs:a>\n"
    else:
        surface_inputs += "            color3f inputs:diffuseColor = (0.5, 0.5, 0.5)\n"
    if normal_map:
        surface_inputs += "            normal3f inputs:normal.connect = </Mug/Looks/Paint/NormalTex.outputs:rgb>\n"
        textures += """
        def Shader "NormalTex"
        {
            uniform token info:id = "UsdUVTexture"
            asset inputs:file = @textures/normal.png@
            float2 inputs:st.connect = </Mug/Looks/Paint/Uv.outputs:result>
            float3 outputs:rgb
        }
"""
    if opacity is not None:
        surface_inputs += "            float inputs:opacity = %s\n" % opacity

    skel = ""
    if skeleton:
        skel = """
    def SkelRoot "Rig"
    {
        def Skeleton "Skel"
        {
            uniform token[] joints = ["root"]
        }
    }
"""
    return """#usda 1.0
(
    defaultPrim = "Mug"
    metersPerUnit = %s
    upAxis = "%s"
)

def Xform "Mug"
{
%s%s%s
    def Scope "Looks"
    {
        def Material "Paint"
        {
            token outputs:surface.connect = </Mug/Looks/Paint/Surface.outputs:surface>

            def Shader "Surface"
            {
                uniform token info:id = "UsdPreviewSurface"
%s                token outputs:surface
            }
%s        }
    }
}
""" % (meters_per_unit, up_axis, mesh("Body"), mesh("Handle", 0.05) if extra_mesh else "", skel,
       surface_inputs, textures)


def make_mug_usdz(path, **kwargs):
    texture = kwargs.get("texture", "checker")
    layer = mug_layer(**kwargs)
    entries = [("mug.usda", layer.encode("utf-8"))]
    if texture != "none" and kwargs.get("texture_path", "textures/mug.png") == "textures/mug.png":
        entries.append(("textures/mug.png", texture_png(texture)))
    if kwargs.get("normal_map"):
        entries.append(("textures/normal.png", texture_png("flat")))
    write_usdz(path, entries)
    return path
