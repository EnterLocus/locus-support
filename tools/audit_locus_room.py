#!/usr/bin/env python3
"""Verify explicit rendering bindings against the delivered self-contained USDZ."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from pxr import Usd, UsdGeom, UsdShade


def audit(metadata_path: Path, usdz_path: Path) -> dict:
    metadata = json.loads(metadata_path.read_text())
    stage = Usd.Stage.Open(str(usdz_path))
    if stage is None:
        raise ValueError('Cannot open delivered USDZ')
    by_name = {}
    for prim in stage.Traverse():
        by_name.setdefault(prim.GetName(), []).append(prim)
    def resolve(name):
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError(f'{name}: expected one exported identity, found {len(matches)}')
        return matches[0]
    report = {'asset': metadata.get('id', metadata.get('displayName')), 'bindings': {}, 'directedSpots': 0}
    supported_nodes = {'UsdPreviewSurface', 'UsdUVTexture', 'UsdTransform2d',
                       'UsdPrimvarReader_float2', 'UsdPrimvarReader_float3',
                       'UsdPrimvarReader_float', 'UsdPrimvarReader_int'}
    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue
        shader = UsdShade.Shader(prim)
        identifier = shader.GetIdAttr().Get()
        if identifier not in supported_nodes:
            raise ValueError(f'{prim.GetPath()}: unsupported shader {identifier}; bake it to a Preview Surface texture network')
        for value in shader.GetInputs():
            if value.GetAttr().GetTimeSamples():
                raise ValueError(f'{value.GetAttr().GetPath()}: material animation is outside this author contract; validate it separately in the target renderer')
        if identifier == 'UsdPreviewSurface':
            displacement = shader.GetInput('displacement')
            if displacement and (displacement.HasConnectedSource() or displacement.Get() not in (0, None)):
                raise ValueError(f'{prim.GetPath()}: bake displacement into mesh geometry before delivery')
    adaptation = metadata.get('spatialAdaptation', {})
    for name in [*adaptation.get('wallEntities', []), *adaptation.get('roofEntities', []),
                 *adaptation.get('deskEntitiesByTeleportID', {}).values()]:
        resolve(name)
    for animation in metadata.get('ambientAnimations', []):
        resolve(animation['entityName'])

    rendering = metadata.get('rendering', {})
    for field, names in rendering.items():
        paths = [resolve(name).GetPath() for name in names]
        if len(set(paths)) != len(paths):
            raise ValueError(f'{field}: duplicate bindings')
        for path in paths:
            if any(path != other and path.HasPrefix(other) for other in paths):
                raise ValueError(f'{field}: overlapping subtrees at {path}')
            if not any(p.IsA(UsdGeom.Mesh) for p in Usd.PrimRange(stage.GetPrimAtPath(path))):
                raise ValueError(f'{field}: {path} has no renderable geometry')
        report['bindings'][field] = len(paths)
    for group in metadata.get('lighting', {}).get('luminaireGroups', []):
        for name in group['entities']:
            resolve(name)
        for proxy in group.get('proxies', [group['proxy']] if 'proxy' in group else []):
            resolve(proxy['anchorEntity'])
            if proxy['type'] == 'spot':
                d = proxy.get('direction')
                if not isinstance(d, list) or len(d) != 3 or not all(type(v) in (int,float) and math.isfinite(v) for v in d):
                    raise ValueError('New authored spot requires an explicit direction')
                if abs(sum(v*v for v in d)-1) >= 0.001:
                    raise ValueError('Spot direction must be a unit vector')
                report['directedSpots'] += 1
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata', type=Path)
    parser.add_argument('usdz', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.metadata, args.usdz), indent=2))
