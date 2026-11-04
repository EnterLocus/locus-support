# Prevent flicker while authoring

Do this before delivery, without waiting for the creator to report flicker.
A still render and an import-validator pass cannot establish temporal stability.

## Build surfaces that do not compete

- Give each visible surface one owner. Remove duplicate faces, coincident
  opposite-facing disks, duplicate imported objects, and overlapping copies
  inside one mesh. Recalculating normals does not remove duplicate geometry.
- Model lampshade openings as open rings with real thickness. A decorative
  rim needs an annulus, not a filled disk across the aperture. Inspect inside,
  outside, and underside. Close a solid only where that closure is intended.
- Integrate trim and panels into the supporting surface, or give intentionally
  separate parts a justified physical separation. Avoid a second wall/floor
  skin on the same plane. Do not apply a tiny arbitrary offset as a universal
  fix: the useful separation depends on scale, distance, and the renderer.
- Give glazing a deliberate construction. Remove unintended duplicate glass
  panes and stacked transparent shells; inspect overlapping transparent props.
- Avoid subpixel geometry and dense high-contrast patterns at the intended
  viewing distance. Review mipmaps, normal-map strength, roughness, and bright
  specular highlights when the shimmer follows detail rather than a surface.

## Run the public surface-risk audit

From this repository, with Blender installed, audit the editable source:

```sh
blender --factory-startup -b /absolute/path/to/Room.blend --disable-autoexec \
  --python-exit-code 2 --python tools/audit_coplanar_surfaces.py -- \
  --json /absolute/path/to/source-surfaces.json
```

Then audit the exact exported USDZ, before packaging:

```sh
blender --factory-startup -b --disable-autoexec \
  --python-exit-code 2 --python tools/audit_coplanar_surfaces.py -- \
  --usdz /absolute/path/to/scene.usdz \
  --json /absolute/path/to/export-surfaces.json
```

On macOS, `blender` can be replaced by
`/Applications/Blender.app/Contents/MacOS/Blender`. This uses Blender's Python
API, with no MCP, Locus source, simulator, or paid service required. The script
reads evaluated render meshes in world metres and does not save changes.
If you downloaded only this skill, replace `tools/audit_coplanar_surfaces.py`
with the bundled [script](../scripts/audit_coplanar_surfaces.py) path.

The JSON report is authoritative: `exitCode` 0 means no findings in a complete
requested scope, 1 means findings needing review, and 2 means an error or
incomplete scan. Check `scopeComplete`, `skippedMeshes`, `pairLimitReached`,
and `omittedFindingCount`; never call an incomplete scan clean. Defaults flag
near-parallel overlap within 2 mm, over 1 cm² per triangle pair, at a 0.1° normal tolerance. Tessellated
small overlaps below that per-pair area threshold can be missed.
These are diagnostic thresholds, not renderer limits or a prescribed gap.
The reported area sums triangle-pair overlap; it is not unique visible area.
Hidden joins and intentional layers may be reported and need human review.

For large rooms, inspect the complete report and divide the scene into
bounded scopes using `--root <object>` (including descendants), or repeat
`--object <mesh>` to compare suspect parts together. Raise
`--max-mesh-triangles`, `--max-triangles`, or `--max-pairs` deliberately if
needed. Unrealized object/collection instances are reported as incomplete;
realize them in a disposable review copy and scan their placed geometry.
Include interfaces between scopes: checking each object separately
cannot detect competition between them. Record scopes, settings, skipped
objects, source hash, findings, and dispositions. Do not suppress a finding
merely to get a successful exit code.

## Check motion and classify remaining problems

Render a short slow camera move from representative seats, including slight
sideways and forward/back motion. Inspect lamps, thin trim, glazing, wall
panels, floor seams, and distant detail. Compare the delivered USDZ with the
source; export can reintroduce duplicate geometry or change transparency.
Blender motion review is useful authoring evidence, not RealityKit acceptance.

On Vision Pro, repeat slow head motion near and far, daylight and low light,
and each relevant lamp group on/off and dimmed. Distinguish:

| Symptom | Investigate first |
| --- | --- |
| Two surfaces alternate or patch as the head moves | Duplicate or near-coplanar faces, including opposite winding |
| Transparent layers swap order | Stacked glazing and alpha sorting |
| Fine lines or highlights sparkle | Subpixel detail, textures, normals, roughness and specular aliasing |
| Illumination pulses while stationary | Authored animation, competing lights, baked-layer/proxy setup or runtime behavior |

Repair the actual cause in the editable source and repeat affected checks on
its new export. Do not globally disable culling, shadows, or materials to hide
it, or treat extra samples as a fix for intersecting geometry. The audit does
not simulate visibility, transparency sorting, aliasing, lighting animation,
or device rendering. Report unavailable motion/device checks as **not
verified**, even when no geometric risks were found.
