# Package v2 delivery

Package v2 is the Room workflow's default delivery format. It keeps stable
identity and updates, unlike a flat compatibility ZIP. The ZIP root contains
`locusplace.json` and `catalog/`; a Room lives at
`catalog/spaces/<space-id>/`. Read the public
[complete Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
for every metadata field and minimum version.

## Package one independently managed Place at a time

Make the normal Room delivery a Room-only archive with its own stable
`packageID`. If it has a companion View, make a separate View-only archive and
give it a different `packageID`. Deliver, hash, validate, import, replace, and
review those archives independently. The app can pair an installed View and
Room; an ordinary Room iteration does not need a combined archive or an
Experience.

Package v2 still supports a combined archive containing a View, Room, and
Experience. Use it only when those contents intentionally have one update and
removal lifecycle. Removing an import removes the whole import, so a combined
archive is not the default for separate Room and View work.

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
overwrite an existing archive. Never edit its output ZIP by hand. Pack a
companion View from a different View-only source directory to a different
output filename; do not add it to this Room archive just for review.

## Review a companion View as a complete sphere

A separate companion View is its own delivery, not merely the image visible
through Room windows. Validate its exact View-only archive with the public
[Package v2 guide](https://enterlocus.com/reference/locusplace-format/) and
the existing archive validator:

```sh
python3 tools/validate_locusplace.py --current-app-version <target-version> \
  /absolute/path/to/MyView.locusplace
```

Then inspect the actual 2:1 panorama at a usable size: the intended forward
view and back, both left/right seam edges, zenith, and nadir. An 8K header or a
passing validator proves dimensions and package structure, not full-sphere
image quality. A thumbnail or Room-window framing cannot stand in for this
review.

If the panorama uses a flat artificial fill, mirrored region, or cropped source
outside its intended window backdrop, disclose that exact limitation as a
limited companion background. Do not describe it as a polished independent
360° View. When reusing previously accepted, unchanged View media, record its
exact hash and known limitations instead of remaking media that the Room
iteration did not request.

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
decorative output. Its scaffold renderer does not implement lamp controls,
proxies, baked-light-layer mixing, or the selected View. It cannot prove that a
lamp actually changes a wall, floor, tabletop, or ceiling in the app. The
resulting renders help find geometry, material, and camera problems but cannot
establish lighting aesthetics, physical comfort, or real-world alignment.
