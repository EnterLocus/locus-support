#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standalone night-lighting photometry and light-grouping audit for Locus Rooms.

Operates on any packaged Room `.locusplace`, flat `.zip`, or workspace directory
containing `space.json` (or `room-manifest.json`) and baked light-layer PNGs.
Uses only Python 3.9+ stdlib (with optional Pillow/NumPy acceleration).

Usage:
  python3 .agents/skills/build-original-locus-room/scripts/audit_lighting_photometry.py \\
      /abs/path/to/MyRoom.locusplace [--allow-radiance] [--json-out report.json]
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import struct
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
import zipfile
import zlib

PRIMARY_OVERHEAD_ROLES = frozenset(("overheads", "chandelier"))
SMALL_MOOD_ROLES = frozenset(("accent", "task", "cove"))

OVERHEAD_NAME_HINTS = (
    "can", "downlight", "ceiling", "overhead", "recessed",
    "chandelier", "pendant", "main", "general", "hall", "gallery",
)
SMALL_MOOD_NAME_HINTS = (
    "desk", "floor", "table", "reading", "niche", "shelf",
    "cove", "strip", "led", "sconce", "lantern", "accent",
    "bedside", "step", "stair", "bar", "under",
)
OUTDOOR_NAME_HINTS = (
    "terrace", "garden", "pool", "patio", "exterior",
    "outdoor", "courtyard", "pathway", "bollard", "tree",
)
COLORED_NAME_HINTS = ("pool", "cyan", "underwater", "aqua", "blue", "neon")


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


def infer_group_role(group: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Infer semantic lighting role(s) from explicit role or id/displayName/entities."""
    explicit = group.get("role")
    if explicit:
        return str(explicit), [str(explicit)]

    group_blob = " ".join([
        str(group.get("id", "")),
        str(group.get("displayName", "")),
    ]).lower()
    entity_blob = " ".join(str(e) for e in group.get("entities", [])).lower()
    full_blob = group_blob + " " + entity_blob

    roles_hit: List[str] = []
    has_overhead = any(k in full_blob for k in (
        "downlight", "can_light", "can-light", "canlight", "ceiling", "overhead", "recessed", "chandelier",
    ))
    has_small = any(k in full_blob for k in (
        "floor_lamp", "floor-lamp", "desk_lamp", "desk-lamp", "niche",
        "shelf_glow", "shelf-glow", "cove", "strip", "led", "reading",
        "table_lamp", "table-lamp", "bedside",
    ))
    has_outdoor = any(k in group_blob for k in OUTDOOR_NAME_HINTS)

    if has_overhead:
        roles_hit.append("overheads")
    if has_small:
        roles_hit.append("accent")
    if has_outdoor and not roles_hit:
        roles_hit.append("outdoor")

    if not roles_hit:
        if any(k in group_blob for k in OVERHEAD_NAME_HINTS):
            roles_hit.append("overheads")
        elif any(k in group_blob for k in SMALL_MOOD_NAME_HINTS):
            roles_hit.append("accent")
        else:
            roles_hit.append("unknown")

    return roles_hit[0], roles_hit


def read_png_info_and_rgb(
    raw_bytes: bytes,
    downsample_target: int = 256,
) -> Tuple[int, int, int, List[Tuple[float, float, float]]]:
    """Decode PNG header and downsampled normalized [0, 1] RGB pixels."""
    if raw_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a valid PNG file")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", raw_bytes[16:26])

    try:
        from PIL import Image  # type: ignore
        import numpy as np  # type: ignore

        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        step = max(1, max(width, height) // downsample_target)
        if step > 1:
            img = img.resize((max(1, width // step), max(1, height // step)), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        arr = arr[:, :, :3] / 255.0
        flat = arr.reshape(-1, 3)
        return width, height, bit_depth, [(float(r), float(g), float(b)) for r, g, b in flat]
    except Exception:
        pass

    pos = 8
    idat = bytearray()
    while pos < len(raw_bytes):
        length = struct.unpack(">I", raw_bytes[pos : pos + 4])[0]
        ctype = raw_bytes[pos + 4 : pos + 8]
        chunk = raw_bytes[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IDAT":
            idat.extend(chunk)
        elif ctype == b"IEND":
            break

    channels_map = {0: 1, 2: 3, 4: 2, 6: 4}
    channels = channels_map.get(color_type)
    if channels is None or bit_depth not in (8, 16):
        return width, height, bit_depth, []

    raw = zlib.decompress(bytes(idat))
    bytes_per_sample = bit_depth // 8
    bpp = channels * bytes_per_sample
    stride = width * bpp
    prev_row = bytearray(stride)
    step = max(1, max(width, height) // downsample_target)
    max_val = 65535.0 if bit_depth == 16 else 255.0
    pixels: List[Tuple[float, float, float]] = []

    offset = 0
    for y in range(height):
        ftype = raw[offset]
        offset += 1
        row = bytearray(raw[offset : offset + stride])
        offset += stride
        if ftype == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((a + prev_row[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                row[i] = (row[i] + pr) & 0xFF
        prev_row = row

        if y % step != 0:
            continue
        for x in range(0, width, step):
            base = x * bpp
            if bit_depth == 16:
                vals = [struct.unpack(">H", row[base + c * 2 : base + c * 2 + 2])[0] / max_val for c in range(channels)]
            else:
                vals = [row[base + c] / max_val for c in range(channels)]
            if channels in (1, 2):
                pixels.append((vals[0], vals[0], vals[0]))
            else:
                pixels.append((vals[0], vals[1], vals[2]))
    return width, height, bit_depth, pixels


def _srgb_to_linear(v: float) -> float:
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(v: float) -> float:
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        return 12.92 * v
    return 1.055 * (v ** (1.0 / 2.4)) - 0.055


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((pct / 100.0) * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def _load_room_bundle(target: Path) -> Tuple[Dict[str, Any], Dict[str, bytes], Optional[Dict[str, Any]]]:
    target = target.expanduser().resolve()
    manifest: Optional[Dict[str, Any]] = None
    pngs: Dict[str, bytes] = {}
    bake_audit: Optional[Dict[str, Any]] = None

    if target.is_file() and zipfile.is_zipfile(str(target)):
        with zipfile.ZipFile(str(target)) as zf:
            names = zf.namelist()
            for candidate in ("space.json", "room-manifest.json", "manifest.json"):
                matches = [n for n in names if n == candidate or n.endswith("/" + candidate)]
                if matches:
                    manifest = json.loads(zf.read(matches[0]).decode("utf-8"))
                    break
            for n in names:
                low = n.lower()
                if low.endswith(".png"):
                    pngs[n] = zf.read(n)
                elif low.endswith("bake-audit.json"):
                    bake_audit = json.loads(zf.read(n).decode("utf-8"))
    elif target.is_dir():
        for candidate in ("space.json", "room-manifest.json", "manifest.json", "room/space.json"):
            p = target / candidate
            if p.is_file():
                manifest = json.loads(p.read_text(encoding="utf-8"))
                break
        if manifest is None:
            for p in sorted(target.glob("catalog/spaces/*/space.json")):
                manifest = json.loads(p.read_text(encoding="utf-8"))
                break
        if manifest is None:
            rz = target / "room.zip"
            if rz.is_file():
                manifest, pngs, bake_audit = _load_room_bundle(rz)
        if not pngs:
            for p in target.rglob("*.png"):
                rel = str(p.relative_to(target))
                if "light" in rel.lower() or "baked" in rel.lower() or "irradiance" in rel.lower():
                    pngs[rel] = p.read_bytes()
        ba = target / "bake-audit.json"
        if ba.is_file():
            bake_audit = json.loads(ba.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError("Target not found: {}".format(target))

    if manifest is None:
        raise ValueError("No space.json or room-manifest.json found in {}".format(target))
    return manifest, pngs, bake_audit


def audit_lighting_photometry(
    target: Path,
    require_irradiance: bool = True,
    downsample_target: int = 192,
) -> Dict[str, Any]:
    """Audit baked irradiance layers, proxy hygiene, and semantic mood grouping."""
    manifest, pngs, bake_audit = _load_room_bundle(target)
    findings: List[Dict[str, Any]] = []
    lighting = manifest.get("lighting")
    if not isinstance(lighting, dict):
        findings.append(_finding("LIGHTING_MISSING", "Blocker", "Room manifest declares no lighting block"))
        return {"passed": False, "target": str(target), "findings": findings, "layers": {}}

    groups = lighting.get("luminaireGroups") or []
    baked = lighting.get("bakedIndirect") or {}

    shadow_proxies = 0
    seat_gated_proxies = 0
    total_proxies = 0
    for g in groups:
        gid = g.get("id", "<group>")
        proxies = g.get("proxies")
        if proxies is None:
            proxies = [g["proxy"]] if g.get("proxy") else []
        for p in proxies:
            total_proxies += 1
            if p.get("castsShadow", False):
                shadow_proxies += 1
                findings.append(_finding(
                    "LIGHTING_SHADOW_PROXY", "Blocker",
                    "Group {} declares a castsShadow=true real-time proxy; bake sharp shadows into light layers instead".format(gid),
                    subject=gid,
                ))
            if p.get("nearTeleportIDs"):
                seat_gated_proxies += 1
                findings.append(_finding(
                    "LIGHTING_SEAT_GATED_PROXY", "High",
                    "Group {} uses a nearTeleportIDs seat-gated proxy whose light pool disappears from other seats; prefer a baked layer".format(gid),
                    subject=gid,
                ))

    group_roles: Dict[str, str] = {}
    for g in groups:
        gid = g.get("id", "<group>")
        primary_role, all_roles = infer_group_role(g)
        group_roles[gid] = primary_role
        if "overheads" in all_roles and "accent" in all_roles:
            findings.append(_finding(
                "LIGHTING_QUADRANT_MIXED_GROUP", "High",
                "Group {} mixes overhead and small-mood fixtures ({}); split by mood layer so big lights can turn off independently".format(
                    gid, g.get("entities", [])[:6]
                ),
                subject=gid,
            ))
        ent_blob = " ".join(str(e).lower() for e in g.get("entities", []))
        if any(c in ent_blob for c in COLORED_NAME_HINTS) and any(
            w in ent_blob for w in ("can", "downlight", "floor", "desk", "niche", "chandelier")
        ):
            findings.append(_finding(
                "LIGHTING_COLORED_MIXED_IN_WARM_GROUP", "Blocker",
                "Group {} mixes colored accent/pool entities with warm interior luminaires".format(gid),
                subject=gid,
            ))

    mode = baked.get("mode", "radiance")
    irradiance_scale = float(baked.get("irradianceScale", 1.0))
    layer_defs = baked.get("layers") or []
    if require_irradiance and mode != "irradiance":
        findings.append(_finding(
            "LIGHTING_NOT_V14_IRRADIANCE", "High",
            "bakedIndirect.mode is {!r}; prefer 'irradiance' (Locus 1.6.0 / protocol 1.5.2+) so UV0 textures stay sharp when Room Lights turn on".format(mode),
        ))
    if len(groups) >= 2 and not layer_defs and baked.get("image"):
        findings.append(_finding(
            "LIGHTING_SINGLE_SHARED_AMBIENT", "Blocker",
            "Room has {} luminaire groups but only one shared bakedIndirect.image; use per-group bakedIndirect.layers so individual switches visibly darken their surroundings".format(len(groups)),
        ))

    layer_metrics: Dict[str, Dict[str, Any]] = {}
    layer_linear_luma: Dict[str, List[float]] = {}

    for ldef in layer_defs:
        gid = ldef.get("luminaireGroupID") or ldef.get("groupID") or ldef.get("id", "<layer>")
        img_rel = ldef.get("image", "")
        raw = None
        for k, v in pngs.items():
            if k == img_rel or k.endswith("/" + img_rel) or Path(k).name == Path(img_rel).name:
                raw = v
                break
        if raw is None:
            findings.append(_finding(
                "LIGHTING_MISSING_LAYER_PNG", "Blocker",
                "Light layer PNG {!r} for group {} not found".format(img_rel, gid),
                subject=gid,
            ))
            continue

        w, h, bit_depth, rgb = read_png_info_and_rgb(raw, downsample_target=downsample_target)
        if mode == "irradiance" and irradiance_scale > 1.0 and bit_depth < 16:
            findings.append(_finding(
                "LIGHTING_LAYER_NOT_16BIT", "Blocker",
                "Irradiance layer {} uses {}-bit PNG with irradianceScale={}; must be 16-bit RGB/RGBA PNG".format(
                    gid, bit_depth, irradiance_scale
                ),
                subject=gid,
            ))

        if not rgb:
            continue

        lin_luma: List[float] = []
        clipped = 0
        overbright = 0
        max_lin = 0.0
        for r, g_c, b in rgb:
            if max(r, g_c, b) >= 250.0 / 255.0:
                clipped += 1
            lr = _srgb_to_linear(r) * irradiance_scale
            lg = _srgb_to_linear(g_c) * irradiance_scale
            lb = _srgb_to_linear(b) * irradiance_scale
            peak_c = max(lr, lg, lb)
            if peak_c > max_lin:
                max_lin = peak_c
            luma_val = 0.2126 * lr + 0.7152 * lg + 0.0722 * lb
            if luma_val > 2.5:
                overbright += 1
            lin_luma.append(luma_val)

        layer_linear_luma[gid] = lin_luma
        lit = sorted(v for v in lin_luma if v > 0.002)
        lit_pct = 100.0 * len(lit) / float(len(lin_luma))
        clipped_pct = 100.0 * clipped / float(len(lin_luma))
        overbright_pct = (100.0 * overbright / float(len(lit))) if lit else 0.0
        p50 = _percentile(lit, 50.0)
        p90 = _percentile(lit, 90.0)
        p99 = _percentile(lit, 99.0)

        step = max(1, max(w, h) // downsample_target)
        gw = max(1, (w + step - 1) // step)
        gh = len(lin_luma) // gw if gw > 0 else 0
        speckle_spikes = 0
        lit_interior = 0
        if gw >= 3 and gh >= 3 and gw * gh == len(lin_luma):
            for yy in range(1, gh - 1):
                row_off = yy * gw
                for xx in range(1, gw - 1):
                    c = lin_luma[row_off + xx]
                    if c <= 0.01:
                        continue
                    lit_interior += 1
                    nb = (
                        lin_luma[row_off + xx - 1]
                        + lin_luma[row_off + xx + 1]
                        + lin_luma[row_off - gw + xx]
                        + lin_luma[row_off + gw + xx]
                    ) * 0.25
                    if nb > 0.005 and c > nb * 3.5 and (c - nb) > 0.15:
                        speckle_spikes += 1
        speckle_pct = (100.0 * speckle_spikes / float(lit_interior)) if lit_interior > 0 else 0.0

        layer_metrics[gid] = {
            "role": group_roles.get(gid, "unknown"),
            "resolution": [w, h],
            "bitDepth": bit_depth,
            "litPercent": round(lit_pct, 2),
            "clippedPercent": round(clipped_pct, 4),
            "overbrightPercent": round(overbright_pct, 2),
            "maxLinear": round(max_lin, 4),
            "medianLitLinear": round(p50, 4),
            "p90LitLinear": round(p90, 4),
            "p99LitLinear": round(p99, 4),
            "speckleSpikePercent": round(speckle_pct, 4),
        }

        if lit_pct < 0.25:
            findings.append(_finding(
                "LIGHTING_EMPTY_LAYER", "High",
                "Light layer {} illuminates only {:.2f}% of the atlas (empty or disconnected lamp group)".format(gid, lit_pct),
                subject=gid,
            ))
        if clipped_pct > 0.5:
            findings.append(_finding(
                "LIGHTING_CLIPPED_HIGHLIGHTS", "High",
                "Light layer {} clips {:.2f}% of pixels >= 250/255 (> 0.5% ceiling; raise irradianceScale or lower fixture lumens)".format(gid, clipped_pct),
                subject=gid,
            ))
        if mode == "irradiance" and (max_lin > 6.5 or p99 > 3.5 or overbright_pct > 2.0):
            findings.append(_finding(
                "LIGHTING_LAYER_OVEREXPOSED", "High",
                "Irradiance layer {} is overexposed (maxLinear={:.2f} [<=6.5], p99Lit={:.2f} [<=3.5], overbright>2.5={:.2f}% [<=2%]; lower near-surface fixture wattage/lumens or apply soft-knee calibration so wood and plaster do not blow out on device)".format(
                    gid, max_lin, p99, overbright_pct
                ),
                subject=gid,
                details={"maxLinear": round(max_lin, 4), "p99LitLinear": round(p99, 4), "overbrightPercent": round(overbright_pct, 2)},
            ))
        if speckle_pct > 1.5:
            findings.append(_finding(
                "LIGHTING_BOUNCE_SPECKLES", "High",
                "Light layer {} has {:.2f}% isolated high-pass speckle spikes (> 1.5%; increase indirect samples or low-pass the bounce pass)".format(gid, speckle_pct),
                subject=gid,
            ))

    if mode == "irradiance":
        if irradiance_scale > 8.5:
            findings.append(_finding(
                "LIGHTING_EXCESSIVE_IRRADIANCE_SCALE", "High",
                "Shared irradianceScale={:.2f} exceeds 8.5 ceiling; an over-powered near-surface lamp inflates irradianceScale, clips highlights on device, and wastes 16-bit dark-end precision (lower near-lamp power and keep irradianceScale <= 6.0)".format(
                    irradiance_scale
                ),
                details={"irradianceScale": irradiance_scale},
            ))
        elif irradiance_scale > 6.0:
            findings.append(_finding(
                "LIGHTING_HIGH_IRRADIANCE_SCALE", "Medium",
                "Shared irradianceScale={:.2f} exceeds recommended 6.0 target; inspect near-lamp pools for whiteout clipping".format(
                    irradiance_scale
                ),
                details={"irradianceScale": irradiance_scale},
            ))

    mood_summary: Dict[str, Any] = {}
    if len(layer_linear_luma) >= 2:
        n_px = min(len(v) for v in layer_linear_luma.values())
        all_sum = [0.0] * n_px
        small_sum = [0.0] * n_px
        overhead_ids = [gid for gid in layer_linear_luma if group_roles.get(gid) in PRIMARY_OVERHEAD_ROLES]
        small_ids = [gid for gid in layer_linear_luma if group_roles.get(gid) in SMALL_MOOD_ROLES]
        for gid, arr in layer_linear_luma.items():
            for i in range(n_px):
                all_sum[i] += arr[i]
                if gid in small_ids:
                    small_sum[i] += arr[i]

        all_lit = sorted(v for v in all_sum if v > 0.004)
        all_med = _percentile(all_lit, 50.0)
        all_clipped = sum(1 for v in all_sum if _linear_to_srgb(v / max(irradiance_scale, 1.0)) >= 250.0 / 255.0)
        all_clipped_pct = 100.0 * all_clipped / float(n_px) if n_px else 0.0
        mood_summary["allOnMedianLinear"] = round(all_med, 4)
        mood_summary["allOnClippedPercent"] = round(all_clipped_pct, 4)

        if overhead_ids and small_ids and all_med > 1e-4:
            small_on_lit_pixels = sorted(small_sum[i] for i in range(n_px) if all_sum[i] > 0.004)
            small_med = _percentile(small_on_lit_pixels, 50.0)
            drop_frac = 1.0 - (small_med / all_med)
            small_peak = max(small_sum) if small_sum else 0.0
            all_peak = max(all_sum) if all_sum else 1e-6
            mood_summary["overheadGroups"] = overhead_ids
            mood_summary["smallMoodGroups"] = small_ids
            mood_summary["smallOnlyMedianLinear"] = round(small_med, 4)
            mood_summary["overheadsOffMedianDropPercent"] = round(drop_frac * 100.0, 2)
            mood_summary["smallMoodPeakRatio"] = round(small_peak / max(all_peak, 1e-6), 3)

            if drop_frac < 0.65:
                findings.append(_finding(
                    "LIGHTING_OVERHEADS_OFF_NO_MOOD_DELTA", "High",
                    "Turning off overheads ({}) only reduces room-wide median linear luminance by {:.1f}% (< 65% required); small lamps ({}) are washing out the room".format(
                        overhead_ids, drop_frac * 100.0, small_ids
                    ),
                    details=mood_summary,
                ))
            if small_peak < 0.08:
                findings.append(_finding(
                    "LIGHTING_SMALL_MOOD_TOO_DIM", "Medium",
                    "Small mood layers ({}) peak at only {:.3f} linear; turning off overheads leaves the room nearly dark".format(
                        small_ids, small_peak
                    ),
                ))

        total_energy = sum(all_sum)
        if total_energy > 1e-6:
            contributions = {}
            for gid, arr in layer_linear_luma.items():
                share = sum(arr[:n_px]) / total_energy
                contributions[gid] = round(share * 100.0, 2)
                if share < 0.005:
                    findings.append(_finding(
                        "LIGHTING_NEGLIGIBLE_GROUP_CONTRIBUTION", "Medium",
                        "Light group {} contributes only {:.2f}% of total baked light energy; toggling it may look ineffective".format(
                            gid, share * 100.0
                        ),
                        subject=gid,
                    ))
            mood_summary["energySharePercent"] = contributions

    if isinstance(bake_audit, dict):
        for gid, linfo in (bake_audit.get("layers") or {}).items():
            for surf_name, svals in (linfo.get("taskSurfaces") or {}).items():
                p95 = float(svals.get("p95", 0.0))
                if p95 >= 0.99:
                    findings.append(_finding(
                        "LIGHTING_TASK_SURFACE_SATURATED", "Medium",
                        "Task surface {} under group {} hits p95={:.3f} (near saturation)".format(surf_name, gid, p95),
                        subject="{}:{}".format(gid, surf_name),
                    ))

    blockers = [f for f in findings if f["severity"] == "Blocker"]
    highs = [f for f in findings if f["severity"] == "High"]
    return {
        "passed": len(blockers) == 0 and len(highs) == 0,
        "target": str(target),
        "mode": mode,
        "irradianceScale": irradiance_scale,
        "groupCount": len(groups),
        "layerCount": len(layer_defs),
        "totalProxies": total_proxies,
        "shadowProxies": shadow_proxies,
        "seatGatedProxies": seat_gated_proxies,
        "moodSummary": mood_summary,
        "layers": layer_metrics,
        "blockerCount": len(blockers),
        "highCount": len(highs),
        "findingCount": len(findings),
        "findings": findings,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Room .locusplace, .zip, or workspace directory")
    parser.add_argument("--allow-radiance", action="store_true", help="Do not fail on legacy mode='radiance'")
    parser.add_argument("--downsample", type=int, default=192)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = audit_lighting_photometry(
        args.target,
        require_irradiance=not args.allow_radiance,
        downsample_target=args.downsample,
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    tag = "LIGHTING_PHOTOMETRY_PASS" if report["passed"] else "LIGHTING_PHOTOMETRY_FAIL"
    print(tag, json.dumps(report, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
