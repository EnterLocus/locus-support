#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standalone Room v14 ``mode: "irradiance"`` light-layer baker for headless Blender.

Bakes albedo-free per-group diffuse irradiance maps onto ``LocusIndirectUV``
(UV1) so Locus multiplies ``irradiance(UV1) * baseColor(UV0) * (1 - metallic) * ao``
at runtime without softening high-frequency UV0 surface textures.

Validate a declarative ``bake-config.json`` with ordinary Python 3.9+:
  python3 .agents/skills/build-original-locus-room/scripts/bake_irradiance.py \\
      --output-root /abs/path/to/work --config /abs/path/to/bake-config.json \\
      --validate-config-only

Run the full Cycles bake inside headless Blender (for example Blender 5.2+):
  blender --background --factory-startup --python-exit-code 1 \\
      --python .agents/skills/build-original-locus-room/scripts/bake_irradiance.py -- \\
      --output-root /abs/path/to/work --config /abs/path/to/bake-config.json \\
      [--width 2048 --height 1024 --direct-samples 96 --indirect-samples 128]
"""

from __future__ import annotations

import argparse
from array import array
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

INDIRECT_ROOT = "Locus_BakedIndirect"
INDIRECT_UV = "LocusIndirectUV"
GUTTER_PX = 16
CHART_GAP_PX = 5
LOW_PASS_RADIUS = 4
LOW_PASS_PASSES = 2

METAL_WORDS = ("Brass", "Bronze", "Steel", "Chrome", "Iron", "Aluminum", "Aluminium")
CYCLES_KEYS = (
    "max_bounces", "diffuse_bounces", "glossy_bounces", "transmission_bounces",
    "volume_bounces", "transparent_max_bounces", "samples", "preview_samples",
    "use_adaptive_sampling", "seed", "use_animated_seed",
)

SEMANTIC_LIGHT_ROLES = ("overheads", "chandelier", "accent", "task", "cove", "outdoor", "decorative")
PRIMARY_OVERHEAD_ROLES = frozenset(("overheads", "chandelier"))
SMALL_MOOD_ROLES = frozenset(("accent", "task", "cove"))
SHADED_FIXTURE_KINDS = frozenset(("floor_lamp", "table_lamp", "desk_lamp", "reading_lamp"))
LINEAR_FIXTURE_KINDS = frozenset(("linear_strip", "cove_strip", "shelf_strip", "step_strip"))

SCALE_BUDGETS = {
    "standard": {
        "max_light_layers": 6,
        "max_light_layer_width": 2048,
        "max_light_layer_height": 2048,
        "max_light_layer_ram_mib": 192.0,
    },
    "large": {
        "max_light_layers": 6,
        "max_light_layer_width": 4096,
        "max_light_layer_height": 2048,
        "max_light_layer_ram_mib": 512.0,
    },
}


def _finding(
    code: str,
    severity: str,
    message: str,
    subject: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if subject:
        out["subject"] = subject
    if details:
        out["details"] = details
    return out


def kelvin_rgb(kelvin: float) -> Tuple[float, float, float]:
    temperature = max(1_000.0, min(12_000.0, float(kelvin))) / 100.0
    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
        blue = 0.0 if temperature <= 19.0 else (
            138.5177312231 * math.log(temperature - 10.0) - 305.0447927307
        )
    else:
        red = 329.698727446 * ((temperature - 60.0) ** -0.1332047592)
        green = 288.1221695283 * ((temperature - 60.0) ** -0.0755148492)
        blue = 255.0
    return (
        max(0.0, min(255.0, red)) / 255.0,
        max(0.0, min(255.0, green)) / 255.0,
        max(0.0, min(255.0, blue)) / 255.0,
    )


def separable_box_blur_rgba(
    pixels: array,
    width: int,
    height: int,
    *,
    radius: int,
    passes: int,
) -> array:
    """Low-pass RGB in scene-linear float while preserving alpha."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if radius < 0 or passes < 0:
        raise ValueError("radius and passes cannot be negative")
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA pixel count does not match width and height")
    if radius == 0 or passes == 0:
        return array("f", pixels)

    try:
        import numpy as np  # type: ignore
    except ImportError:
        np = None

    if np is not None:
        buf = np.frombuffer(pixels, dtype=np.float32).reshape(height, width, 4).copy()
        rgb = buf[:, :, :3]
        xs = np.arange(width)
        x_lo = np.maximum(0, xs - radius)
        x_hi = np.minimum(width - 1, xs + radius)
        x_cnt = (x_hi - x_lo + 1).reshape(1, width, 1)
        ys = np.arange(height)
        y_lo = np.maximum(0, ys - radius)
        y_hi = np.minimum(height - 1, ys + radius)
        y_cnt = (y_hi - y_lo + 1).reshape(height, 1, 1)
        for _ in range(passes):
            cs_x = np.concatenate(
                [np.zeros((height, 1, 3), dtype=np.float64), np.cumsum(rgb, axis=1, dtype=np.float64)],
                axis=1,
            )
            rgb = ((cs_x[:, x_hi + 1, :] - cs_x[:, x_lo, :]) / x_cnt).astype(np.float32)
            cs_y = np.concatenate(
                [np.zeros((1, width, 3), dtype=np.float64), np.cumsum(rgb, axis=0, dtype=np.float64)],
                axis=0,
            )
            rgb = ((cs_y[y_hi + 1, :, :] - cs_y[y_lo, :, :]) / y_cnt).astype(np.float32)
        buf[:, :, :3] = rgb
        out = array("f")
        out.frombytes(buf.tobytes())
        return out

    result = array("f", pixels)
    for _ in range(passes):
        horizontal = array("f", result)
        for y in range(height):
            row = y * width
            for channel in range(3):
                running = 0.0
                right = min(width - 1, radius)
                for x in range(right + 1):
                    running += result[(row + x) * 4 + channel]
                for x in range(width):
                    left = max(0, x - radius)
                    right = min(width - 1, x + radius)
                    horizontal[(row + x) * 4 + channel] = running / (right - left + 1)
                    outgoing = x - radius
                    incoming = x + radius + 1
                    if outgoing >= 0:
                        running -= result[(row + outgoing) * 4 + channel]
                    if incoming < width:
                        running += result[(row + incoming) * 4 + channel]
        vertical = array("f", horizontal)
        for x in range(width):
            for channel in range(3):
                running = 0.0
                bottom = min(height - 1, radius)
                for y in range(bottom + 1):
                    running += horizontal[(y * width + x) * 4 + channel]
                for y in range(height):
                    top = max(0, y - radius)
                    bottom = min(height - 1, y + radius)
                    vertical[(y * width + x) * 4 + channel] = running / (bottom - top + 1)
                    outgoing = y - radius
                    incoming = y + radius + 1
                    if outgoing >= 0:
                        running -= horizontal[(outgoing * width + x) * 4 + channel]
                    if incoming < height:
                        running += horizontal[(incoming * width + x) * 4 + channel]
        result = vertical
    return result


def validate_light_groups(
    light_groups: Sequence[Dict[str, Any]],
    scale: str = "standard",
    layer_resolution: Optional[Tuple[int, int]] = None,
) -> List[Dict[str, Any]]:
    """Enforce semantic mood-layer lighting rules and physical emitter hygiene."""
    findings: List[Dict[str, Any]] = []
    budgets = SCALE_BUDGETS.get(scale, SCALE_BUDGETS["standard"])

    if not light_groups:
        findings.append(_finding(
            "LIGHTING_NO_GROUPS", "Blocker",
            "bake-config.json must declare at least one semantic group in lightGroups",
        ))
        return findings

    baked_groups = [g for g in light_groups if g.get("bakedLayer", True)]
    if len(baked_groups) > budgets["max_light_layers"]:
        findings.append(_finding(
            "LIGHTING_TOO_MANY_LAYERS", "Blocker",
            "{} baked light layers exceed ceiling of {} for scale={!r}".format(
                len(baked_groups), budgets["max_light_layers"], scale
            ),
        ))

    if layer_resolution is not None:
        w, h = int(layer_resolution[0]), int(layer_resolution[1])
        ram_mib = (w * h * 8.0 * len(baked_groups)) / (1024.0 * 1024.0)
        if w > budgets["max_light_layer_width"] or h > budgets["max_light_layer_height"]:
            findings.append(_finding(
                "LIGHTING_LAYER_RES_TOO_HIGH", "High",
                "Light layer resolution {}x{} exceeds {}x{} guideline for scale={!r}".format(
                    w, h, budgets["max_light_layer_width"], budgets["max_light_layer_height"], scale
                ),
            ))
        if ram_mib > budgets["max_light_layer_ram_mib"]:
            findings.append(_finding(
                "LIGHTING_LAYER_RAM_EXCEEDED", "Blocker",
                "Resident Float16 light layers estimate {:.1f} MiB > {:.1f} MiB budget".format(
                    ram_mib, budgets["max_light_layer_ram_mib"]
                ),
            ))

    seen_ids = set()
    roles_present = set()
    for group in light_groups:
        gid = group.get("id", "<unnamed-group>")
        if gid in seen_ids:
            findings.append(_finding(
                "LIGHTING_DUPLICATE_GROUP", "Blocker",
                "Duplicate light group id {!r}".format(gid),
                subject=gid,
            ))
        seen_ids.add(gid)

        role = group.get("role")
        if role not in SEMANTIC_LIGHT_ROLES:
            findings.append(_finding(
                "LIGHTING_INVALID_ROLE", "Blocker",
                "Light group {} has role {!r}; expected one of {}".format(gid, role, SEMANTIC_LIGHT_ROLES),
                subject=gid,
            ))
        else:
            roles_present.add(role)

        fixture_roles = set()
        kelvins = set()
        colored_flags = set()
        fixtures = group.get("fixtures", [])
        if not fixtures:
            findings.append(_finding(
                "LIGHTING_EMPTY_GROUP", "High",
                "Light group {} declares zero fixtures".format(gid),
                subject=gid,
            ))
        for fx in fixtures:
            fx_id = fx.get("id", gid)
            fx_role = fx.get("role", role)
            if fx_role:
                fixture_roles.add(fx_role)
            colored_flags.add(bool(fx.get("isColored", False)))
            if "kelvin" in fx:
                kelvins.add(int(fx["kelvin"]))

            kind = str(fx.get("kind", "")).lower()
            emitter = str(fx.get("emitterType", "")).lower()
            if kind in SHADED_FIXTURE_KINDS and emitter == "point":
                findings.append(_finding(
                    "LIGHTING_UNSHADED_LAMP_POINT", "Blocker",
                    "Fixture {} ({}) uses bare omnidirectional 'point' emitter; use directional 'spot' (down + weak up) so shaded lamps do not wash out the whole room".format(fx_id, kind),
                    subject=fx_id,
                ))
            if kind in LINEAR_FIXTURE_KINDS and emitter in ("spot", "point"):
                findings.append(_finding(
                    "LIGHTING_LINEAR_AS_SPOT", "High",
                    "Linear strip fixture {} uses '{}' emitter; use rectangular 'area' or 'emissive_mesh'".format(fx_id, emitter),
                    subject=fx_id,
                ))
            lumens = fx.get("lumens")
            if lumens is not None:
                lm = float(lumens)
                if kind in ("desk_lamp", "reading_lamp") and lm > 300.0:
                    findings.append(_finding(
                        "LIGHTING_DESK_LAMP_OVERBRIGHT", "High",
                        "Task lamp {} set to {:.0f} lm (> 300 lm guideline to prevent desktop glare)".format(fx_id, lm),
                        subject=fx_id,
                    ))
                if lm <= 0.0 and emitter != "emissive_mesh":
                    findings.append(_finding(
                        "LIGHTING_ZERO_LUMENS", "High",
                        "Fixture {} has non-positive lumens ({})".format(fx_id, lm),
                        subject=fx_id,
                    ))

        if (fixture_roles & PRIMARY_OVERHEAD_ROLES) and (fixture_roles & SMALL_MOOD_ROLES):
            findings.append(_finding(
                "LIGHTING_MIXED_QUADRANT_GROUP", "Blocker",
                "Light group {} mixes overhead ({}) and small-mood ({}) fixtures; split by mood layer so primary overheads can turn off independently".format(
                    gid,
                    sorted(fixture_roles & PRIMARY_OVERHEAD_ROLES),
                    sorted(fixture_roles & SMALL_MOOD_ROLES),
                ),
                subject=gid,
            ))

        if len(colored_flags) > 1:
            findings.append(_finding(
                "LIGHTING_MIXED_COLORED_AND_WARM", "Blocker",
                "Light group {} mixes colored and warm-white fixtures (runtime tints untextured glows per group)".format(gid),
                subject=gid,
            ))

        if len(kelvins) >= 2 and (max(kelvins) - min(kelvins)) > 600:
            findings.append(_finding(
                "LIGHTING_WIDE_KELVIN_SPREAD", "Medium",
                "Light group {} spans {}K..{}K (> 600K spread inside one group)".format(gid, min(kelvins), max(kelvins)),
                subject=gid,
            ))

    if len(baked_groups) >= 2 and not (roles_present & SMALL_MOOD_ROLES):
        findings.append(_finding(
            "LIGHTING_NO_SMALL_MOOD_LAYER", "High",
            "Room has {} baked groups but none with a small-mood role ({}); visitors need an accent/task/cove layer when overheads turn off".format(
                len(baked_groups), sorted(SMALL_MOOD_ROLES)
            ),
        ))

    return findings


def validate_bake_config(config: Dict[str, Any], width: int, height: int) -> Dict[str, Any]:
    """Validate declarative bake-config.json before starting Blender Cycles."""
    findings = validate_light_groups(
        config.get("lightGroups", []),
        scale=config.get("scale", "standard"),
        layer_resolution=(width, height),
    )
    if not config.get("rootName"):
        findings.append(_finding(
            "BAKE_CONFIG_NO_ROOT", "Blocker",
            "bake-config.json requires rootName",
        ))
    blockers = [f for f in findings if f["severity"] == "Blocker"]
    highs = [f for f in findings if f["severity"] == "High"]
    return {
        "passed": len(blockers) == 0 and len(highs) == 0,
        "blockerCount": len(blockers),
        "highCount": len(highs),
        "findings": findings,
    }


def compute_irradiance_scale(peak_linear: float, p99999_linear: Optional[float] = None) -> float:
    """Compute a shared HDR irradianceScale in [1.0, 64.0] with headroom above peak."""
    if not math.isfinite(peak_linear) or peak_linear <= 1.0:
        return 1.0
    if peak_linear <= 32.0:
        target = peak_linear * 1.02
    else:
        p = p99999_linear if (p99999_linear is not None and math.isfinite(p99999_linear)) else peak_linear
        target = max(p * 1.15, 16.0)
    return round(min(max(math.ceil(target * 100.0) / 100.0, 1.0), 64.0), 4)


def _shelf_pack(sizes: Sequence[Tuple[int, int]], width: int, height: int) -> Optional[List[Tuple[int, int]]]:
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    skyline = [(0, width, 0)]
    placed: List[Optional[Tuple[int, int]]] = [None] * len(sizes)
    for i in order:
        w, h = sizes[i][0] + GUTTER_PX, sizes[i][1] + GUTTER_PX
        best = None
        for start in range(len(skyline)):
            x = skyline[start][0]
            if x + w > width + GUTTER_PX:
                break
            top, span, j = 0, 0, start
            while span < w and j < len(skyline):
                top = max(top, skyline[j][2])
                span = skyline[j][0] + skyline[j][1] - x
                j += 1
            if span < w or top + h > height + GUTTER_PX:
                continue
            if best is None or top < best[1] or (top == best[1] and x < best[0]):
                best = (x, top)
        if best is None:
            return None
        x, top = best
        placed[i] = (x, top)
        new = []
        for sx, sw, sy in skyline:
            for a, b in ((sx, min(sx + sw, x)), (max(sx, x + w), sx + sw)):
                if b > a:
                    new.append((a, b - a, sy))
        new.append((x, w, top + h))
        new.sort()
        merged = []
        for seg in new:
            if merged and merged[-1][2] == seg[2] and merged[-1][0] + merged[-1][1] == seg[0]:
                merged[-1] = (merged[-1][0], merged[-1][1] + seg[1], seg[2])
            else:
                merged.append(seg)
        skyline = merged
    return placed  # type: ignore


def _fit(demands, width: int, height: int):
    lo, hi = 0.1, 4000.0
    for _ in range(40):
        k = (lo + hi) / 2.0
        if _shelf_pack([d(k) for d in demands], width, height) is None:
            hi = k
        else:
            lo = k
    sizes = [d(lo) for d in demands]
    return lo, sizes, _shelf_pack(sizes, width, height)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    raw = list(argv) if argv is not None else sys.argv[1:]
    if "--" in raw:
        raw = raw[raw.index("--") + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True, help="Path to declarative bake-config.json")
    parser.add_argument("--blend-name", default="")
    parser.add_argument("--width", type=int, default=2048)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--direct-samples", type=int, default=96)
    parser.add_argument("--indirect-samples", type=int, default=128)
    parser.add_argument("--reuse-existing-uv", action="store_true")
    parser.add_argument("--keep-blend-atlas", action="store_true")
    parser.add_argument("--groups", default="", help="Comma-separated subset of group IDs (scratch)")
    parser.add_argument("--validate-config-only", action="store_true", help="Validate bake-config.json without launching Cycles")
    return parser.parse_args(raw)


def _run_blender_bake(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    import bpy  # type: ignore
    import numpy as np  # type: ignore

    output = args.output_root.expanduser().resolve()
    blend_name = args.blend_name or config.get("blendName", "room.blend")
    bpy.ops.wm.open_mainfile(filepath=str(output / blend_name))
    scene = bpy.context.scene

    def principled(material):
        if not material.use_nodes:
            raise RuntimeError("Receiver material {} is not node-based".format(material.name))
        nodes = [n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"]
        if len(nodes) != 1:
            raise RuntimeError("Receiver material {} needs exactly one Principled BSDF".format(material.name))
        return nodes[0]

    def create_indirect_image(name: str, width: int, height: int):
        img = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=True)
        img.generated_color = (0.0, 0.0, 0.0, 1.0)
        img.colorspace_settings.name = "Linear Rec.709"
        return img

    def save_indirect_image(image, path: Path) -> None:
        export_scene = bpy.data.scenes.new("Locus_Indirect_Texture_Encoding")
        try:
            export_scene.display_settings.display_device = "sRGB"
            export_scene.view_settings.view_transform = "Standard"
            export_scene.view_settings.look = "None"
            export_scene.view_settings.exposure = 0.0
            export_scene.view_settings.gamma = 1.0
            export_scene.render.dither_intensity = 0.0
            settings = export_scene.render.image_settings
            settings.file_format = "PNG"
            settings.color_mode = "RGB"
            settings.color_depth = "16"
            settings.compression = 15
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_render(str(path), scene=export_scene)
        finally:
            bpy.data.scenes.remove(export_scene)
        image.filepath = str(path)
        image.source = "FILE"
        image.colorspace_settings.name = "sRGB"
        image.reload()

    def configure_cycles(*, include_color: bool) -> None:
        scene.render.engine = "CYCLES"
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.seed = 0
        scene.cycles.use_animated_seed = False
        scene.cycles.preview_samples = 16
        scene.cycles.max_bounces = 4
        scene.cycles.diffuse_bounces = 3
        scene.cycles.glossy_bounces = 1
        scene.cycles.transmission_bounces = 1
        scene.render.bake.target = "IMAGE_TEXTURES"
        scene.render.bake.margin = 8
        scene.render.bake.margin_type = "EXTEND"
        scene.render.bake.use_pass_color = bool(include_color)
        for obj in scene.objects:
            if obj.type == "LIGHT":
                obj.hide_render = not obj.name.startswith("_BAKE_")
            if obj.name.startswith("_PREVIEW"):
                obj.hide_render = True
        if scene.world and scene.world.use_nodes:
            for node in scene.world.node_tree.nodes:
                if node.type == "BACKGROUND":
                    node.inputs["Strength"].default_value = 0.0

    def low_pass_image(image) -> None:
        width, height = image.size
        buf = array("f", [0.0]) * len(image.pixels)
        image.pixels.foreach_get(buf)
        filtered = separable_box_blur_rgba(buf, width, height, radius=LOW_PASS_RADIUS, passes=LOW_PASS_PASSES)
        image.pixels.foreach_set(filtered)
        image.update()

    cycles_state = {k: getattr(scene.cycles, k) for k in CYCLES_KEYS}
    world_state = None
    if scene.world and scene.world.use_nodes:
        world_state = [
            (n, n.inputs["Strength"].default_value)
            for n in scene.world.node_tree.nodes
            if n.type == "BACKGROUND"
        ]

    root = bpy.data.objects[config["rootName"]]
    manifest_path = output / config.get("manifestName", "space.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    excluded = set(config.get("excludedEntities", []))
    desk_groups = list(config.get("deskGroups", []))
    layer_scale = float(config.get("layerScale", 1.0))
    atlas_name = config.get("atlasName", "{}-irradiance".format(manifest.get("id", "room").replace("space.", "")))

    groups = manifest["lighting"]["luminaireGroups"]
    luminaires = {n for g in groups for n in g["entities"]}
    luminaire_meshes = {
        o for n in luminaires if bpy.data.objects.get(n) is not None
        for o in [bpy.data.objects[n], *bpy.data.objects[n].children_recursive]
        if o.type == "MESH"
    }

    def is_metal(obj) -> bool:
        names = [m.name for m in obj.data.materials if m]
        return bool(names) and all(any(w in n for w in METAL_WORDS) for n in names)

    def is_generated_prop(obj) -> bool:
        return bool(obj.get("locus_generated_prop")) or any(
            "Generated" in (m.name if m else "") for m in obj.data.materials
        )

    def receiver_weight(obj) -> float:
        n = obj.name
        if is_generated_prop(obj):
            return 6.0
        near = ("Chair", "Stool", "Sofa", "Daybed", "Pillow", "Table", "Desk", "Island", "Book", "Vase", "Rug", "Linen", "Boucle", "Art", "Bench")
        if any(k in n for k in near):
            return 3.0
        if any(k in n for k in ("Floor", "Stair", "Hearth", "TV_Screen")):
            return 1.4
        if any(k in n for k in ("Leaves", "Bark", "Mulch", "Pebbles", "Firebox")):
            return 0.5
        return 1.0

    def world_area(obj) -> float:
        scale_det = abs(obj.matrix_world.to_3x3().determinant()) ** (2.0 / 3.0)
        return max(sum(p.area for p in obj.data.polygons) * scale_det, 1e-4)

    def chart_count(mesh, uv_name: str) -> int:
        parent = list(range(len(mesh.polygons)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        uv = mesh.uv_layers[uv_name].data
        edges = {}
        for poly in mesh.polygons:
            corners = [
                (mesh.loops[i].vertex_index, (round(float(uv[i].uv.x), 6), round(float(uv[i].uv.y), 6)))
                for i in poly.loop_indices
            ]
            for i, c in enumerate(corners):
                c1 = corners[(i + 1) % len(corners)]
                key = (c, c1) if c <= c1 else (c1, c)
                parent[find(poly.index)] = find(edges.setdefault(key, poly.index))
        return len({find(i) for i in range(len(parent))})

    def uv_extent(obj, uv_name: str):
        uv = obj.data.uv_layers[uv_name].data
        us = [c.uv.x for c in uv]
        vs = [c.uv.y for c in uv]
        area = 0.0
        for poly in obj.data.polygons:
            pts = [uv[i].uv.copy() for i in poly.loop_indices]
            area += abs(sum(a.x * b.y - b.x * a.y for a, b in zip(pts, pts[1:] + pts[:1]))) / 2.0
        return min(us), min(vs), max(max(us) - min(us), 1e-9), max(max(vs) - min(vs), 1e-9), area

    # Select opaque non-emissive receivers
    receivers = []
    for obj in root.children_recursive:
        if obj.type != "MESH" or obj.name in excluded or obj.name in luminaires or is_metal(obj):
            continue
        skip = False
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            shader = principled(mat)
            if shader.inputs["Transmission Weight"].default_value > 1e-4 or shader.inputs["Alpha"].default_value < 0.999:
                skip = True
                break
            if shader.inputs["Emission Strength"].default_value > 1e-6 and "__LocusIndirect__" not in mat.name:
                if not shader.inputs["Emission Color"].is_linked and max(shader.inputs["Emission Color"].default_value[:3]) == 0:
                    shader.inputs["Emission Strength"].default_value = 0.0
                else:
                    skip = True
                    break
        if not skip:
            receivers.append(obj)

    if not receivers:
        raise RuntimeError("No eligible baked receivers found under {}".format(config["rootName"]))

    for dname in desk_groups:
        if bpy.data.objects.get(dname) is not None:
            bpy.data.objects[dname]["locus_desk_group_for"] = dname

    # Strip previous Locus indirect nodes on rebake and attach non-grouped receivers under Locus_BakedIndirect
    indirect = bpy.data.objects.get(INDIRECT_ROOT)
    if indirect is None:
        indirect = bpy.data.objects.new(INDIRECT_ROOT, None)
        scene.collection.objects.link(indirect)
        indirect.parent = root

    for obj in receivers:
        for index, source in enumerate(list(obj.data.materials)):
            if source is None or not source.use_nodes:
                continue
            nodes = source.node_tree.nodes
            if nodes.get("Locus_BakedIndirect_Texture") is not None:
                mat = source.copy()
                mnodes = mat.node_tree.nodes
                for nname in ("Locus_BakedIndirect_Texture", "Locus_BakedIndirect_UV"):
                    n = mnodes.get(nname)
                    if n is not None:
                        mnodes.remove(n)
                sh = principled(mat)
                sh.inputs["Emission Color"].default_value = (0, 0, 0, 1)
                sh.inputs["Emission Strength"].default_value = 0.0
                mat.name = source.name.split("__LocusIndirect__", 1)[0]
                obj.data.materials[index] = mat
        in_own_group = (obj.parent is not None and "locus_desk_group_for" in obj.parent) or bool(obj.get("locus_baked_own_entity"))
        if not in_own_group and obj.parent != indirect:
            world_xf = obj.matrix_world.copy()
            obj.parent = indirect
            obj.matrix_world = world_xf

    # Unwrap / pack UV1 (LocusIndirectUV) unless --reuse-existing-uv is set
    original_uvs = {}
    blocks = {}
    if not args.reuse_existing_uv:
        bpy.ops.object.select_all(action="DESELECT")
        scene.tool_settings.use_uv_select_sync = True
        for obj in receivers:
            obj.data = obj.data.copy()
            base = next((layer.name for layer in obj.data.uv_layers if layer.active_render), None)
            if base is None:
                layer = obj.data.uv_layers.new(name="st")
                layer.active_render = True
                base = layer.name
            original_uvs[obj.name] = base
            if obj.data.uv_layers.get(INDIRECT_UV) is not None:
                obj.data.uv_layers.remove(obj.data.uv_layers[INDIRECT_UV])
            keep_src = is_generated_prop(obj)
            obj.data.uv_layers.active = obj.data.uv_layers[base]
            layer = obj.data.uv_layers.new(name=INDIRECT_UV, do_init=keep_src)
            obj.data.uv_layers.active = layer
            if not keep_src:
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project(
                    angle_limit=math.radians(66), island_margin=0.0,
                    area_weight=0.2, correct_aspect=True, scale_to_bounds=False,
                )
                bpy.ops.object.mode_set(mode="OBJECT")
                obj.select_set(False)
            else:
                obj["locus_bake_source_uv"] = True
            obj.data.uv_layers[base].active_render = True

        charts = {obj.name: chart_count(obj.data, INDIRECT_UV) for obj in receivers}
        floor_px = {obj.name: 4.0 * math.sqrt(max(1, charts[obj.name])) for obj in receivers}
        need = [world_area(o) * receiver_weight(o) for o in receivers]
        _, squares, _ = _fit(
            [lambda k, a=a, o=o: (int(max(24, floor_px[o.name], k * math.sqrt(a))),) * 2 for a, o in zip(need, receivers)],
            args.width, args.height,
        )
        for obj, (s, _) in zip(receivers, squares):
            if obj.get("locus_bake_source_uv"):
                continue
            gap = max(1.0, min(CHART_GAP_PX, 0.2 * s / math.sqrt(max(1, charts[obj.name]))))
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            obj.data.uv_layers.active = obj.data.uv_layers[INDIRECT_UV]
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="ADD", margin=gap / s, shape_method="AABB")
            bpy.ops.object.mode_set(mode="OBJECT")
            obj.select_set(False)

        extents = [uv_extent(o, INDIRECT_UV) for o in receivers]

        def demand(k, a, o, ext):
            _, _, ew, eh, uv_area = ext
            fill = max(uv_area / (ew * eh), 0.05)
            px = max(k * k * a / fill, floor_px[o.name] ** 2, 24 * 24)
            w = math.sqrt(px * ew / eh)
            return int(max(24, min(args.width, w))), int(max(24, px / max(24, min(args.width, w))))

        _, sizes, placed = _fit(
            [lambda k, a=a, o=o, e=e: demand(k, a, o, e) for a, o, e in zip(need, receivers, extents)],
            args.width, args.height,
        )
        for obj, (bw, bh), (x, y), (u0, v0, ew, eh, _) in zip(receivers, sizes, placed, extents):
            uv = obj.data.uv_layers[INDIRECT_UV].data
            for corner in uv:
                u, v = (corner.uv.x - u0) / ew, (corner.uv.y - v0) / eh
                corner.uv = ((x + u * bw) / args.width, (y + v * bh) / args.height)
            *_, uv_area = uv_extent(obj, INDIRECT_UV)
            texels = math.sqrt(uv_area * args.width * args.height / max(world_area(obj), 1e-9))
            blocks[obj.name] = {
                "blockPx": [bw, bh], "at": [x, y], "weight": receiver_weight(obj),
                "areaM2": round(world_area(obj), 2), "charts": charts[obj.name], "texelsPerMeter": round(texels, 1),
            }
    else:
        for obj in receivers:
            base = next((layer.name for layer in obj.data.uv_layers if layer.active_render), "st")
            original_uvs[obj.name] = base
            if obj.data.uv_layers.get(INDIRECT_UV) is None:
                raise RuntimeError("--reuse-existing-uv requires {} on {}".format(INDIRECT_UV, obj.name))

    image = create_indirect_image(atlas_name, args.width, args.height)

    # Deduplicate indirect materials per base material to avoid shader/VRAM bloat
    indirect_by_base: Dict[Any, Any] = {}
    for obj in receivers:
        for slot_index, source in enumerate(list(obj.data.materials)):
            if source is None:
                continue
            mat = indirect_by_base.get(source)
            if mat is None:
                mat = source.copy()
                mat.name = "{}__LocusIndirect__shared".format(source.name)
                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                shader = principled(mat)
                texture = nodes.new("ShaderNodeTexImage")
                texture.name = "Locus_BakedIndirect_Texture"
                texture.label = "Locus baked irradiance"
                texture.image = image
                uv = nodes.new("ShaderNodeUVMap")
                uv.name = "Locus_BakedIndirect_UV"
                uv.uv_map = INDIRECT_UV
                links.new(uv.outputs["UV"], texture.inputs["Vector"])
                shader.inputs["Emission Strength"].default_value = 0.0
                nodes.active = texture
                texture.select = True
                indirect_by_base[source] = mat
            obj.data.materials[slot_index] = mat

    emissive = {}
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree.nodes.get("Principled BSDF") is not None:
            strength = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
            if strength.default_value > 0 and "__LocusIndirect__" not in mat.name:
                emissive[mat] = strength.default_value
    glass = [
        o for o in root.children_recursive if o.type == "MESH" and o not in receivers
        and any(m and m.use_nodes and principled(m).inputs["Transmission Weight"].default_value > 1e-4 for m in o.data.materials)
    ]
    shadow_state = {o: o.visible_shadow for o in glass}
    hide_state = {o: o.hide_render for o in luminaire_meshes}
    for o in glass:
        o.visible_shadow = False

    # Prefer Metal GPU on macOS when available
    try:
        scene.cycles.device = "GPU"
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dev in prefs.devices:
            dev.use = dev.type == "METAL"
    except Exception:
        scene.cycles.device = "CPU"

    def spawn_fixture_lights(group_cfg: Dict[str, Any]):
        spawned = []
        for idx, fx in enumerate(group_cfg.get("fixtures", [])):
            etype = str(fx.get("emitterType", "spot")).lower()
            if etype == "emissive_mesh":
                continue
            loc = tuple(float(c) for c in fx["position"])
            lumens = float(fx.get("lumens", 400.0))
            kelvin = int(fx.get("kelvin", 2900))
            btype = {"spot": "SPOT", "point": "POINT", "area": "AREA"}.get(etype, "SPOT")
            ldata = bpy.data.lights.new("_BAKE_{}_{}".format(group_cfg["id"], idx), btype)
            ldata.energy = lumens * 0.15
            ldata.color = kelvin_rgb(kelvin)
            if btype == "SPOT":
                ldata.spot_size = math.radians(float(fx.get("spotDegrees", 95.0)))
                ldata.spot_blend = float(fx.get("blend", 0.65))
                ldata.shadow_soft_size = float(fx.get("radius", 0.05))
            elif btype == "AREA":
                ldata.shape = "RECTANGLE"
                ldata.size = float(fx.get("sizeX", 1.0))
                ldata.size_y = float(fx.get("sizeY", 0.05))
            else:
                ldata.shadow_soft_size = float(fx.get("radius", 0.04))
            lobj = bpy.data.objects.new(ldata.name, ldata)
            scene.collection.objects.link(lobj)
            lobj.location = loc
            rot = fx.get("rotationEuler", [0.0, 0.0, 0.0])
            lobj.rotation_euler = tuple(float(r) for r in rot)
            spawned.append(lobj)
        return spawned

    wanted_filter = set(args.groups.split(",")) if args.groups else None
    group_cfgs = [
        g for g in config.get("lightGroups", [])
        if g.get("bakedLayer", True) and (wanted_filter is None or g["id"] in wanted_filter)
    ]
    layers, timings = {}, {}

    for gcfg in group_cfgs:
        gid = gcfg["id"]
        mesh_emitters = {
            fx["entityName"] for fx in gcfg.get("fixtures", [])
            if fx.get("emitterType") == "emissive_mesh" and fx.get("entityName")
        }
        emitter_mats = {
            m for n in mesh_emitters if bpy.data.objects.get(n)
            for m in bpy.data.objects[n].data.materials
        }
        for mat, val in emissive.items():
            principled(mat).inputs["Emission Strength"].default_value = val if mat in emitter_mats else 0.0
        for o in luminaire_meshes:
            o.hide_render = o.name not in mesh_emitters
        spawned = spawn_fixture_lights(gcfg)
        configure_cycles(include_color=False)
        bpy.ops.object.select_all(action="DESELECT")
        for r in receivers:
            r.select_set(True)
        bpy.context.view_layer.objects.active = receivers[0]
        started = time.monotonic()
        passes = []
        for direct in (True, False):
            scene.render.bake.use_pass_direct = direct
            scene.render.bake.use_pass_indirect = not direct
            scene.render.bake.use_clear = True
            scene.cycles.samples = args.direct_samples if direct else args.indirect_samples
            bpy.ops.object.bake(type="DIFFUSE", uv_layer=INDIRECT_UV)
            if not direct:
                low_pass_image(image)
            px = np.empty(len(image.pixels), np.float32)
            image.pixels.foreach_get(px)
            passes.append(np.nan_to_num(px.reshape(-1, 4)[:, :3], nan=0.0, posinf=0.0, neginf=0.0).copy())
        layers[gid] = np.maximum(passes[0] + passes[1], 0.0)
        timings[gid] = round(time.monotonic() - started, 1)
        for lo in spawned:
            bpy.data.objects.remove(lo, do_unlink=True)
        print("LAYER_BAKED", gid, timings[gid], "maxLinear=", round(float(layers[gid].max()), 4), flush=True)

    # 24-sample radiance composite fallback for USD Quick Look & legacy fallback
    radiance_preview = None
    if not args.keep_blend_atlas:
        all_spawned = []
        all_mesh_emitters = set()
        for gcfg in group_cfgs:
            all_spawned.extend(spawn_fixture_lights(gcfg))
            for fx in gcfg.get("fixtures", []):
                if fx.get("emitterType") == "emissive_mesh" and fx.get("entityName"):
                    all_mesh_emitters.add(fx["entityName"])
        for mat, val in emissive.items():
            principled(mat).inputs["Emission Strength"].default_value = val
        for o in luminaire_meshes:
            o.hide_render = o.name not in all_mesh_emitters
        configure_cycles(include_color=True)
        bpy.ops.object.select_all(action="DESELECT")
        for r in receivers:
            r.select_set(True)
        bpy.context.view_layer.objects.active = receivers[0]
        scene.render.bake.use_pass_direct = True
        scene.render.bake.use_pass_indirect = True
        scene.render.bake.use_clear = True
        scene.cycles.samples = 24
        bpy.ops.object.bake(type="DIFFUSE", uv_layer=INDIRECT_UV)
        px = np.empty(len(image.pixels), np.float32)
        image.pixels.foreach_get(px)
        radiance_preview = np.nan_to_num(px.reshape(-1, 4)[:, :3], nan=0.0, posinf=0.0, neginf=0.0).copy()
        for lo in all_spawned:
            bpy.data.objects.remove(lo, do_unlink=True)

    # Restore scene state
    for mat, val in emissive.items():
        principled(mat).inputs["Emission Strength"].default_value = val
    for o, st in hide_state.items():
        o.hide_render = st
    for o, st in shadow_state.items():
        o.visible_shadow = st
    for k_c, v_c in cycles_state.items():
        setattr(scene.cycles, k_c, v_c)
    for node, strength in world_state or []:
        node.inputs["Strength"].default_value = strength

    composite = sum(layers.values())
    finite = (composite * layer_scale)[np.isfinite(composite * layer_scale)]
    peak = float(finite.max()) if finite.size else 0.0
    p99999 = float(np.percentile(finite, 99.999)) if finite.size else 0.0
    irradiance_scale = compute_irradiance_scale(peak, p99999)

    def encode(target, rgb, path: Path, divisor: float = 1.0):
        rgba = np.concatenate(
            [np.clip(rgb * layer_scale / divisor, 0.0, 1.0), np.ones((rgb.shape[0], 1), np.float32)], 1
        )
        target.pixels.foreach_set(rgba.ravel())
        target.update()
        save_indirect_image(target, path)

    (output / "LightLayers").mkdir(exist_ok=True)
    if not args.keep_blend_atlas:
        (output / "Baked").mkdir(exist_ok=True)

    audit = {
        "mode": "irradiance",
        "resolution": [args.width, args.height],
        "samples": {"direct": args.direct_samples, "indirect": args.indirect_samples},
        "scale": layer_scale,
        "irradianceScale": irradiance_scale,
        "compositeMaxLinear": round(peak, 4),
        "timingsSeconds": timings,
        "receivers": len(receivers),
        "blocks": blocks,
        "layers": {},
    }
    for gid, rgb in layers.items():
        layer_img = create_indirect_image("light-" + gid, args.width, args.height)
        encode(layer_img, rgb, output / "LightLayers" / "light-{}.png".format(gid), divisor=irradiance_scale)
        bpy.data.images.remove(layer_img)
        scaled_norm = np.clip(rgb * layer_scale / irradiance_scale, 0.0, 1.0)
        encoded = scaled_norm ** (1.0 / 2.2)
        lum = encoded @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        lit = lum[lum > 0.004]
        audit["layers"][gid] = {
            "litPercent": round(100.0 * len(lit) / len(lum), 2),
            "maxLinear": round(float((rgb * layer_scale).max()), 4),
            "p50": round(float(np.percentile(lit, 50)), 4) if len(lit) else 0.0,
            "p90": round(float(np.percentile(lit, 90)), 4) if len(lit) else 0.0,
            "p99": round(float(np.percentile(lit, 99)), 4) if len(lit) else 0.0,
            "clippedPercent": round(100.0 * float((rgb * layer_scale / irradiance_scale >= 1.0).any(1).mean()), 6),
        }

    if not args.keep_blend_atlas:
        encode(image, radiance_preview if radiance_preview is not None else composite, output / "Baked" / "{}.png".format(atlas_name), divisor=1.0)
        for r in receivers:
            for mat in r.data.materials:
                shader = principled(mat)
                texture = mat.node_tree.nodes["Locus_BakedIndirect_Texture"]
                mat.node_tree.links.new(texture.outputs["Color"], shader.inputs["Emission Color"])
                shader.inputs["Emission Strength"].default_value = 1.0
            base = r.data.uv_layers[original_uvs[r.name]]
            old = base.name
            base.name = "st"
            base.active_render = True
            for mat in r.data.materials:
                if not mat or not mat.use_nodes:
                    continue
                for node in mat.node_tree.nodes:
                    if node.type == "UVMAP" and node.uv_map == old and node.name != "Locus_BakedIndirect_UV":
                        node.uv_map = "st"
        bpy.ops.wm.save_as_mainfile(filepath=str(output / blend_name))

    (output / "bake-audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print("BAKE_IRRADIANCE_DONE", json.dumps({"irradianceScale": irradiance_scale, "layers": list(layers.keys())}), flush=True)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    config = json.loads(args.config.expanduser().resolve().read_text(encoding="utf-8"))
    validation = validate_bake_config(config, args.width, args.height)
    if not validation["passed"]:
        print("BAKE_CONFIG_FAIL", json.dumps(validation, sort_keys=True), file=sys.stderr)
        return 1
    if args.validate_config_only:
        print("BAKE_CONFIG_PASS", json.dumps(validation, sort_keys=True))
        return 0
    return _run_blender_bake(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
