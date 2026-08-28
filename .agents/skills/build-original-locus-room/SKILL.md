---
name: build-original-locus-room
description: Build and validate an original 3D Room asset for Locus from visual references, including Blender authoring, USDZ packaging, usable teleport seats, and import-and-entry checks. Use when creating or revising an original Locus Room; do not use for importing an unchanged third-party model.
---

# Build an Original Locus Room

This is a sample skill for creating an original Room that can be imported into
Locus. It uses Blender through Blender MCP for 3D authoring. Adapt it to the
user's tools and workflow. Follow the current
[Room package reference](https://enterlocus.com/package-format/) and validate
the finished archive before delivery.

## Check the Blender connection

Before modeling, confirm that Blender MCP can read the active Blender scene,
create or edit an object, save the `.blend` source, and export the result. If
Blender MCP is unavailable, stop and tell the user; do not claim that geometry
or Blender checks were completed.

## Understand the request

Treat images and drawings as visual references rather than geometry to trace.
Confirm the Room's purpose, size, layout, materials, lighting, important views,
and required seats or desks. State any assumption that changes the floor count,
footprint, or deliverables.

Record known creators, sources, licenses, requested credit, modifications, and
AI use truthfully in `provenance.json`. Use only assets the user has the right
to use.

## Build the Room

- Create original geometry at human scale with metric dimensions.
- Use file-backed materials that export cleanly to USDZ.
- Check stairs, rails, ceilings, furniture clearance, normals, glass, and
  collision before export.
- Keep editable sources outside the runtime ZIP and export one self-contained,
  meter-scale, +Y-up USDZ.
- Create a current exterior preview that shows the complete Room.

## Add entry seats

Every Room needs a `teleportCatalog` whose selected house contains at least one
calibrated, usable seat. Give each selectable work seat its own desk or table.
Do not add a seat preset that has no usable place to sit or work.

Check each seat from its intended eye height and direction. Review the forward
view, the full surround, overhead clearance, nearby furniture, and circulation.

## Package and check the Room

Start from the [public authoring examples](https://enterlocus.com/create-your-own-place/).
Use the public packer to create the ZIP, then run the
[public Python validator](https://enterlocus.com/tools/validate_locusplace.py)
on the exact archive that will be delivered.

Passing the validator confirms the archive structure, metadata, referenced
assets, and machine-checkable limits. It does not prove that the Room is
comfortable, correctly scaled in use, or visually complete.

Import that archive into Locus, pair it with a View, enter the Room, and try
every declared seat on Apple Vision Pro. Fix any scale, material, placement,
clearance, or view problem before delivery.

Report the archive path, content version, validator result, tested seats, and
any check that remains pending.
