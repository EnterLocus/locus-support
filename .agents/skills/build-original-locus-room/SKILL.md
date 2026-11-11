---
name: build-original-locus-room
description: Build an original 3D Room for Locus on a Mac, from a concept image and metric layout to a checked Package v2 archive and physical Apple Vision Pro iteration. Use for a new Room or an original professional 3D scene. No image-generation provider or API key is required.
---

# Build an Original Locus Room

This public workflow takes an original Room from design input to a Package v2
archive that a creator checks on Apple Vision Pro. A concept image guides the
design; it is not proof that the delivered Room works, looks right, or is
comfortable on device.

It runs from a clone of the public `locus-support` repository with Blender,
macOS, Xcode or the Xcode Command Line Tools, and the installed Locus app. It
does not need private Locus source code, internal tools, a Simulator, an API
key, or a particular image-model vendor. Commands below are relative to the
public repository root. Use Python 3.9 or later and pass the Locus version
being targeted to `--current-app-version`.

Package a Room and a View as separate Package v2 import archives with separate
stable `packageID` values. This is the default even when they are designed as a
pair: each archive can then be replaced, removed, and iterated without changing
the other. A combined Package v2 archive remains supported for content that
really shares one lifecycle, but is not the normal creation or review delivery.

Any capable external agent can perform the normal workflow. For a clean-room
demonstration, start that agent with fresh context and give it only the public
repository, this skill, the creator's inputs, and public tools. Do not use a
Simulator in either case. Renders and archive checks establish useful evidence
but leave physical-device appearance, tracking, scale, and comfort as device
acceptance gaps until the creator checks them.

## The four steps

Read the linked reference when beginning its step. The public
[Package v2 guide](https://enterlocus.com/reference/locusplace-format/) and
[field reference](https://enterlocus.com/reference/locus-asset-format/) are
the canonical online contracts.

| Step | Creator and agent outcome | Reference |
| --- | --- | --- |
| 1. Choose a concept image | The creator supplies or selects one clear visual target. | [Concept and brief](references/concept-and-brief.md) and [design language](references/design-language.md) |
| 2. Derive a metric layout | The agent turns that image into a buildable floor plan and seat layout before modeling. | [Concept and brief](references/concept-and-brief.md) and [larger Rooms](references/larger-rooms.md) |
| 3. Build, review, and package | The agent models from both inputs, repairs the editable source, and produces a checked Room-only Package v2 archive plus portable editable source. | [Headless Blender](references/blender-headless.md), [materials and export](references/materials-and-export.md), [lighting and glass](references/lighting-and-glass.md), [Room TVs](references/room-tvs.md), and [Package v2 delivery](references/package-v2.md) |
| 4. Check on Apple Vision Pro and iterate | The creator checks the exact archive on the physical device and sends screenshots and concrete findings back to the agent for revisions. | [Device preview and report](references/device-preview-and-report.md) |

## 1. Choose a concept image

The creator produces or selects a single concept image using ChatGPT, any
text-to-image model, another image model, a supplied photo or sketch, a
Blender blockout, or their own image. Image generation is optional: there is
no provider, API, or paid-service prerequisite. The image should establish the
principal view, mood, architectural type, major materials, opening, and
day/night state. It is the camera and visual target for review.

Outdoor mountains, water, clouds, or city light in the concept image establish
framing and daylight, **not** geometry for the Room. In Virtual Space, Locus
surrounds the Room with whichever 360° View the visitor pairs with it. Never
model or export a skybox sphere, curved backdrop/cyclorama, scenery card, or
distant terrain mesh inside the Room's `scene.usdz`.

Record the Room's intended purpose, each seat and its purpose, desk-backed
seats, visitor-controlled lamps, optional TVs, animation or sound, and a rights
inventory for every supplied or incorporated asset. Record material AI use
truthfully in `provenance.json`: `aiGenerated: true` names every materially
contributing generative provider in `aiProvider`; a DCC, renderer, exporter,
or ordinary build tool is not an AI provider. Embedded content must permit
redistribution in the delivered USDZ.

## 2. Derive a metric floor plan and seat layout

Before building geometry, the agent derives a metric floor plan from the
concept image. It is a layout target, not a dump of exported anchors. Specify
the Room envelope and dimensions; opening widths, heights, and locations;
floor levels and transitions; usable paths and clearance; and the View opening
or virtual wall/roof references. Room Portal opens detected real walls;
virtual references do not create portals.

For every seat, record its intended eye position and facing direction, purpose,
forward focal point, and whether it is desk-backed or lounge seating. For a
desk-backed seat, define the tabletop and usable working relationship; for a
lounge seat, define the relaxed view and circulation around it. Include the
principal comparison camera's eye height, direction, framing, and field of
view. The plan must make each path, seat surround, ceiling height, and opening
reviewable before detail work begins.

When the Room has a natural place to sit and watch, such as a living room
sofa, media room, den or bedroom, offer a TV; Room TVs require Locus 1.4.9 or
later. Plan each TV with the seats that watch it: size it by viewing distance,
face it toward its main seat, keep its center near seated eye level, and leave
the area under it clear for the remote. See [Room TVs](references/room-tvs.md).

## 3. Build from the image and layout, then package the result

The agent models from both the concept image and the metric layout, preserving
the editable source, scripts, textures, and review renders. Blender Python in
background mode is the default build route and needs no Blender MCP; another
professional 3D workflow is fine when the creator chooses it. Use
[Headless Blender](references/blender-headless.md) for the default route and
[Materials and export](references/materials-and-export.md#asset-and-texture-inputs)
for asset inputs. When existing assets would improve the requested quality or
save work, actively look for suitable licensed models and textures; candidates
include [Poly Haven](https://polyhaven.com/models), NVIDIA's
[SimReady assets](https://huggingface.co/datasets/nvidia/simready-assets), and
Scenario's [3D collection](https://huggingface.co/datasets/scenario-labs/3d-collection),
and [Amazon Berkeley Objects GLB](https://huggingface.co/datasets/codepawl/abo-glb)
for furniture and household objects (CC BY 4.0; retain attribution and changes).
The creator can also provide assets or use ChatGPT or another image model to
generate textures. Select only useful assets, verify their individual terms,
record provenance, and prepare them for Blender and USDZ export. Free or
generated inputs are optional, and no paid provider is a prerequisite.
Tripo is an optional image-to-3D route, never a prerequisite; see
[optional paid generation](references/optional-paid-generation.md).
Match the comparison camera to the concept image, review the blockout before
detail, and review the finished Room against both the image and layout.

Render the principal view, exterior and thumbnail views, plus enough
overlapping views at every declared seat to inspect the forward view, complete
surround, above, and below. Fix the editable source—not a hand-edited ZIP—for
floating or intersecting objects, unsupported props, incomplete walls, light
leaks, backwards fixtures, clipping, poor sightlines, or unusable desk space.
Seat eye points belong in front of the backrest over the cushion, not at a
chair center. Use [Materials and export](references/materials-and-export.md)
for export-safe PBR and [Lighting and glass](references/lighting-and-glass.md)
for controlled fixtures, receiving-surface light, or glazing. A lamp that only
glows as a fixture is incomplete when the intended scene calls for it to light
nearby architecture: bake its contribution into intentional opaque receiving
surfaces. Use one baked layer per independently switchable, dimmable, or
recolorable luminaire group; a single shared atlas is only appropriate for
light that is controlled solely by Room master/overall EV.

Model each TV screen as one flat 16:9 quad of its own, with its own UVs and a
non-emissive off-state material, set a few millimetres in front of its frame.
Declare it in `tvs` and set `minimumAppVersion` to `1.4.9` or later, as
described in [Room TVs](references/room-tvs.md).

Before delivery, follow [Flicker prevention](references/flicker-prevention.md):
avoid duplicate and near-coplanar surfaces, run the public geometry audit on
the source and exact exported USDZ, and review a slow camera move. Fix reported
visible-surface risks or document an intentional overlap; record incomplete
scopes. Do not wait for creator feedback to inspect lamp openings, trim,
glazing, and thin detail. A clean geometry report does not prove no flicker.

Export one self-contained USDZ in meters, +Y up, with world -Z forward, and
store its ZIP members uncompressed. Leave window glazing transmissive and
openings completely clear to the outside world: exclude any Blender World
environment or temporary preview backdrop from `scene.usdz` along with preview
cameras and authoring lights. Inspect the exported USDZ as well as the
authoring scene: its axes, scale, unique
referenced entity names, texture packaging and paths, transparency, fixture
emission, and bounds. `usdchecker` can accept a USDZ whose appearance is still
wrong in the app.

Package the Room as a Room-only Package v2 archive—the canonical
feature-complete import format—and deliver that importable archive together
with portable editable source. If this Room has a companion View, package and
deliver the View independently with its own `packageID`; do not combine them
for an ordinary iteration. Preserve the Room `packageID`, space ID, teleport
IDs, and exported entity names across Room revisions; increase `contentVersion`
whenever that archive's bytes change. Derive `anchorXZ` and
`sourceFloorOffset` from the final exported USDZ bounds after axis and
root-transform conversion, rather than copying DCC coordinates. Use
`tools/pack_locusplace.py` and `tools/validate_locusplace.py` as described in
[Package v2 delivery](references/package-v2.md).

The older five-file flat ZIP is a compatibility appendix in
[room interface](references/room-interface.md): it receives a new UUID on each
import and is not this workflow's default delivery format.

Validate the exact delivery archive with an explicit, empty render directory:

```sh
python3 tools/check_room.py --current-app-version <target-version> \
  --renders /absolute/path/to/renders /absolute/path/to/MyRoom.locusplace
```

Read every checker warning and inspect the complete render contact sheet. In
`check_room.py` renders, clear windows and openings are expected to show the
checker's neutral gray lighting scaffold rather than outdoor scenery; painted
mountains or sky through a window mean an exported backdrop mesh is blocking
the View. `--current-app-version` and the explicit `--renders` directory are
required evidence for this handoff. Correct the editable source, rebuild,
repack, and recheck when either render review or the checker exposes a problem.
A passing archive remains narrower evidence than physical-device acceptance.

## 4. Check the exact archive on Apple Vision Pro and iterate

The creator imports the exact checked Package v2 archive from Files or a direct
HTTPS URL on a physical Apple Vision Pro. In **Preview in 3D**, inspect the
full model, materials, bounds, and thumbnail relationship. Pair the Room with
a View, enter Virtual Space, and check actual appearance, scale, reach,
readability, comfort, and lighting in the intended conditions.

Try every declared seat: its forward view, full surround, headroom, footroom,
focal point, clipping, facing direction, and usable path. For every desk-backed
seat, check tabletop alignment and **Hide Desk** when declared; its group must
contain the table and everything resting on it. Try every light control and,
if present, each experimental animation switch, speed, and replay interval.
Turn on every TV from the seats that watch it, using Locus 1.4.9 or later.

The creator sends the archive hash, screenshots or recordings, and concrete
observations to the agent. For example, record when a lamp flickers or show a
wall fixture from multiple angles when it appears detached. Investigate the
actual cause; do not assume a static render proves a flicker fix. The agent
repairs the editable source, exports a new USDZ, rebuilds the archive, reruns the exact-archive
checker and affected render review, and returns a revised archive. Reimport the
revised archive while keeping the stable IDs, incremented `contentVersion`, and
saved settings behavior described in the device reference; then repeat the
affected physical-device checks on that exact revised archive. Report its hash,
target app version, checks performed, and every unavailable check as `not
verified`. Do not infer device acceptance from a render, importer result,
command exit code, or archive validation.

## License

This skill, its references, and bundled scripts are licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). See
`LICENSE.md` and `LICENSES/Apache-2.0.txt` in the repository for scope.
