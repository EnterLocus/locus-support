---
name: build-original-locus-room
description: Build an original 3D Room for Locus on a Mac, from a brief or reference image to a checked Package v2 archive and Apple Vision Pro preview. Use for a new Room or for adapting an original professional 3D scene. The workflow uses no API key; paid generation is optional.
---

# Build an Original Locus Room

This is a sample skill for taking an original Room from a brief to an importable
Package v2 archive. It uses a reference image as the design and camera target, a
repeatable 3D build, an exported USDZ as the source of truth for seats, the
public Room checker, and device preview. It is not a promise that a render or
an archive alone proves comfort or appearance on Apple Vision Pro.

The required workflow runs on **macOS** with Blender and Xcode or the Xcode
Command Line Tools. The checks use macOS image and USD tooling. There is no
supported non-Mac route. Start in a clone of the public `locus-support`
repository; commands below use paths relative to its root. Use Python 3.9 or
later and pass the Locus version being targeted to `--current-app-version`.

No API key is required. A supplied photo, sketch, or Blender blockout can be
the reference image. Paid image generation, image-to-3D, material relief, and
audio are optional additions, never prerequisites; see
[optional paid generation](references/optional-paid-generation.md).

## Stages

Read the reference for each stage when that stage begins.

| Stage | Deliverable | Reference |
| --- | --- | --- |
| 1. Brief and concept | Brief, seat plan, and one approved reference image | [Concept and brief](references/concept-and-brief.md) and [design language](references/design-language.md) |
| 2. Model from the image | Reproducible source, blockout and final review renders | [Headless Blender](references/blender-headless.md) |
| 3. Materials and export | Self-contained, meter-scale, +Y-up USDZ | [Materials and export](references/materials-and-export.md) |
| 4. Optional lights | Fixture bodies, proxies, and optional baked indirect layer | [Lighting and glass](references/lighting-and-glass.md) |
| 5. Package v2 | Source directory, archive, and USDZ-derived seats | [Package v2 delivery](references/package-v2.md) |
| 6. Check and review | Checked archive and inspected render contact sheet | [Package v2 delivery](references/package-v2.md#validate-the-exact-archive) |
| 7. Device preview | Import, Preview in 3D, seats, lights, and Hide Desk | [Device preview and report](references/device-preview-and-report.md) |
| 8. Report | SHA-256, evidence, and explicit open checks | [Device preview and report](references/device-preview-and-report.md#write-the-report) |

For many floors, seats, and lamps, add [larger Rooms](references/larger-rooms.md)
to the plan. The public [Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
and [field reference](https://enterlocus.com/reference/locus-asset-format/)
are the canonical online contracts.

## 1. Establish the deliverable and rights

Write down the Room's intended purpose, principal view, each seat and its
purpose, desk-backed seats, visitor-controlled lamps, View opening, and any
optional animation. Room Portal opens detected real walls; virtual wall and
roof references do not create portals.

Inventory every model, texture, image, font, and generated input. Record each
non-original component's creator, source URL, license identifier and URL, and
required credit. `provenance.json` must describe AI use truthfully:
`aiGenerated: true` names every materially contributing generative provider in
`aiProvider`. A DCC, renderer, exporter, or ordinary build tool is not an AI
provider. Embedded content must permit redistribution in the delivered USDZ.

## 2. Brief, reference image, and model

Turn the brief into one reference image. Any image model is acceptable but
optional: use a creator-supplied photo or sketch, or render a simple Blender
blockout. The selected image sets both the thumbnail viewpoint and the camera
used to compare the blockout and final model. A concept image is design input,
not proof of a working Room.

Build original geometry with the creator's preferred professional 3D workflow.
When no tool is specified, use Blender Python in background mode and save the
scripts and review renders. Match a camera to the reference's eye height,
direction, field of view, and framing. Compare the blockout to it before
adding detail, then compare the finished Room again.

Review every seat in the source: its forward view, a 360-degree surround, and
the view above and below. Repair floating or intersecting objects, unsupported
props, incomplete walls, light leaks, backwards fixtures, clipping, and poor
sightlines before export. Place each eye point in front of the backrest over
the cushion, not at the chair's center.

For a desk-backed seat, the desktop must be a real slab with thickness. Map
the seat to the actual tabletop, not a parent containing legs, chairs, lamps,
computers, or props. If offering **Hide Desk**, make a separate group contain
the table and every object resting on it; the tabletop is a descendant of that
group. Keep seat IDs and exported entity names stable across revisions.

## 3. Materials and export

Export one self-contained USDZ in meters, +Y up, with world -Z forward. Store
its ZIP members uncompressed. Use file-backed base-color, roughness, metallic,
and normal maps where appropriate, and bake procedural looks to images.

Inspect the exported USDZ, not only the authoring viewport. Confirm the axes,
scale, unique referenced entity names, embedded texture paths, controlled
fixture emission, and transparency parameters. `usdchecker` can accept a
USDZ whose appearance is still wrong in RealityKit.

Common export failures are covered in
[materials and export](references/materials-and-export.md): give open thin
objects real thickness because double-sided material intent is back-face
culled; split a packed ORM image into grayscale roughness and metallic maps;
point thin leaf normals outward; and do not add a terrain base that blocks View
water or inflates the Room bounds.

## 4. Optional lighting and animation

Treat a `luminaireGroups` entry as one visitor control: fixture bodies make the
lamp look on, bounded proxies provide direct light, and optional
`bakedIndirect.entities` provide broad diffuse response. The fixture body must
remain visibly emissive even where its proxy is scoped with `nearTeleportIDs`.
Respect the Room v3 safety limits: no more than 12 authored proxies, 4 active
at a seat, 1 shadow-casting proxy, 10,000 lumens per proxy, and per-light
brightness between -4 and +1 EV.

Experimental `ambientAnimations` may change. Add them only after the USDZ
contains the named clips; test every switch, speed, and replay interval. Do
not describe a checker pass as proof that an animation looks right.

## 5. Package v2 and derive seats from the USDZ

Package v2 is the default and canonical feature-complete import format. Its
ZIP root contains `locusplace.json` and `catalog/`; the Room is under
`catalog/spaces/<space-id>/`. It preserves stable IDs: keep `packageID`, space
ID, and teleport IDs stable. Increase `contentVersion` whenever the archive
bytes change. Run `tools/validate_locusplace.py` as part of packing, then use
the Room checker as the required delivery validation. Starting with Locus
1.4.5, reimporting a changed payload with the same imported `packageID` asks
before replacing it and keeps its saved settings and organization.

Run `tools/pack_locusplace.py` for the archive. Do not copy DCC coordinates
into `anchorXZ`: derive `anchorXZ` and `sourceFloorOffset` from the final
exported USDZ bounds after axis and root-transform conversion. The bundled
`scripts/locus_room_v2.py` helper reads those bounds through Blender's bundled
`pxr`, turns friendly seat positions into the Package v2 `houses` teleport
format, and prints eye points for review cameras. Its full use is in
[Package v2 delivery](references/package-v2.md).

The old five-file flat ZIP is only a compatibility appendix in
[room interface](references/room-interface.md). It receives a new UUID on
each import and is not this workflow's default delivery format.

## 6. Validate the exact archive and review renders

For every delivery, run the public Room checker against the exact archive with
an explicit, empty output directory for its seat renders:

```sh
python3 tools/check_room.py --current-app-version <target-version> \
  --renders /absolute/path/to/renders /absolute/path/to/MyRoom.locusplace
```

The checker verifies Package v2 structure and Room bindings, reports entry
risks, and produces render evidence. Read every warning and inspect the whole
render contact sheet. Correct the editable source and rebuild; never patch the
ZIP by hand. A pass does not prove physical comfort, real-world alignment, or
device appearance.

## 7. Preview on Apple Vision Pro

Import the exact checked archive from Files or a direct HTTPS URL. Use
**Preview in 3D** from the Room card, pair the Room with a View, enter Virtual
Space, and try every declared seat, light control, and Hide Desk. Exercise
desk alignment, reach, scale, lighting, and comfort from more than one seat.
Simulator and render evidence cannot substitute for this device check.

## 8. Report

Report the archive's SHA-256, target app version, checker result, render
contact sheet, imported/entered result, seat-by-seat and control-by-control
device result, and anything not yet checked. An independent reviewer should
inspect the archive, checker output, renders, and device evidence separately
from the author. Say `not verified` for unavailable device checks; never infer
them from a simulator, a launch command, or a successful ZIP validation.

## License

This skill, its references, and bundled scripts are licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). See
`LICENSE.md` and `LICENSES/Apache-2.0.txt` in the repository for scope.
