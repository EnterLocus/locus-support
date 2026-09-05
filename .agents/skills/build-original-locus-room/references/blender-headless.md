# Build with Blender Python in background mode

Use this route when a coding agent creates a Room from a brief without an
explicitly chosen authoring tool. It requires an installed Blender executable,
permission to run local scripts, and an image-capable tool to inspect saved
renders. It does not require an open Blender window, an MCP server, or a person
operating the viewport. Preserve a creator's explicit choice of another tool.

## Prepare reproducible inputs

Locate Blender and record its version. Keep the brief, builder scripts, render
settings, and asset inventory with the project. Use explicit source and output
paths and fixed random seeds where procedural variation is involved. Preserve
the original Room when revising it and write a separate output version.

Python can model architecture and assemble external furniture, plants, PBR
materials, and lighting environments. Download chosen assets before building,
retain their local files, and record source URLs, licenses, required credits,
and hashes. Check that their terms permit redistribution inside the Room USDZ.
Do not limit a headless build to primitive furniture or flat colors, and do
not assume that an asset library or paid generation service is required.

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
automatically enabled add-ons. These
scripts are not included generators: the skill's bundled scaffolder only
creates metadata around a finished USDZ and thumbnail.

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

Create cameras at the actual declared seat positions and orientations. Render
the forward view and enough overlapping views to inspect the full surround,
including above and below, for every seat. Include exterior views and the
Room thumbnail. Save the images with their camera and lighting settings.

Inspect the rendered pixels with an image-capable tool. Check composition,
scale, contact with floors, clipping, glass, texture scale, lighting, and
usable desk space. Repair the source and rerender affected views. Contact
sheets and geometry checks help organize review but do not prove appearance.
If image inspection is unavailable, retain the renders and report visual
review as pending. Do not ask the creator to watch each modeling iteration.

Headless describes how Blender runs; visual review uses its saved images.
Choose render settings for the purpose: a polished Cycles image helps judge
the authored scene but does not demonstrate Locus's realtime appearance.

## Export and finish the Room

Use export-compatible materials with file-backed color, roughness, and normal
maps. Bake procedural appearance when needed by the target format. Keep
preview cameras and authoring lights out of the exported model; declare any
visitor-controlled lights using the Room interface. Export the required
meter-scale, +Y-up USDZ, reopen a clean copy, and check the actual entity names,
material bindings, texture packaging, axes, and bounds.

Make the editable source portable as well as the USDZ. Keep texture originals
beside the source, use relative image paths, and pack the required images.
Blender can retain a separate absolute original path inside each packed image;
check both the image path and its packed-file paths. Move a copy of the source
bundle away from the original location, reopen it, unpack and reload its images,
then export again. Compare geometry, material connections, texture bytes, UVs
and light directions with the delivered model; record any measured floating-point
round-trip differences. A packed-image icon alone does not prove relocation works.

For indirect-light atlases and architectural glazing, use
[Lighting and glass](lighting-and-glass.md). It explains linear float baking,
UV roles, RGB16 texture encoding, and the difference between base roughness
and clearcoat roughness. These steps fit this headless workflow and do not
require an additional service or a separate preview app.

Return to `../SKILL.md` for scaffolding, exact ZIP validation, and the Locus
import-and-entry checks. Preserve editable sources, scripts, texture sources,
and review images outside the five-file ZIP. Background rendering cannot
replace the final Apple Vision Pro checks for appearance, tracking, and comfort.
