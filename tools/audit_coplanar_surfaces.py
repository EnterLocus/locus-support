#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Find overlapping near-coplanar surface risks in a Blender source or USDZ.

Run with Blender's --python option. Findings are authoring diagnostics, not a
prediction or proof of device flicker. No geometry or material is modified.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def clip(poly, distance):
    """Clip a convex polygon to distance(point) >= 0."""
    if not poly:
        return []
    out = []
    previous = poly[-1]
    dp = distance(previous)
    for point in poly:
        d = distance(point)
        if (d >= 0) != (dp >= 0):
            t = dp / (dp - d)
            out.append(tuple(a + t * (b - a) for a, b in zip(previous, point)))
        if d >= 0:
            out.append(point)
        previous, dp = point, d
    return out


def signed_area(poly):
    return sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(poly, poly[1:]+poly[:1])) / 2 if poly else 0


def overlap_area(a, b, distance):
    """Shared area inside the plane-distance slab; handles opposite winding."""
    axis = max(range(3), key=lambda k: abs(a['normal'][k]))
    axes = [k for k in range(3) if k != axis]
    project = lambda p: tuple(p[k] for k in axes)
    poly = [project(p) for p in a['vertices']]
    other = [project(p) for p in b['vertices']]
    if signed_area(other) < 0:
        other.reverse()
    for p, q in zip(other, other[1:]+other[:1]):
        poly = clip(poly, lambda v: (q[0]-p[0])*(v[1]-p[1])-(q[1]-p[1])*(v[0]-p[0]))
    if not poly:
        return 0.0
    def plane_b(v):
        p = [0.0, 0.0, 0.0]
        for k, value in zip(axes, v):
            p[k] = value
        p[axis] = (a['plane'] - sum(a['normal'][k]*p[k] for k in axes)) / a['normal'][axis]
        return dot(b['normal'], sub(p, b['vertices'][0]))
    poly = clip(poly, lambda v: distance - plane_b(v))
    poly = clip(poly, lambda v: distance + plane_b(v))
    return abs(signed_area(poly)) / abs(a['normal'][axis])


def audit_triangles(triangles, *, distance=0.002, min_area=0.0001,
                    angle_degrees=0.1, cell_size=0.5, max_pairs=1000000,
                    max_findings=100, skipped=None):
    """Public geometry boundary: world-metre triangles with object/face IDs."""
    if not all(math.isfinite(x) and x > 0 for x in [distance, min_area, angle_degrees, cell_size]):
        raise ValueError('Distances, minimum area and angle must be finite and positive')
    if angle_degrees > 1 or min(max_pairs, max_findings) < 1:
        raise ValueError('Angle must be at most 1 degree; limits must be positive')
    width = 2 * math.sin(math.radians(angle_degrees))
    cosine = math.cos(math.radians(angle_degrees))
    buckets = {}
    records = []
    degenerate = 0
    for item in triangles:
        v = item['vertices']
        if len(v) != 3 or any(len(p) != 3 or not all(math.isfinite(c) for c in p) for p in v):
            raise ValueError('Triangle vertices must be finite XYZ coordinates in metres')
        raw = cross(sub(v[1], v[0]), sub(v[2], v[0]))
        length = math.sqrt(dot(raw, raw))
        if length < 1e-14:
            degenerate += 1
            continue
        n = tuple(x/length for x in raw)
        low = tuple(min(p[k] for p in v) for k in range(3))
        high = tuple(max(p[k] for p in v) for k in range(3))
        ranges = [range(math.floor((low[k]-distance)/cell_size), math.floor((high[k]+distance)/cell_size)+1) for k in range(3)]
        cells = list(itertools.product(*ranges)) if math.prod(len(x) for x in ranges) <= 64 else None
        record = dict(item, normal=n, plane=dot(n, v[0]), low=low, high=high, cells=cells)
        index = len(records)
        records.append(record)
        key = tuple(math.floor(x/width) for x in n)
        bucket = buckets.setdefault(key, {'members': [], 'large': [], 'grid': defaultdict(list)})
        bucket['members'].append(index)
        if cells is None:
            bucket['large'].append(index)
        else:
            for cell in cells:
                bucket['grid'][cell].append(index)
    findings = {}
    checked = 0
    exhausted = False
    for i, a in enumerate(records):
        candidates = set()
        for sign in [1, -1]:
            key = tuple(math.floor(sign*x/width) for x in a['normal'])
            for offset in itertools.product([-1, 0, 1], repeat=3):
                bucket = buckets.get(tuple(x+y for x, y in zip(key, offset)))
                if bucket is None:
                    continue
                if a['cells'] is None:
                    candidates.update(bucket['members'])
                else:
                    candidates.update(bucket['large'])
                    for cell in a['cells']:
                        candidates.update(bucket['grid'].get(cell, []))
        for j in sorted(candidates):
            if j <= i:
                continue
            b = records[j]
            if (a['object'], a['face']) == (b['object'], b['face']):
                continue  # Triangulation of one polygon is not duplicate geometry.
            if any(a['low'][k] > b['high'][k]+distance or b['low'][k] > a['high'][k]+distance for k in range(3)):
                continue
            if abs(dot(a['normal'], b['normal'])) < cosine:
                continue
            checked += 1
            if checked > max_pairs:
                exhausted = True
                break
            ds = [dot(a['normal'], sub(v, a['vertices'][0])) for v in b['vertices']]
            if min(ds) > distance or max(ds) < -distance:
                continue
            area = overlap_area(a, b, distance)
            if area < min_area:
                continue
            key = tuple(sorted([a['object'], b['object']]))
            row = findings.setdefault(key, {'objects': list(key), 'overlapAreaM2': 0.0,
                                            'trianglePairs': 0, 'largestOverlapM2': 0.0})
            row['overlapAreaM2'] += area
            row['trianglePairs'] += 1
            if area > row['largestOverlapM2']:
                row.update(largestOverlapM2=area, faces=[a['face'], b['face']],
                           winding='opposite' if dot(a['normal'], b['normal']) < 0 else 'same',
                           exampleCenterMeters=[sum(v[k] for v in a['vertices'])/3 for k in range(3)])
        if exhausted:
            break
    rows = sorted(findings.values(), key=lambda row: (-row['overlapAreaM2'], row['objects']))
    skipped = list(skipped or [])
    complete = not skipped and not exhausted
    return {'scopeComplete': complete, 'findingCount': len(rows), 'findings': rows[:max_findings],
            'omittedFindingCount': max(0, len(rows)-max_findings), 'scannedTriangles': len(records),
            'degenerateTriangles': degenerate, 'checkedPairs': min(checked, max_pairs),
            'pairLimitReached': exhausted, 'skippedMeshes': skipped,
            'parameters': {'distanceMeters': distance, 'minimumOverlapAreaM2': min_area,
                           'normalToleranceDegrees': angle_degrees},
            'limits': 'Surface-risk diagnostics only. Hidden joins and intentional layers need review. '
                      'No visibility, alpha sorting, temporal aliasing, lighting animation or device-flicker proof.'}


def blender_triangles(args):
    import bpy
    if args.usdz:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.wm.usd_import(filepath=str(args.usdz.resolve()))
    source = args.usdz or Path(bpy.data.filepath)
    if not str(source) or not source.is_file():
        raise ValueError('Load a .blend or provide --usdz with the exact exported model')
    if args.root:
        root = bpy.data.objects.get(args.root)
        if root is None:
            raise ValueError('Root object does not exist: ' + args.root)
        objects = [root, *root.children_recursive]
    elif args.object:
        missing = [name for name in args.object if name not in bpy.data.objects]
        if missing:
            raise ValueError('Objects do not exist: ' + ', '.join(missing))
        objects = [bpy.data.objects[name] for name in args.object]
    else:
        objects = list(bpy.context.scene.objects)
    graph = bpy.context.evaluated_depsgraph_get()
    triangles, skipped = [], []
    scope_names = {obj.name for obj in objects}
    # Object/collection and Geometry Nodes instances need their own evaluated
    # placement. Do not silently claim that scanning the prototype covered them.
    instances = defaultdict(int)
    for instance in graph.object_instances:
        if instance.is_instance and instance.parent and instance.parent.name in scope_names:
            instances[instance.parent.name] += 1
    skipped.extend({'object': name, 'instances': count, 'reason': 'unrealized instances; realize a review copy'}
                   for name, count in sorted(instances.items()))
    for obj in sorted(objects, key=lambda x: x.name):
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            count = len(mesh.loop_triangles)
            if count > args.max_mesh_triangles or len(triangles)+count > args.max_triangles:
                skipped.append({'object': obj.name, 'triangles': count, 'reason': 'triangle limit'})
                continue
            matrix = evaluated.matrix_world
            points = [tuple(matrix @ vertex.co) for vertex in mesh.vertices]
            # Blender's scene scale is the source metre conversion; USD import
            # already converts stage units into the importing scene's units.
            scale = bpy.context.scene.unit_settings.scale_length
            for tri in mesh.loop_triangles:
                triangles.append({'object': obj.name, 'face': tri.polygon_index,
                                  'vertices': [tuple(c*scale for c in points[i]) for i in tri.vertices]})
        finally:
            evaluated.to_mesh_clear()
    if not triangles:
        raise ValueError('No triangles were scanned in the requested scope')
    return source, triangles, skipped


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usdz', type=Path, help='Import and audit an exact exported USDZ in a fresh scene')
    scope = p.add_mutually_exclusive_group()
    scope.add_argument('--root', help='Audit this Blender object and all descendants')
    scope.add_argument('--object', action='append', help='Audit these exact mesh objects (repeatable)')
    p.add_argument('--json', type=Path, required=True)
    p.add_argument('--distance', type=float, default=0.002)
    p.add_argument('--min-area', type=float, default=0.0001)
    p.add_argument('--max-mesh-triangles', type=int, default=20000)
    p.add_argument('--max-triangles', type=int, default=250000)
    p.add_argument('--max-pairs', type=int, default=1000000)
    p.add_argument('--max-findings', type=int, default=100)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    try:
        if min(args.max_mesh_triangles, args.max_triangles) < 1:
            raise ValueError('Triangle limits must be positive')
        source, triangles, skipped = blender_triangles(args)
        report = audit_triangles(triangles, distance=args.distance, min_area=args.min_area,
                                 max_pairs=args.max_pairs, max_findings=args.max_findings, skipped=skipped)
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk)
        report.update(source=str(source.resolve()), sha256=digest.hexdigest(),
                      scope={'root': args.root, 'objects': args.object},
                      exitCode=2 if not report['scopeComplete'] else 1 if report['findingCount'] else 0)
    except Exception as error:
        report = {'scopeComplete': False, 'error': str(error), 'exitCode': 2}
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2)+'\n')
    print('COPLANAR_SURFACE_REPORT', json.dumps({k:v for k,v in report.items() if k not in ['findings','skippedMeshes']}), flush=True)
    raise SystemExit(report['exitCode'])


if __name__ == '__main__':
    main()
