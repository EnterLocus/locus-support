# Package v2 delivery

Package v2 is the Room workflow's default delivery format. It keeps stable
identity and updates, unlike a flat compatibility ZIP. The ZIP root contains
`locusplace.json` and `catalog/`; a Room lives at
`catalog/spaces/<space-id>/`. Read the public
[complete Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
for every metadata field and minimum version.

## Derive seats from the final USDZ

Never normalize seats against a DCC viewport or an earlier export. The
delivered USDZ's visual bounds define the coordinate frame:

```text
anchorX = (floorX - boundsMinX) / (boundsMaxX - boundsMinX)
anchorZ = (floorZ - boundsMinZ) / (boundsMaxZ - boundsMinZ)
sourceFloorOffset = floorY - boundsMinY
```

Use the bundled helper. `bounds` needs Blender's bundled Python (or a Python
with `pxr`); save the resulting JSON and ordinary Python can perform the later
steps:

```sh
BLENDER_PYTHON=/Applications/Blender.app/Contents/Resources/<version>/python/bin/python3.x
$BLENDER_PYTHON .agents/skills/build-original-locus-room/scripts/locus_room_v2.py \
  bounds /absolute/path/to/scene.usdz > /absolute/path/to/bounds.json

python3 .agents/skills/build-original-locus-room/scripts/locus_room_v2.py \
  seats --bounds-json /absolute/path/to/bounds.json \
  --seats /absolute/path/to/seats.json --house-id space.example-room \
  --output /absolute/path/to/teleport-points.json

python3 .agents/skills/build-original-locus-room/scripts/locus_room_v2.py \
  eye-points --bounds-json /absolute/path/to/bounds.json \
  --teleports /absolute/path/to/teleport-points.json
```

`seats.json` is an authoring input, not package metadata. Each entry needs an
`id`, `title`, positive `eyeHeight`, exactly one `floor` or `eye` coordinate,
and exactly one facing value: `yawRadians`, `lookAt`, or `facing`. Coordinates
are USD coordinates by default; pass `--frame blender` only when the input uses
Blender's Z-up coordinates. The helper rejects seats outside the final X/Z
bounds and prints the resulting eye points for review cameras.

To convert an existing flat `teleport-points.json` without altering point
records, use:

```sh
python3 .agents/skills/build-original-locus-room/scripts/locus_room_v2.py \
  convert-points /absolute/path/to/flat-teleport-points.json \
  --house-id space.example-room --output /absolute/path/to/teleport-points.json
```

The output uses the Package v2 `{"houses": {"space-id": [...]}}` shape.
Review all values after conversion; changing an archive's bytes later requires
an increased `contentVersion`.

## Pack the source directory

Keep editable Blender files, scripts, source textures, and renders outside the
Package v2 source directory. Set stable `packageID` and space ID values once,
then increment `contentVersion` whenever an archive changes. Generate the
archive with the public packer:

```sh
python3 tools/pack_locusplace.py --current-app-version <target-version> \
  /absolute/path/to/editable-package /absolute/path/to/MyRoom.locusplace
```

The packer creates the manifest file inventory and content hash. It refuses to
overwrite an existing archive. Never edit its output ZIP by hand.

## Validate the exact archive

Run the Room checker after the final pack, not a checker against a staging
directory. Pass an explicit empty render directory and inspect its contact sheet
before delivering:

```sh
python3 tools/check_room.py --current-app-version <target-version> \
  --renders /absolute/path/to/renders /absolute/path/to/MyRoom.locusplace
```

The checker covers Package v2 structure, USDZ/resource checks, Room bindings,
entry risks, and seat-view render evidence. Treat warnings as review work, not
decorative output. The resulting renders help find geometry, material, and
camera problems but cannot establish physical comfort or real-world alignment.
