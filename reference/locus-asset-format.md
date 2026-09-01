# Public Locus Room and View ZIP format

Status: v1 remains supported and immutable; v2 adds visitor-controlled Room
lighting metadata and a View condition that suggests the light switch's initial
position; Room v3 adds Room-owned baked indirect light and bounded authoring
limits. All versions use the same flat ZIP layout.

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
positive-emissive PBR materials. Locus treats it as one shared, low-frequency
indirect layer. It should represent broad opaque receivers, not glass, water,
transmissive materials, luminaire glow meshes, or recognizable
fixture-specific halos. Bounded proxies own local pools of direct light. The
Room owns the layer's baseline strength; the app owns the documented EV
multiplier.

The Room Lights master switch controls the indirect layer. Overall Room EV
scales it by `2^overallEV`; individual-light enable, EV, temperature, and color
do not recolor or double-count the shared bounce. This lets the overall control
simulate changing room response while direct lamp controls remain local.

For v3, every proxy is at most 10,000 lumens and every brightness range stays
inside `-4...+1 EV`. A Room may declare at most 12 proxies, at most 4 may be
active at any seat, and at most 1 may cast a shadow. These are hard safety
bounds, not recommended intensities. `bakedIndirect` and multiple
`proxies` are v3-only.

### How desk alignment identifies a desk

Locus does not inspect USDZ geometry and guess which object looks like a desk.
A Room identifies the virtual tabletop by mapping a teleport ID to the exact
exported entity name in `spatialAdaptation.deskEntitiesByTeleportID`. For the
example above, `seat.window` must also be an ID in `teleport-points.json`, and
`scene.usdz` must contain exactly one entity named `Window_Desk_Top`. A shared
table may be mapped from several seat IDs. An unmapped seat remains usable but
does not receive automatic desk alignment or desk passthrough.

Locus uses the mapped entity's recursive visual bounds to derive surface
height, footprint, and orientation. The mapped subtree therefore represents
the tabletop surface and must not include unrelated descendants that change
those bounds. Physical-desk matching and passthrough depend on world sensing
and are available only on Apple Vision Pro.

`scripts/validate_locus_asset.py` checks the mapping shape and USDZ structure;
it does not prove that an entity name resolves to the intended tabletop.
Therefore import the exact validated ZIP and enter every mapped seat. Package
loading can be checked elsewhere, but desk detection, alignment, passthrough,
scale, reach, and comfort require a physical Apple Vision Pro.

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
dimensions must match `view.json`. `thumbnail.jpg` is required.
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
tools used. The license describes rights in the asset. An App Store EULA is an
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
python3 scripts/pack_locus_asset.py /absolute/path/to/asset /absolute/path/to/asset.zip
python3 scripts/validate_locus_asset.py /absolute/path/to/asset.zip
```

The packer is deterministic, refuses to overwrite an existing ZIP, and only
publishes a ZIP accepted by the same validator. Room validation uses macOS
`sips` and Xcode's `usdchecker`. A `VALID` result covers structure, metadata,
image decoding, model structure, and machine-checkable limits. Import the
exact ZIP and enter every Room seat to check scale, appearance, and comfort.

Do not include editable sources, GLB, source textures, parent folders,
symlinks, extra metadata, or an authored asset ID.
