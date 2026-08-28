---
name: build-original-locus-room
description: Build and validate an original 3D Room ZIP for Locus with Blender MCP, a self-contained USDZ, a required thumbnail, usable entry seats, truthful provenance, and import checks. Use when creating or revising an original Locus Room.
---

# Build an Original Locus Room

This is a sample skill for creating one Room that can be imported into Locus.
It uses Blender through Blender MCP for 3D authoring. Follow the current
[Room ZIP reference](https://enterlocus.com/package-format/) and validate the
finished archive before delivery.

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
AI use truthfully in `provenance.json`. Set `aiGenerated` to `true` and name
the provider in `aiProvider` when AI contributed to the Room. Use only assets
the user has the right to use. The license must describe the asset rights, not
the App Store agreement for the Locus app.

## Build the Room

- Create original geometry at human scale with metric dimensions.
- Use file-backed materials that export cleanly to USDZ.
- Check stairs, rails, ceilings, furniture clearance, normals, glass, and
  collision before export.
- Keep editable sources outside the runtime ZIP and export one self-contained,
  meter-scale, +Y-up USDZ.
- Create a current `thumbnail.jpg` that shows the complete Room.

## Add entry seats

Every Room needs at least one calibrated, usable point in
`teleport-points.json`. Give each selectable work seat its own desk or table.
Do not add a seat preset that has no usable place to sit or work.

Check each seat from its intended eye height and direction. Review the forward
view, the full surround, overhead clearance, nearby furniture, and circulation.

## Package and check the Room

Create one flat directory with exactly these root files:

```text
room/
|-- space.json
|-- provenance.json
|-- teleport-points.json
|-- scene.usdz
`-- thumbnail.jpg
```

Do not add an ID, parent folder, `.blend`, GLB, source texture, or any file not
listed above. Put the user-visible name in `space.json` as `displayName`; Locus
assigns a UUID at import. Duplicate display names are allowed.

Use the scripts included with this sample skill to create and validate the
exact ZIP that will be delivered:

```sh
python3 scripts/pack_locus_asset.py /absolute/path/to/room /absolute/path/to/room.zip
python3 scripts/validate_locus_asset.py /absolute/path/to/room.zip
```

Passing the validator confirms the archive structure, metadata, referenced
assets, and machine-checkable limits. It does not prove that the Room is
comfortable, correctly scaled in use, or visually complete.

Import that archive into Locus, pair it with a View, enter the Room, and try
every declared seat on Apple Vision Pro. Fix any scale, material, placement,
clearance, or view problem before delivery.

Report the archive path, validator result, tested seats, and any check that
remains pending.
