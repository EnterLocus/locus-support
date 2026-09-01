---
name: build-original-locus-room
description: Prepare and validate an original 3D Room for Locus using the public Room ZIP, seat, entity, desk, lighting, provenance, and device-verification contracts. Use when creating or revising an original Locus Room in any professional 3D workflow.
---

# Build an Original Locus Room

This is a sample skill for integrating an original 3D environment with Locus.
Respect the creator's preferred 3D tools and established authoring workflow.
Concentrate on the public Locus interface, deterministic packaging, validation,
and honest reporting; do not substitute generic modeling advice for the
creator's judgment.

Follow the current
[Room ZIP reference](https://enterlocus.com/reference/locus-asset-format.md)
and validate the exact finished archive before delivery.

## Establish the deliverable

Confirm the intended Room, important views, entry seats, optional desks, Room
Portal surfaces, and visitor-controlled lights. State any assumption that
changes the Room interface or delivered files.

Record known creators, sources, rights, requested credit, modifications, and
AI use truthfully in `provenance.json`. Set `aiGenerated` to `true` and name
the provider in `aiProvider` when AI contributed. Use only assets the creator
has the right to use.

## Apply the Locus interface

- Export one self-contained, meter-scale, +Y-up USDZ with world -Z forward.
- Give every metadata-referenced entity a stable, unique exported name.
- Declare exactly one View opening and at least one usable entry seat.
- Keep teleport IDs stable across revisions.
- Map an optional desk seat to the tabletop entity itself, not a hierarchy
  containing legs, chairs, lamps, computers, or props.
- Name optional wall and roof entities explicitly for spatial adaptation.
- Create a current `thumbnail.jpg` that represents the delivered Room.

## Declare optional lighting

Treat each `luminaireGroups` entry as one logical visitor control.
`entities` names the emissive fixture bodies; `proxy` or Room-v3 `proxies`
declares bounded direct sources. `nearTeleportIDs` scopes only those direct
sources to selected seats. It must not make an enabled fixture body appear off
from another seat.

Room v3 may declare `bakedIndirect.entities` for an authored, low-frequency
indirect receiver layer. Keep glass, water, transmissive materials, luminaire
glow meshes, and fixture-specific halos out of it. Locus scales the layer with
the Room Lights master and Overall Room EV; per-light switches and color
controls do not recolor the shared bounce.

Respect the Room-v3 safety contract: no more than 12 authored proxies, 4 active
proxies at a seat, 1 shadow-casting proxy, 10,000 lumens per proxy, and a
brightness range within -4...+1 EV. These limits are not modeling or lighting
recommendations.

## Package the Room

Create one flat directory with exactly these root files:

```text
room/
|-- space.json
|-- provenance.json
|-- teleport-points.json
|-- scene.usdz
`-- thumbnail.jpg
```

Do not add an ID, parent folder, editable source, GLB, source texture, cache, or
any other file. Put the user-visible name in `space.json` as `displayName`;
Locus assigns a UUID at import and allows duplicate display names.

Use the scripts included with this sample skill to create and validate the
exact ZIP:

```sh
python3 scripts/pack_locus_asset.py /absolute/path/to/room /absolute/path/to/room.zip
python3 scripts/validate_locus_asset.py /absolute/path/to/room.zip
```

Passing the validator confirms the archive structure and machine-checkable
asset requirements. It does not prove comfort, scale, appearance, or runtime
behavior.

Import that archive into Locus, pair it with a View, and try every declared
seat on Apple Vision Pro. Exercise every desk mapping, adaptive surface, and
light control that the Room declares. Correct the source and rebuild rather
than patching the ZIP by hand.

Report the archive path, validator result, tested seats and interfaces, and any
physical-device check that remains pending.
