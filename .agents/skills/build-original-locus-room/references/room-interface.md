# Locus Room interface reference

Use this bundled reference when authoring offline. The public reference at
<https://enterlocus.com/reference/locus-asset-format.md> remains canonical.

## Coordinate and archive contract

- Use right-handed meters, +Y up, and world -Z forward.
- Quaternions are `[x, y, z, w]`.
- A Room ZIP is flat and contains exactly `space.json`, `provenance.json`,
  `teleport-points.json`, `scene.usdz`, and `thumbnail.jpg`.
- The USDZ is self-contained, stores its members without compression, and must
  pass `usdchecker --arkit`.
- `thumbnail.jpg` must contain decodable JPEG or PNG image data.
- `displayName` is user-facing text, not identity. Locus assigns an import UUID.

## One-seat Room v3 example

Every entity name below must resolve exactly once in the delivered USDZ. Change
the dimensions, normalized seat anchor, eye height, yaw, and entity names to
match the actual authored scene.

```json
{
  "formatVersion": 3,
  "displayName": "Glass Reading Pavilion",
  "caption": "A quiet one-seat pavilion with a warm pendant.",
  "previewCamera": {"yawDegrees": 0, "pitchDegrees": -8, "zoom": 0.8},
  "seatedOrigin": {
    "translationMeters": [0, 0, 0],
    "orientationXYZW": [0, 0, 0, 1]
  },
  "safeHeadVolume": {
    "centerMeters": [0, 1.2, 0],
    "sizeMeters": [1.2, 0.8, 1.2]
  },
  "viewOpenings": [{
    "id": "surroundings",
    "transform": {
      "translationMeters": [0, 1.4, -2],
      "orientationXYZW": [0, 0, 0, 1]
    },
    "widthMeters": 4,
    "heightMeters": 2.5
  }],
  "spatialAdaptation": {
    "wallEntities": ["Rear_Wall"],
    "roofEntities": ["Roof"],
    "deskEntitiesByTeleportID": {"seat.primary": "Table_Top"}
  },
  "lighting": {
    "luminaireGroups": [{
      "id": "reading-pendant",
      "displayName": "Reading Pendant",
      "entities": ["Pendant_Glow"],
      "authoredColor": {"mode": "temperature", "kelvin": 2700},
      "controls": {
        "brightnessEVRange": [-4, 1],
        "temperatureKelvinRange": [2000, 6500],
        "supportsFullColor": false
      },
      "proxy": {
        "type": "spot",
        "anchorEntity": "Pendant_Light_Anchor",
        "intensityLumens": 900,
        "attenuationRadiusMeters": 3.5,
        "colorTemperatureKelvin": 2700,
        "innerAngleDegrees": 30,
        "outerAngleDegrees": 70,
        "castsShadow": false
      }
    }],
    "bakedIndirect": {"entities": ["Locus_BakedIndirect"]}
  }
}
```

`teleport-points.json` for that seat:

```json
{
  "formatVersion": 1,
  "points": [{
    "id": "seat.primary",
    "title": "Reading Seat",
    "anchorXZ": [0.5, 0.55],
    "sourceFloorOffset": 0,
    "eyeHeight": 1.15,
    "yawRadians": 0
  }]
}
```

The opening transform describes the single View opening, not three physical
glass walls. Three glazed sides can still use one logical opening. `anchorXZ`
is normalized into the Room bounds and is not a world-space translation.

Calculate the seat only after the final USDZ export and any root transform or
axis conversion. In the delivered Room coordinate system:

```text
anchorX = (seatWorldX - boundsMinX) / (boundsMaxX - boundsMinX)
anchorZ = (seatWorldZ - boundsMinZ) / (boundsMaxZ - boundsMinZ)
```

Do not paste a DCC world-space Z value into the second normalized component.
Confirm both the resulting position and `yawRadians` by entering the Room; a
valid value can still place the visitor under a lamp or facing backward.

## Spatial adaptation

`wallEntities`, `roofEntities`, and `deskEntitiesByTeleportID` are optional as
a group. When `spatialAdaptation` exists, all three fields exist; empty arrays
or an empty desk map are allowed. The desk value names the tabletop subtree
itself. Do not map a parent containing legs, chairs, lamps, or props because
Locus derives the surface from recursive visual bounds.

World-sensing desk alignment, passthrough, Room Portal behavior, and physical
comfort require Apple Vision Pro. A simulator can verify that the Room imports,
loads, enters, and exposes non-world-sensing controls.

## Lighting layers

Room v1 omits `lighting`. Room v2 supports `luminaireGroups` with one optional
`proxy` per group. Room v3 adds `bakedIndirect` and permits either `proxy` or a
non-empty `proxies` array, never both.

- `entities`: one or more exported emissive fixture bodies controlled together.
- `nearTeleportIDs`: optional direct-proxy scope; it does not hide or darken
  the emissive fixture body.
- `authoredColor`: `temperature` plus `kelvin`, or `srgb` plus three components.
- `brightnessEVRange`: per-light control bounds within `[-4, 1]` for Room v3,
  not the range of the app's separate Overall Room brightness control.
- Direct proxies: at most 12 authored, 4 active at any seat, one shadow caster,
  10,000 lumens each, and attenuation radius no greater than 6 meters.
- Point proxies cannot cast shadows. Spot angles satisfy
  `0 < innerAngleDegrees <= outerAngleDegrees <= 175`.
- `bakedIndirect.entities`: positive-emissive opaque receiver subtrees only;
  exclude glass, water, transmissive surfaces, fixture glow, and local halos.

For producing the indirect textures and checking glass material fidelity,
follow [Lighting and glass](lighting-and-glass.md). Its export and appearance
checks complement these metadata limits; they do not add required ZIP files
or change the schema.

## Experimental Room v4 animations

Room animation playback is experimental. A Room v4 `space.json` may add a
non-empty `ambientAnimations` array. Every entry contains exactly:

```json
{
  "id": "coffee-break",
  "displayName": "Coffee Break",
  "entityName": "Ambient_CoffeeActor",
  "animationName": "default subtree animation",
  "isEnabledByDefault": true,
  "defaultSpeed": 1,
  "speedRange": [0.5, 1.5],
  "defaultIntervalRangeSeconds": [8, 20],
  "intervalRangeSeconds": [0, 60]
}
```

The ID is unique and stable. `entityName` and `animationName` must resolve the
intended clip in the exact delivered USDZ. Speed stays inside `0.25...2` and
the default sits inside `speedRange`. Interval endpoints are ordered values
from 0 through 3,600 seconds; the default range fits inside the adjustable
range. `[0, 0]` means immediate replay, matching nonzero values mean a fixed
pause, and different endpoints select a new random pause after every play.

Controls exposes one experimental switch per animation. Quick Settings exposes
experimental switch, speed, and interval values and can save them for that Room
on the current device. All of these animation fields and behaviors may change;
Room v1-v3 remains the stable authoring path.

## Provenance example

Use exactly one of `license` or `rights`. All URLs are HTTPS. If several
third-party components are embedded, list them in a durable notices page and
use its URL as `sourcePageURL`; summarize them in `modificationNotes`.

```json
{
  "formatVersion": 1,
  "creatorOrAgency": "Example Studio",
  "sourcePageURL": "https://example.com/room-notices",
  "license": {
    "identifier": "CC-BY-4.0",
    "name": "Creative Commons Attribution 4.0 International",
    "url": "https://creativecommons.org/licenses/by/4.0/"
  },
  "requestedCredit": "Room design by Example Studio",
  "modificationNotes": "Original geometry and arrangement. Embedded third-party components and their licenses are listed on the source page.",
  "aiGenerated": true,
  "aiProvider": "Name the material provider or providers"
}
```

`aiProvider` is required when `aiGenerated` is true and forbidden when it is
false. Name the generative AI provider, not Blender, Maya, a renderer, or an
export script. Provenance does not replace the underlying license terms, and a
rights URL must publish the statement it accompanies.

## Exact delivery gates

1. Inspect all declared seated eye points in the authoring tool, then recompute
   `anchorXZ` from the final delivered USDZ bounds.
2. Export a self-contained USDZ and run `usdchecker --arkit`.
3. Inspect the exported USD hierarchy and materials. Verify every metadata
   entity name, embedded texture, controlled fixture's positive emission, and
   transparent surface. A valid USDZ may still contain opaque glass or a dark
   lamp when an exporter changes material semantics.
4. Pack with the bundled packer and validate that exact ZIP.
5. Record its SHA-256.
6. Import that exact ZIP through Locus's public flow and enter the Room.
7. Capture and inspect visual evidence.
8. Run physical Vision Pro checks for world sensing, scale, reach, and comfort.
9. For experimental Room v4, exercise every animation switch, speed, continuous
   and nonzero interval state, motion comfort, and sustained performance.

### Authored rendering and spotlight direction (formatVersion 5)

Room v5 requires a Locus build that supports this format. Use the final exported
USDZ as the material reference: Locus preserves its supported PBR values and
texture/UV connections. Object names, mesh dimensions, and imported Room IDs do
not select material presets. A frosted panel remains frosted, even if its name
contains `glass`.

| Authored input | Supported behavior |
| --- | --- |
| Meshes, metric transforms, normals, UV sets | Loaded from the USDZ; visitor placement applies to the Room root. |
| USD Preview Surface base color, roughness, metallic, specular, normal, clearcoat, clearcoat roughness, opacity | Retained as exported, including supported connected textures. Export a Preview Surface network; bake procedural nodes to maps. |
| Emission | Retained. Declared lamp groups may scale emission and apply the visitor's color choice; color changes retain the emission map. Declared baked indirect receivers scale emission only. |
| Transparent surfaces | Opacity blending; this is not a promise of physical transmission, refraction, caustics, or order-independent layered glass. Inspect intersecting transparent surfaces in Locus. |
| Reflections | The selected View supplies distant environment lighting. This does not capture the Room interior or provide spatially exact mirrors. |
| Object animation | The embedded transform clips and optional experimental controls described below. Arbitrary material animation and procedural shader nodes require target-renderer validation and are not part of this contract. |

The optional `rendering` object contains both arrays, even when either is empty:

```json
"rendering": {
  "softenedReflectionEntities": ["Panel_927"],
  "uiFadeEntities": ["Furniture_412"]
}
```

Each entry names one unique exported entity and its descendants. Names are
case-sensitive, nonempty, at most 200 UTF-8 bytes, and unique within each array.
Do not name both an ancestor and its descendant within the same array. A
missing, ambiguous, overlapping, or geometry-free binding fails Room loading
with the affected entity name.

- `softenedReflectionEntities` opts those subtrees into an environment source
  that retains the View's vertical brightness distribution while averaging
  its horizontal detail. This can avoid recognizable distant landmarks in
  glazing; it has no horizontal reflection detail, is not a Room reflection,
  and never changes material roughness, coatings, or opacity.
- `uiFadeEntities` permits temporary fading when that subtree blocks the
  visitor's windows. Declare furniture deliberately and keep structure out
  unless fading that structure is intended. A fade multiplies existing entity
  opacity and restores it afterward. Keep animated opacity on a child of a
  static fade root so two controls do not write the same component.

Omitting `rendering` grants neither opt-in. An empty array also grants nothing.
Locus does not infer permission from names or a size threshold.

Every v5 `spot` proxy requires `direction`: a finite unit vector in the Room's
exported +Y-up coordinates. For example, `[0.6, -0.8, 0]` points down and toward
+X; `[0, -1, 0]` points straight down. The anchor supplies position only.
Rotating or scaling its mesh does not reinterpret this vector. Derive it from
the authored light's emission axis during export. `point` proxies must omit
`direction`. The existing lumens, radius, active-light, shadow, and adjustment
budgets continue to apply.

Rooms v1–v4 remain importable. A legacy spot without `direction` keeps its
specified downward default; use v5 to declare another direction. Legacy
packages receive no implicit rendering roles, and their material inputs are
preserved. If an older clear-glass asset exhibits the known colored center in
a sun highlight, correct the unused clearcoat roughness in its editable source
and re-export; Locus does not rewrite connected maps or apply a blanket patch
to imported materials. The tested uncoated-glass correction is clearcoat
roughness 0.2, with the intended base roughness and opacity retained. Intentional
coatings and animated inputs need separate evaluation.

`spatialAdaptation.wallEntities` and `roofEntities` are validated references;
they do not hide or cut the virtual architecture. Room Portal operates on the
visitor's tracked real-room surfaces. Only the explicit desk mapping connects
a virtual tabletop to desk alignment and desk passthrough.


### Inspect the delivered model before packaging

The flat ZIP validator checks metadata, archive structure, and USDZ validity.
The optional `audit_locus_room.py` tool also opens the delivered USD scene and
checks actual entity identities, overlapping rendering bindings, spotlight
directions, and the supported shader network. Run it with a Python environment
containing Pixar USD (`pxr`), such as Blender's bundled Python:

```sh
python3 audit_locus_room.py /path/to/room/space.json /path/to/room/scene.usdz
```

The audit reports the exact entity or shader path when a fix is needed. Bake
unsupported procedural nodes to Preview Surface texture inputs and bake
displacement into geometry. Material animation is outside this supported
author contract and requires separate target-renderer evaluation. Run the
public packer and validator afterward, then import the resulting ZIP and check
it in Locus; offline checks cannot establish glass compositing, visual quality,
tracking, or physical comfort.


For a reproducible independent v5 example, use the public
[`build_material_study.py`](https://github.com/EnterLocus/locus-support/blob/main/tools/build_material_study.py)
Blender builder. It includes contrasting glass, roughness/coat textures,
transparent water, a directed lamp, and furniture with explicit fade permission.
Its materials and names do not rely on any built-in Room behavior.
