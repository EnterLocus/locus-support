# Public Locus Room and View ZIP format

Status: v1 remains supported and immutable; v2 adds visitor-controlled Room
lighting metadata and a View condition that suggests the light switch's initial
position; Room v3 adds Room-owned baked indirect light and bounded authoring
limits; Room v4 adds independently controlled USDZ animations with saved
playback speed and randomized replay intervals; Room v5 adds explicit rendering
roles and spotlight directions. All versions use the same flat
ZIP layout.

A public archive contains exactly one Room or one View. It is an ordinary
`.zip` file with all files at the ZIP root. It never contains a Catalog,
Experience, package envelope, or author-chosen asset ID.

Locus assigns a new UUID when it imports an asset. `displayName` is
user-visible copy, may repeat, and is not an identity. Importing the same ZIP
twice creates two assets with different UUIDs and the same display name.

## Room ZIP

The five files are all required:

```text
room.zip
|-- space.json
|-- provenance.json
|-- teleport-points.json
|-- scene.usdz
`-- thumbnail.jpg
```

`space.json` contains the Room metadata. It does not name files or contain an
ID:

```json
{
  "formatVersion": 1,
  "displayName": "My Room",
  "caption": "A quiet two-seat room.",
  "previewCamera": {
    "yawDegrees": 0,
    "pitchDegrees": -8,
    "zoom": 0.8
  },
  "seatedOrigin": {
    "translationMeters": [0, 0, 0],
    "orientationXYZW": [0, 0, 0, 1]
  },
  "safeHeadVolume": {
    "centerMeters": [0, 1.25, 0],
    "sizeMeters": [1.2, 1, 1.2]
  },
  "viewOpenings": [
    {
      "id": "surroundings",
      "transform": {
        "translationMeters": [0, 1.25, -2],
        "orientationXYZW": [0, 0, 0, 1]
      },
      "widthMeters": 4,
      "heightMeters": 2.5
    }
  ],
  "spatialAdaptation": {
    "wallEntities": ["Rear_Wall"],
    "roofEntities": ["Roof"],
    "deskEntitiesByTeleportID": {
      "seat.window": "Window_Desk_Top"
    }
  }
}
```

`caption`, `previewCamera`, and `spatialAdaptation` are optional. Every Room
must have exactly one View opening and at least one teleport point. Coordinates
are right-handed meters with +Y up and -Z forward. Quaternions are
`[x, y, z, w]`. `anchorXZ` values are normalized into the Room bounds.

`teleport-points.json` has this shape:

```json
{
  "formatVersion": 1,
  "points": [
    {
      "id": "seat.window",
      "title": "Window Desk",
      "anchorXZ": [0.45, 0.55],
      "sourceFloorOffset": 0,
      "eyeHeight": 1.15,
      "yawRadians": 3.1415927
    }
  ]
}
```

`scene.usdz` is a self-contained, meter-scale, +Y-up USDZ. Its ZIP members are
stored without compression and it must pass `usdchecker --arkit`.
`thumbnail.jpg` is required and must decode as JPEG or PNG image data. Locus
does not capture a missing thumbnail during import.

### Room lighting (formatVersion 2)

A Room without lighting keeps `formatVersion: 1` and omits `lighting`; Locus
shows no light switch or Room lighting settings and builds no runtime rig. A
Room that declares lamps uses `formatVersion: 2` and adds:

```json
"lighting": {
  "luminaireGroups": [
    {
      "id": "desk-pendant",
      "displayName": "Desk Pendant",
      "entities": ["Desk_Pendant_Glow"],
      "nearTeleportIDs": ["seat.window"],
      "authoredColor": {"mode": "temperature", "kelvin": 2700},
      "controls": {
        "brightnessEVRange": [-4, 1],
        "temperatureKelvinRange": [2000, 6500],
        "supportsFullColor": false
      },
      "proxy": {
        "type": "spot",
        "anchorEntity": "Desk_Pendant_Anchor",
        "intensityLumens": 900,
        "attenuationRadiusMeters": 3.5,
        "colorTemperatureKelvin": 2700,
        "innerAngleDegrees": 30,
        "outerAngleDegrees": 65,
        "castsShadow": false
      }
    }
  ]
}
```

Each group is one independently controlled logical lamp/circuit. Keep `id`
stable across Room revisions; split separately controllable physical lamps into
separate groups. Every entity and anchor must resolve in the delivered USDZ.
`authoredColor` is either `temperature` plus `kelvin`, or `srgb` plus three
components. Full color and color temperature are per-light capabilities, never
Room-wide controls. New public Rooms do not author condition-to-intensity
tables.

`nearTeleportIDs` is optional. When present, it must be a non-empty unique list
of authored teleport IDs and only the group's bounded direct proxy is active at
those seats. An enabled fixture's emissive body remains visible from every
seat. Omitting the field makes the direct proxy available throughout the Room.

### Room indirect lighting (formatVersion 3)

A newly authored Room that simulates artificial diffuse bounce uses
`formatVersion: 3`. It keeps the v2 `luminaireGroups` and adds one or more
opaque receiver subtrees:

```json
"lighting": {
  "luminaireGroups": ["... v2 group objects ..."],
  "bakedIndirect": {
    "entities": ["Locus_BakedIndirect"]
  }
}
```

Format v3 may replace a group's legacy `proxy` object with a non-empty
`proxies` array when one logical switch drives multiple physical emitters. For
example, a paired dining pendant remains one control but authors one downward
spot per shade. Do not write both spellings in the same group.

Every named subtree must resolve exactly once in `scene.usdz` and contain
positive-emissive PBR materials. The subtree is an authored low-frequency
indirect layer: include broad opaque floors and walls;
exclude glass, water, luminaire glow meshes, and other transparent or
transmissive materials. Also exclude a ceiling, tabletop, or other receiver
when the combined atlas would paint a recognizable fixture-specific halo that
cannot follow that fixture's individual switch; bounded proxies own those local
pools. A dedicated second UV atlas is recommended so indirect
light does not replace the receivers' base PBR texture coordinates. The exact
delivered atlas must be denoised or deterministically low-pass filtered at its
final authored emission strength; visible fireflies or high-frequency speckle
are invalid for this deliberately low-frequency layer. Each Room owns that
baseline strength, while the app owns only the documented EV multiplier.

The Room Lights master switch controls the indirect layer. Overall Room EV uses
the app-owned `-4...+4 EV` range and scales it by `2^overallEV`;
individual-light enable, EV, temperature, and color do not recolor or
double-count the shared bounce. This lets the overall control simulate changing
room response while direct lamp controls remain local. Overall and per-light EV
are combined and clamped to `-4...+4 EV` before rendering.

For v3, every proxy is at most 10,000 lumens and every authored per-light
brightness range stays inside `-4...+1 EV`. These are hard package bounds, not
recommended intensities; functional indoor proxies normally begin around
700–1,500 lumens with a
2.5–3.5 m reach. Locus still accepts v2 archives using the older wider numeric
contract and safely normalizes them during import; locked v2 bytes are never
rewritten. `bakedIndirect` requires Room v3 or later.

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
visitor's tracked real walls, independently of this virtual geometry. The current
product can open multiple walls, but not the real ceiling. Only the explicit desk mapping connects
a virtual tabletop to desk alignment and desk passthrough.

### Ambient animations (formatVersion 4)

A Room whose USDZ contains independently playable environment animation uses
`formatVersion: 4` and adds a non-empty `ambientAnimations` array:

```json
"ambientAnimations": [
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
  },
  {
    "id": "ceiling-fan",
    "displayName": "Ceiling Fan",
    "entityName": "Ambient_CeilingFan",
    "animationName": "default subtree animation",
    "isEnabledByDefault": true,
    "defaultSpeed": 1,
    "speedRange": [0.25, 1.5],
    "defaultIntervalRangeSeconds": [0, 0],
    "intervalRangeSeconds": [0, 60]
  }
]
```

`entityName` resolves one subtree in `scene.usdz`; `animationName` resolves one
animation in that entity's animation library. Each ID is stable and unique.
Speed is a multiplier inside `0.25...2`. Interval is the pause after a complete
play: `[0, 0]` means replay immediately and therefore run continuously; any
other range samples a fresh random delay after every completion. Both interval
ranges are ordered seconds between 0 and 3,600, and the default endpoints must
fit inside the adjustable range.

Controls and Quick Settings operate on the same session values. Quick Settings
can save each animation's switch, speed, and interval as that Room's defaults
on the current device. Format v1-v3 Rooms cannot declare this field and keep
their existing behavior unchanged.

### How desk alignment identifies a desk

Locus does not inspect USDZ geometry and guess which object looks like a desk.
A Room author identifies the virtual tabletop explicitly by mapping a teleport
ID to the exact exported entity name in
`spatialAdaptation.deskEntitiesByTeleportID`. For the example above,
`seat.window` must also be the `id` of a point in `teleport-points.json`, and
`scene.usdz` must contain an entity named exactly `Window_Desk_Top`. A shared
table may be mapped from several seat IDs. If a seat has no mapping, it remains
usable as a teleport but receives no automatic desk alignment or desk
passthrough. There is currently no in-app surface picker that creates this
mapping after import.

Make the mapped entity the tabletop itself or a tightly bounded tabletop slab,
not the complete desk-and-chair hierarchy. Locus uses that entity's recursive
visual bounds in its own frame to derive the surface height, oriented width and
depth, and yaw. Keep legs, chairs, lamps, computers, plants, and loose props
outside the mapped entity's descendants; otherwise they can raise the measured
"top" or enlarge the footprint. Use a stable, unique semantic name such as
`Window_Desk_Top`, keep the surface level and non-degenerate, and verify the
meter-scale, +Y-up result in the exported USDZ. Blender may remain Z-up while
authoring, but the exported entity must have one vertical axis and two
horizontal axes without tilt or shear.

Calibrate the seat and table together. Put the chair at a clear near edge rather
than diagonally off a corner, face it toward the tabletop and intended view,
keep the nearest reach zone clear, and use a realistic tabletop height—about
0.72–0.76 m is a practical starting range. Do not rely on runtime correction to
repair a badly placed asset: Locus refuses horizontal Room movement over 0.75 m
or vertical movement over 0.35 m.

The visitor's real desk is a separate measurement. On a physical Vision Pro,
Locus requests world sensing and filters horizontal ARKit planes, rejecting
floors and windows and preferring nearby, table-sized surfaces in front of the
visitor. The current basic table candidate is 0.2–1.0 m below the tracked head,
within 2.5 m, at least 0.09 m², at least 0.35 m on its short side, and no more
than 5:1 in aspect ratio; an unclassified surface must satisfy stricter mesh,
area, shape, and reach checks. A final match also rejects a physical near edge
farther than 1.25 m. These are real-room filters, not a way to discover the
virtual tabletop inside `scene.usdz`.

After a successful measurement, Locus turns the Room about the visitor to match
desk-edge direction, moves it along that edge normal to match reach, and matches
the tabletop height. Desk passthrough remains the visitor's separate **Show
desk** choice. If no trustworthy plane is found, Locus may move the authored
edge within reach using a bounded fallback, but it does not claim alignment or
open passthrough.

`tools/validate_locus_asset.py` checks the mapping shape, USDZ structure, and actual RealityKit entity bindings;
it does not prove that an entity name resolves to the intended tabletop.
Therefore import the exact validated ZIP and enter every mapped seat. Simulator
can exercise package loading, but real-table detection, alignment, passthrough
edges, scale, reach, and comfort require the exact delivered build on a physical
Vision Pro.

## How Locus uses a Room

The authoring interface and the runtime rules are both documented here. Public
Room ZIPs are converted into Locus's internal Package v2 representation during
import. That conversion does not make internal fields secret or require a
creator to maintain two manifests. Author the five-file Room ZIP; Locus supplies
the internal identity, file paths, and bookkeeping.

| Author input | Runtime behavior and creator responsibility |
| --- | --- |
| `scene.usdz` | Locus loads the exported hierarchy, materials and transforms. Its actual visual bounds determine the coordinate frame for normalized seats. Author scale, clearances and appearance in the model. |
| `teleport-points.json` | Each point is a selectable seat, not a moving character. `anchorXZ` locates it within the delivered model bounds; `sourceFloorOffset` is the floor height above the model's minimum Y (including any foundation or floor-slab thickness), `eyeHeight` locates the eyes above it, and `yawRadians` sets its heading. Switching seats repositions the Room around the visitor. |
| `seatedOrigin` | Defines the authored floor frame used to carry the safety volume to the active seat. Use an upright frame: a finite normalized quaternion with no pitch or roll. It does not replace the seat catalog or specify a walkable spawn collider. |
| `safeHeadVolume` | Defines a box that follows the selected seat and its floor frame. Locus uses it with tracking and presence to decide when immersive content can be shown safely. Each half-extent has a runtime minimum of 1 m: an authored box smaller than 2 m on an axis cannot narrow that runtime range. This is not a wall collider or permission to put geometry close to the visitor's head. |
| `viewOpenings` | Exactly one logical opening connects a Room/View composition. It does not cut holes in the USDZ. Model the real architectural openings yourself. Virtual Space surrounds the Room with the View; this field does not determine which real walls Room Portal opens. |
| `spatialAdaptation.wallEntities` / `roofEntities` | Exact validated references to virtual architecture. They do not hide those meshes or create real-world portals. Room Portal uses detected real walls and supports opening multiple walls; the current product cannot open the real ceiling. |
| `deskEntitiesByTeleportID` | Names the tabletop used for that seat's alignment and optional desk passthrough. Without a mapping the seat still loads, but receives neither automatic desk alignment nor desk passthrough. See the desk-mapping contract in this reference. |
| `lighting` | Owns explicit emissive fixtures, optional bounded direct lights and optional shared indirect light. Controls do not discover lamps from names, and a material alone does not create a runtime point/spot light. |
| `rendering` | Explicitly opts subtrees into softened View reflections or temporary window-obstruction fading. Omitted roles grant neither behavior. These permissions do not change the underlying material design. |
| `ambientAnimations` | Binds embedded named clips to experimental switch/speed/interval controls. A valid entity name does not prove a clip exists or moves correctly; test playback in Locus. |
| `thumbnail.jpg` / `previewCamera` | Supply the library image and initial 3D preview framing. Neither determines the immersive seat. |

### Collision and quality: internal fields, not additional author inputs

The importer currently creates this internal metadata for every public Room:

```json
{
  "collision": {"mode": "embedded"},
  "quality": {
    "status": "unverified",
    "triangleCount": 0,
    "materialCount": 0,
    "entityCount": 0,
    "maxTextureDimension": 0
  }
}
```

These fields describe the internal package, not extra JSON to paste into the
public `space.json`. Both the app importer and public validator reject them in
that public file. Adding them only to the public validator would produce ZIPs
that the app rejects.

The internal schema also has a `separate` collision mode with a USDZ path. The
current Virtual Space loader does not use either mode to build a walking,
physics, or visitor-body collision system. A declared collision mesh does not
prevent someone moving through virtual furniture. Runtime head safety and real
desk measurement are separate systems. No separate collision file is accepted
in a public Room ZIP.

`quality` is bookkeeping, not a quality certificate. Import sets it to
`unverified` with zero declared counts, then inspects the actual USDZ composition
and mesh topology against the limits below. Supplying smaller numbers cannot
bypass that inspection. The public validator performs actual model and texture
budget checks too; it does not require a creator to estimate those values.
Keep measured authoring statistics with the editable source when useful.

### Model and texture budgets

| Resource | Maximum |
| --- | ---: |
| Room ZIP | 1 GiB |
| One extracted file, including `scene.usdz` | 768 MiB |
| All extracted ZIP files | 2 GiB |
| Entries inside the USDZ | 4,096 |
| Expanded USDZ members | 1.5 GiB |
| Actual model triangles | 5,000,000 |
| Actual model materials | 1,024 |
| Actual model entities | 100,000 |
| One model texture dimension | 16,384 pixels |
| One image's decoded pixels | 150,000,000 |
| All embedded model texture pixels | 500,000,000 |

ModelIO inspects the loaded composition rather than trusting JSON counts.
Instance compositions are rejected by the current import budget policy; realize
instances before export. These are rejection limits, not performance targets.
A small Room should stay far below them. Appearance, interactive frame rate,
tracking, reach and comfort still require checking the exact Room in Locus.

## View ZIP

Four root files are required and one is optional:

```text
view.zip
|-- view.json
|-- provenance.json
|-- panorama.jpg
|-- thumbnail.jpg
`-- lighting.jpg       optional
```

`panorama.jpg` is a complete 2:1 equirectangular JPEG or PNG. Its decoded
dimensions must match `view.json`. The 4K minimum for direct image imports
(including Browser images) is not a View ZIP format restriction. `thumbnail.jpg` is required.
`lighting.jpg`, when present, is a separate small 2:1 SDR image used for Room
lighting and reflections.

```json
{
  "formatVersion": 2,
  "displayName": "My View",
  "caption": "A complete panoramic View.",
  "panorama": {
    "projection": "equirectangular",
    "width": 12288,
    "height": 6144,
    "initialYawDegrees": 0
  },
  "environment": {
    "skyGainEV": 0.5,
    "exposureEV": 0,
    "horizonPitchDegrees": 0,
    "condition": "night",
    "colorGrade": {
      "contrast": 1.1,
      "saturation": 1.2
    },
    "directSun": {
      "enabled": false,
      "illuminanceLux": 5000
    }
  }
}
```

`caption` and `environment` are optional. `initialYawDegrees` is optional.
`contrast` accepts `0.5...2`; `saturation` accepts `0...2`. An enabled sun also
requires finite `azimuthDegrees` and `elevationDegrees`. These are starting
values; a user may later change them with Edit View in Locus.

`environment.condition` is available in `formatVersion: 2`: `dusk` and `night`
initially turn a composed Room's lights on; `day`, `overcast`, and an omitted
condition initially leave them off. It never maps to a Room brightness. The
visitor can override the switch, and a lamp that is on uses its Room-authored
intensity plus saved Room EV offsets.

## Provenance

Every Room and View uses the same required `provenance.json` shape. Third-party
content declares `license`; Locus-owned content that grants no reuse license
declares `rights` instead. Exactly one is required:

```json
{
  "formatVersion": 1,
  "creatorOrAgency": "Example Studio",
  "sourcePageURL": "https://example.com/source",
  "originalAssetURL": "https://example.com/asset",
  "license": {
    "identifier": "CC0-1.0",
    "name": "CC0 1.0 Universal",
    "url": "https://creativecommons.org/publicdomain/zero/1.0/"
  },
  "requestedCredit": "Example Studio",
  "modificationNotes": "Prepared as a Locus Room.",
  "aiGenerated": false
}
```

`sourcePageURL` and `originalAssetURL` are optional HTTPS URLs. When
`aiGenerated` is `true`, `aiProvider` is required and names the provider or
tools used. When `aiGenerated` is `false`, omit `aiProvider`; supplying it is
invalid. The license describes rights in the asset. An App Store EULA is an
app distribution agreement and is not an asset provenance license.

For an all-rights-reserved original, replace `license` with:

```json
"rights": {
  "statement": "All rights reserved. No separate reuse license is granted.",
  "url": "https://enterlocus.com/asset-rights/"
}
```

## Pack and validate

Keep only regular root files in the source directory, then run:

```sh
python3 tools/pack_locus_asset.py /absolute/path/to/asset /absolute/path/to/asset.zip
python3 tools/validate_locus_asset.py /absolute/path/to/asset.zip
```

The packer is deterministic, refuses to overwrite an existing ZIP, and only
publishes a ZIP accepted by the same validator. Room validation uses macOS
`sips`, Xcode's `usdchecker`, and a small Swift RealityKit checker compiled with
`xcrun swiftc`. The downloadable Python validator includes its Swift checker; it requires no
private repository or separately downloaded helper. The same binding rules
are used by the app before import. A `VALID` result covers structure, metadata,
image decoding, model structure, and machine-checkable entity bindings. Import the
exact ZIP and enter every Room seat to check scale, appearance, and comfort.

Do not include `.blend`, GLB, source textures, parent folders, symlinks,
Catalog files, Experience files, an ID, or an internal package envelope.

### Inspect the delivered model before packaging

The flat ZIP validator and the app's public Room import preflight both load
models with authored name references through RealityKit. References in spatial
adaptation, rendering, lighting (including proxy anchors and baked indirect),
and ambient animations must resolve to exactly one entity. Rendering groups
also reject overlapping ancestor/descendant bindings and subtrees without
renderable geometry, matching runtime rules. A Blender object and its mesh
must not share a referenced name: use a distinct mesh name such as
`Table_Cup_Geometry`. Unreferenced duplicate names are allowed.

Import rejects these failures before committing a library entry or consuming
an import allowance. Transport, schema and resource-budget validation precede
the native load. This is binding validation, not a substitute for light-material,
animation-playback or physical-device visual acceptance.
The optional `audit_locus_room.py` tool also opens the delivered USD scene and
checks actual entity identities, overlapping rendering bindings, spotlight
directions, and the supported shader network. Run it with a Python environment
containing Pixar USD (`pxr`), such as Blender's bundled Python:

```sh
python3 tools/audit_locus_room.py /path/to/room/space.json /path/to/room/scene.usdz
```

The audit reports the exact entity or shader path when a fix is needed. Bake
unsupported procedural nodes to Preview Surface texture inputs and bake
displacement into geometry. Material animation is outside this supported
author contract and requires separate target-renderer evaluation. Run the
public packer and validator afterward, then import the resulting ZIP and check
it in Locus; offline checks cannot establish glass compositing, visual quality,
tracking, or physical comfort.


### Build an independent material example

`tools/build_material_study.py` creates an editable Blender Room with matte and
textured glossy floors, three glass finishes, a transparent water surface,
roughness and coat maps, a wall-facing spotlight, and explicitly declared
furniture. It uses arbitrary object names and receives a fresh identity on
normal import. It requires a Locus build supporting Room v5.

```sh
blender --background --factory-startup --python-exit-code 1 --python tools/build_material_study.py -- --output /path/to/material-study
python3 tools/audit_locus_room.py /path/to/material-study/room/space.json /path/to/material-study/room/scene.usdz
python3 tools/pack_locus_asset.py /path/to/material-study/room /path/to/material-study.zip
```

Use a Python environment with Pixar USD for the audit. Keep `MaterialStudy.blend`
and the generated textures with the editable source; import only the flat ZIP.
