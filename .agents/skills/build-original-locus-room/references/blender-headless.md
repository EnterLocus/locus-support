# Build with Blender Python in background mode

Use this route when a coding agent creates a Room from the selected concept
image and metric layout without an explicitly chosen authoring tool. It
requires an installed Blender executable, permission to run local scripts, and
an image-capable tool to inspect saved renders. If Blender fails to start or
hangs inside a restrictive agent sandbox, run the same command outside it. It
does not require an open
Blender window, an MCP server, or a person operating the viewport. Preserve a
creator's explicit choice of another tool.

## Prepare reproducible inputs

Keep the concept image, metric plan, brief, builder scripts, render settings,
and asset inventory with the project. Locate Blender and record its version.
Use explicit source and output paths and fixed random seeds where procedural
variation is involved. Preserve the original Room when revising it and write a
separate output version.

Python can model architecture and assemble external furniture, plants, PBR
materials, and lighting environments. Download chosen assets before building,
retain their local files, and record source URLs, licenses, required credits,
and hashes. Check that their terms permit redistribution inside the Room USDZ.
Do not limit a headless build to primitive furniture or flat colors, and do not
assume an asset library or paid generation service is required.

## Decide what to code, source, or generate

Separate the Room by **parametric, constraint-bound structure and scene
orchestration vs. standalone freeform props**, rather than asking a 3D generator
for a whole Room or drawing a crude boundary by material softness:

- **Code in Blender Python** (spatial skeleton, constraint-bound geometry, and
  scene assembly): low-entropy, metric-exact, planar, transparent, emissive, or
  contract-bound parts—walls, floor slabs, roofs, reveals, stairs ($2R + G$,
  connected landings, real slab openings), guardrails, mullions, single-sheet
  transmissive glazing, rectilinear tables/desks/cabinets/shelves,
  `deskEntitiesByTeleportID` tabletop slabs, `Hide Desk` parent groups, TV
  screen quads, empty water basins, luminaire groups, UV lightmap atlases,
  coplanar audits, and calibrated seat anchors. Whole-Room, shell, stair, and
  glazing 3D generation fails in practice because generative meshes warp planes,
  round corners, fuse addressable sub-entities, and bake false reflections into
  glass.
- **Source from licensed libraries or optional single-object image-to-3D**
  (standalone freeform and sculpted props): high-entropy organic and upholstered
  forms (sofas, lounge chairs, cushions, plants, rocks, ceramics, sculpture)
  plus standalone sculpted or ornate hard-surface props (curved solid-wood
  chairs, carved frames, decorative lamp bodies) that carry no architectural
  tolerances, large planar spans, or articulated sub-parts—avoiding "programmer
  art" chamfered boxes. Search the free licensed sources in
  [Materials and export](materials-and-export.md#asset-and-texture-inputs)
  first; use creator-authorized
  [Optional paid generation](optional-paid-generation.md) only when elected.
- **Bridge hybrid seats and multi-part/SubD objects**: for SubD industrial
  shapes or multi-part articulated equipment that neither simple `bpy` CSG nor
  raw image-to-3D solves cleanly alone, prefer a clean licensed mesh or split
  the assembly so Python builds the metric frames, hinges, glass, emitters, or
  bound surfaces while the imported mesh supplies only the static sculpted
  body. When an imported or generated chair hosts a selectable seat, normalize
  its axes and uniform scale, measure its actual backrest and cushion profile in
  Python to place the eye `0.25–0.35 m` in front of the backrest (never at the
  bounding-box center), and author any paired desk alignment surface as a clean
  Python slab.

## Run scripts inside Blender

With Blender on PATH, these are invocation patterns for scripts the agent
authors for the Room:

```sh
blender --background --factory-startup --python-exit-code 1 --python /absolute/path/to/build_room.py
blender --background --factory-startup /absolute/path/to/room-copy.blend --python-exit-code 1 --python /absolute/path/to/review_and_export_room.py
```

Use Blender's absolute executable path when it is not on PATH. The first form
starts a new scene; the second explicitly loads a saved source copy after
factory startup. Both avoid dependencies on personal startup files and
automatically enabled add-ons. These scripts are not included generators: the
skill's bundled scaffolder only creates metadata around a finished USDZ.

Set `--python-exit-code` before `--python` so an uncaught Python exception
fails the process. Scripts importing `bpy` run inside Blender, while the
bundled scaffolder, packer, and validator run with ordinary Python. Inspect
the installed Blender version's exporter arguments before using them.

Build through `bpy.data` and explicitly configured operators. Avoid dependencies
on an active viewport, current GUI selection, unsaved edits, or session-only
add-ons. Repeated builds should replace only their own scene or named
collection without accumulating duplicates. Save the `.blend` and separate
long authoring, baking, review, and export stages so they can be retried.

## Render, inspect, and repair

Create cameras at the intended seat eye positions and facing directions from
the metric layout. Render the principal comparison camera, the forward view and
enough overlapping views to inspect the full surround—including above and
below—for every seat. Include exterior views and the Room thumbnail. Save the
images with their camera and lighting settings.

Inspect the rendered pixels with an image-capable tool. Compare composition,
openings, floor levels, path clearance, focal points, and seating with both the
concept image and the metric plan. Check scale, contact with floors, clipping,
glass, texture scale, lighting, and usable desk space: keep the central work
reach zone of every mapped desk (`deskEntitiesByTeleportID`) completely clear of
open books or loose clutter (place edge lamps, book stacks, and candles only at
far side corners), build complete full-depth door frames (jamb liners spanning
wall thickness, threshold/sill, and interior/exterior casings rather than
face-only trim that exposes wall edges or leaks light), and always evaluate
vertex heights in **world space (`obj.matrix_world @ v.co`)** in grounding or
overlap-repair scripts so non-zero object origins never float furniture. Repair
the source and rerender affected views. Contact sheets and geometry checks help
organize review but do not prove app appearance. If image inspection is
unavailable, retain the renders and report visual review as pending. Do not ask
the creator to watch each modeling iteration.

Headless describes how Blender runs; visual review uses its saved images.
Choose render settings for the purpose: a polished Cycles image helps judge the
authored scene but does not demonstrate Locus's realtime appearance. Outdoor
scenery in the concept image represents Locus's runtime View rather than Room
geometry: you may use a Blender `World` shader (or a source-only preview
collection disabled for export) to judge daylight and framing, while keeping
windows transparent and openings clear.

## Export and finish the Room

Use export-compatible materials with file-backed color, roughness, and normal
maps. Bake procedural appearance when needed by the target format. Keep preview
cameras, authoring lights, and any temporary preview backdrops or sky domes out
of the exported model; declare any visitor-controlled lights using the Room
interface, and leave openings unobstructed for Locus's 360° View. Export the
required meter-scale, +Y-up USDZ, reopen a clean copy, and check the actual
entity names, material bindings, texture packaging, axes, and bounds.

Make the editable source portable as well as the USDZ. Keep texture originals
beside the source, use relative image paths, and pack the required images.
Blender can retain a separate absolute original path inside each packed image;
check both the image path and its packed-file paths. Move a copy of the source
bundle away from the original location, reopen it, unpack and reload its images,
then export again. Compare geometry, material connections, texture bytes, UVs,
and light directions with the delivered model; record any measured floating-
point round-trip differences. A packed-image icon alone does not prove
relocation works.

For baked Room lighting and architectural glazing, follow
[Lighting and glass](lighting-and-glass.md) as part of the headless build
pipeline—not as an afterthought. Name every receiver's base UV layer `st`, keep
glass, water, pure metals, moving `interactiveStates` parts, and fixture glows
out of `Locus_BakedIndirect`, and drive per-group `mode: "irradiance"` light
baking with the bundled `../scripts/bake_irradiance.py` script (validating
`bake-config.json` with `--validate-config-only` before spending Cycles GPU
time). Afterward, run `../scripts/audit_lighting_photometry.py` on the workspace
or packaged `.locusplace` to verify 16-bit PNGs, zero clipping, low speckle,
and clear overhead-off mood contrast. Keep `clearcoatRoughness >= 0.2` on
uncoated clear glass, and preserve `scene.cycles` and World settings across
baking and review stages. These steps fit this headless workflow and do not
require an additional service or a separate preview app.

Return to `../SKILL.md` for packaging, exact ZIP validation, and physical
Apple Vision Pro checks. Preserve editable sources, scripts, texture sources,
and review images outside the Package v2 archive. Background rendering cannot
replace the final device checks for appearance, tracking, and comfort.
