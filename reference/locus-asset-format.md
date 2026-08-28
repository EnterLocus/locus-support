# Public Locus Room and View ZIP format v1

A public archive contains exactly one Room or one View. It is an ordinary
`.zip` file with all files at the ZIP root. It does not contain an
author-chosen asset ID.

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
  "formatVersion": 1,
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

## Provenance

Every Room and View uses the same required `provenance.json` shape:

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

Do not include `.blend`, GLB, source textures, parent folders, symlinks, an ID,
or any file not listed in the Room or View layout.
