# Complete Locus Package v2 authoring

Status: canonical publication, storage, composition and feature-complete import
contract. Locus 1.2.1 and later accept this archive from Files or a public HTTPS
URL for both View and Room imports. The older flat format in
[`locus-asset-format.md`](locus-asset-format/) remains a compatibility input.

A `.zip` or `.locusplace` file is one ordinary ZIP archive containing one or more
Package-v2 Destinations (product name: Views), Spaces (Rooms), and Experiences.
It is the secure publication and integrity envelope used by Locus itself and by
feature-complete portable packages. The ZIP root contains `locusplace.json` and
`catalog/` directly; do not put both inside another parent directory.

Validation is based on archive bytes and manifests, never the filename
extension. A complete package preserves its `packageID`, content IDs,
`contentVersion` update stream and supported Experiences; importing the same
content hash is an idempotent no-op. The maintained packer and validator produce
and inspect this exact format.

This envelope carries pure data, not executable extensions. For one Locus
binary, every runtime-consumed Package-v2 capability has the same content
semantics whether the archive is bundled, downloaded from the Library or
imported from Files/URL. The origin may change entitlement, custom-import
allowance, update authority, storage, removal and UI labels, but never enables a
different Room/View schema or renderer feature. Scripts, plugins, dynamic
libraries and executable members are outside the format. All origins retain
the same path confinement, integrity, resource-budget, structural-decode,
reference-closure and minimum-version checks.

Use this guide for the complete envelope and baseline manifests. The
[field reference](locus-asset-format/) documents the optional View and Room
capabilities, their assets, ranges, and minimum app versions. The
[envelope schema](../schemas/locusplace-v1.schema.json) and
[provenance schema](../schemas/provenance-v1.schema.json) describe JSON shape;
the packer and validator also check file bytes and cross-field rules. A JSON
Schema alone cannot validate an archive or prove that it will feel comfortable
on Apple Vision Pro.

## Start with a working complete package

Clone or download [the public tools repository](https://github.com/EnterLocus/locus-support).
Run these commands from its root on macOS, with Python 3.9 or later and an Xcode installation that provides
`xcrun usdchecker` and `xcrun usdcat`. Basic validation uses the Python standard library,
`/usr/bin/sips` for full image decoding, and Xcode's `usdchecker` and `usdcat`
for models. Advanced cloud, water reflection/contact, and sun-free-sky checks
also need NumPy and Pillow: `python3 -m pip install numpy pillow`.

```sh
python3 examples/locusplace/build_examples.py /absolute/path/to/locusplace-examples
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /absolute/path/to/locusplace-examples/view-only.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /absolute/path/to/locusplace-examples/room-only.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /absolute/path/to/locusplace-examples/combined.locusplace
```

The target directory must be absent or empty. These tiny synthetic examples
exercise the format; the gradient and cube are not production-quality scenery
or a finished Room. Their source and generated content are Apache-2.0 licensed.
See [the example instructions](../examples/locusplace/README.md).

`--current-app-version` is the Locus version you are validating **for**; it does
not upgrade the installed app or grant support for a capability. The tools
conservatively default to `1.0.0`; pass the intended version explicitly. Complete
imports require Locus 1.2.1 or later, and newer fields require their own version
floor. The Room ground and midground controls require a supporting 1.4.4-or-later
build; this guide does not assert that such a build is currently on the App Store.

For your own package, unzip an example into an editable folder or create the
layout below. Replace its assets and provenance, use your own stable IDs, and
pack to an output **outside** that folder:

```sh
python3 tools/pack_locusplace.py --current-app-version 1.4.4 MyEditablePlace MyPlace.zip
python3 tools/validate_locusplace.py --current-app-version 1.4.4 --json MyPlace.zip
```

The packer recomputes `files` and `contentHash`, validates the archive, and only
then publishes it. It refuses to overwrite an existing output. It leaves the
editable source untouched. Import the result through **Places → Import → Import
a View** or **Import a Room → Files**, choosing an entrypoint whose content
kind is included. A combined package installs its contents together. A direct
public HTTPS ZIP URL works too. Check each authored seat, effect, light and
sound on Apple Vision Pro before sharing a finished place.

## Archive layout

```text
example.locusplace
├── locusplace.json
└── catalog/
    ├── destinations/<destination-id>/
    │   ├── destination.json
    │   ├── provenance.json
    │   └── ...
    ├── spaces/<space-id>/
    │   ├── space.json
    │   ├── provenance.json
    │   └── ...
    └── experiences/<experience-id>/
        └── experience.json
```

Every non-directory member other than the root `locusplace.json` must be
declared in `files`. Every declared file must exist. The archive may contain
only the three known catalog collections, and every file must be inside a
package ID declared by `contents`. Package-v2 manifests remain
forward-compatible with unknown fields, but unknown envelope fields, unsupported format versions, collections and content
modes fail closed. Provenance follows its published schema.

A View-only or Room-only archive installs reusable catalog content. Once the
catalog resolves, Locus derives its default pairings: each View with Your Room,
and each View with every Room that has a destination opening. An explicit
Experience replaces only its named pair and may refer to content in the same
archive or to a stable ID already present in the built-in/imported catalog.

## `locusplace.json`

```json
{
  "formatVersion": 1,
  "packageID": "place.example-combined",
  "contentVersion": "1.0.0",
  "minimumAppVersion": "1.0.0",
  "contents": {
    "destinationIDs": ["destination.example-view"],
    "spaceIDs": ["space.example-room"],
    "experienceIDs": ["experience.example-combined"]
  },
  "files": [
    {
      "path": "catalog/destinations/destination.example-view/destination.json",
      "byteCount": 214,
      "sha256": "<64 lowercase hex characters>"
    }
  ],
  "contentHash": "<64 lowercase hex characters>"
}
```

`packageID` and all content IDs are stable ASCII identifiers of at most 128
bytes. They begin with a letter or digit and then use only letters, digits,
`.`, `_`, and `-`.
Versions have exactly three numeric components. An update with changed bytes
must retain the same declared content IDs and use a greater `contentVersion`.
Importing the same `contentHash` is an idempotent no-op.

`contentHash` is SHA-256 over every file record sorted by Unicode path. Each
record contributes these UTF-8 bytes:

```text
path NUL decimal-byteCount NUL lowercase-sha256 NUL
```

This hash is independent of JSON whitespace and ZIP member ordering. The
validator also streams and verifies every declared file's actual byte count,
ZIP CRC, and SHA-256.

### Envelope field reference

| Field | Required | Meaning |
|---|---:|---|
| `formatVersion` | yes | Integer `1`; unknown envelope versions fail closed. |
| `packageID` | yes | Stable identity of this install/update stream; it is not a filename. |
| `contentVersion` | yes | Three numeric components such as `1.2.0`; increase when bytes change under the same IDs. |
| `minimumAppVersion` | yes | Oldest Locus version allowed to import the archive, also three numeric components. |
| `contents.destinationIDs` | yes | Unique View IDs owned by the ZIP; use `[]` when none. |
| `contents.spaceIDs` | yes | Unique Room IDs owned by the ZIP; use `[]` when none. |
| `contents.experienceIDs` | yes | Unique Experience IDs owned by the ZIP; use `[]` when none. |
| `files` | yes | Complete generated inventory of every payload file, excluding `locusplace.json`. |
| `files[].path` | yes | Canonical archive-relative `catalog/...` path. |
| `files[].byteCount` | yes | Exact expanded byte count. |
| `files[].sha256` | yes | SHA-256 of expanded bytes, 64 lowercase hexadecimal characters. |
| `contentHash` | yes | SHA-256 identity of the canonical payload inventory described above. |

## Package-v2 metadata inside the ZIP

The complete envelope uses `formatVersion: 1`; each `destination.json`,
`space.json` and `experience.json` uses `formatVersion: 2`. The Room v1–v10
numbers in the [flat compatibility reference](locus-asset-format/#flat-compatibility-room-zip)
belong to the separate flat `space.json` input. Do not change a complete
`space.json` to version 10 to use baked light layers. In complete packages,
optional capabilities are enabled by their typed fields and guarded by
`minimumAppVersion`.


All package asset paths are relative to the directory containing their
manifest, not to the ZIP root. Every reference resolves to a regular file
inside that package. Base Package-v2 manifests allow forward-compatible metadata; individual
capability profiles may use closed field sets. Do not rely on an unknown field
being rendered. The outer envelope rejects unknown fields, and provenance must
follow its published schema.

Coordinates are right-handed, meters, +Y up, and −Z forward. Quaternions are
`[x, y, z, w]`. A transform can contain `translationMeters` (three finite
numbers), `orientationXYZW` (four finite numbers with non-zero length), and
`scale` (three finite positive numbers).

### View: `destination.json`

```json
{
  "formatVersion": 2,
  "id": "destination.example-view",
  "title": "Example View",
  "panorama": {
    "path": "panorama.jpg",
    "projection": "equirectangular",
    "width": 8192,
    "height": 4096,
    "initialYawDegrees": 0
  },
  "provenance": "provenance.json"
}
```

| Field | Required | Meaning and validation |
|---|---:|---|
| `formatVersion` | yes | Integer `2`. |
| `id` | yes | Stable View ID; equals its directory and envelope ID. |
| `title` | yes | Non-empty user-visible View name. |
| `panorama.path` | yes | Package-relative final JPEG or PNG; decoded bytes, not extension alone, determine type. |
| `panorama.projection` | yes | Exactly `equirectangular`. |
| `panorama.width`, `height` | yes | Positive decoded dimensions, exactly declared, with `width == 2 * height`. |
| `panorama.initialYawDegrees` | no | Finite rotation within the canonical panorama frame; default `0`. |
| `sourceImage` | no | Optional package-relative JPEG/PNG audit image. It is not rendered, but complete packages may retain it as typed, decoded and budgeted data. Editable/DCC sources remain outside the runtime ZIP. |
| `thumbnail` | no | Package-relative JPEG/PNG catalog image. |
| `caption` | no | Human-readable description. |
| `generation.generator` | no | Truthful generator or tool name. |
| `generation.model` | no | Optional model/workflow version. |
| `generation.generatedAt` | no | Optional timestamp; RFC 3339 UTC is recommended. |
| `depthLayers[]` | no in Package v2; unsupported in public ZIP imports | Reserved ordered depth assets. Public import rejects the field until a product runtime and byte-level validator consume its encoding. |
| `midground.path` | no | Runtime midground USDZ rendered in both Experience Modes; it follows the same member allowlist, structure and resource budgets for bundled, Library and imported packages. See the [midground reference](locus-asset-format/#complete-view-source-and-midground-data-locus-121). |
| `midground.transform` | no | Optional finite transform for `midground.path`. |
| `midground.terrainEntities` | no | Unique non-empty names of ground units in `midground.path`; the runtime uses them to grade terrain beneath the Room footprint. |
| `midground.water` | no | App-rendered water declaration, including validated mask/normal-map and optional shore data described in the [field reference](locus-asset-format/). |
| `sky` | no | App-rendered procedural night sky (stars, Milky Way, optional aurora) shown through a validated 2:1 grayscale `sky.mask`; requires `minimumAppVersion >= 1.2.4`. See the [sky reference](locus-asset-format/#procedural-sky-celestial-bodies-and-near-orbit). |
| `gpuTexture`, `gpuTextures` | no | Validated ASTC KTX1 sidecars available to user ZIPs and Library packages alike. The v1 panorama sidecar requires `1.2.3`; the v2 source-image array requires `1.3.0`. Source hashes, dimensions and mip levels must match. |
| `water`, `clouds`, `fireflies` | no | Runtime water (including glow), painted-cloud motion and firefly declarations; require `minimumAppVersion >= 1.3.0`. Their referenced assets and resource budgets follow the common Package-v2 contract. |
| `environment.sunPath` | no | Authored sun-free sky and optional masked solar disc; requires `1.3.0` and its authoring attestation. |
| `celestial` | no | Animated celestial body and referenced textures; requires `1.2.4`, or the newer floor declared by its optional features (cloud-shell motion/evolution requires `1.3.0`). |
| `nearOrbit` | no | Near-orbit profiles, texture assets and content-bound fallback proof. v1 and v2 require `1.3.0`; v2 includes the tile manifest, tile images and their GPU sidecars. |
| `splat.variants`, `splat.ply` | no in Package v2; unsupported in public ZIP imports | Reserved future asset references. The splat backend has been removed, so public import rejects the entire field. |
| `splat.metricScaleFactor` | no in Package v2; unsupported in public ZIP imports | Positive finite scale in the reserved contract. |
| `splat.groundPlaneOffset` | no in Package v2; unsupported in public ZIP imports | Finite authored ground offset in the reserved contract. |
| `splat.placement` | no in Package v2; unsupported in public ZIP imports | Optional shared transform in the reserved contract. |
| `environment` | no | Visible-View brightness, optional small SDR Room lighting, and direct-sun defaults below. |
| `audio.path` | no in Package v2; unsupported in public ZIP imports | Reserved runtime audio file. Public import rejects the field until complete audio byte validation and playback are product-supported. |
| `audio.loops` | with Package-v2 audio; unsupported in public ZIP imports | Boolean controlling repetition in the reserved contract. |
| `provenance` | yes for imports | Package-relative provenance JSON. |

Complete ZIPs accept the fields this binary actually consumes, plus explicitly
retained metadata such as `sourceImage`, when their payload can be validated as
typed and budgeted data. `midground` is part of the common runtime contract and
requires `minimumAppVersion >= 1.2.1`.
`depthLayers`, `splat`, and the legacy `audio` block remain reserved or retired
without a current runtime consumer, so this binary rejects them regardless of
origin instead of accepting a type-blind path. When a later binary implements
one of those capabilities, it must add the field's asset references, type and
budget checks, runtime consumer and app-version floor to the common contract;
it must not add a separate public-import switch.

**12,288×6,144 (12K) is recommended, not required.** Lower resolutions such
as 8,192×4,096, 6,144×3,072, or 4,096×2,048 are valid when strictly 2:1 and
declared with their real decoded dimensions. Do not upscale a smaller source
merely to claim 12K: it invents no detail and wastes memory.

Panorama coordinates are fixed: `u = 0.5` is yaw 0 and initial forward/world
−Z; `u` increases eastward toward +X; the seam is `u = 0/1`, yaw ±180°; and the
top image row is the zenith. `initialYawDegrees` rotates the image inside this
frame and does not redefine it.

Optional View lighting:

```json
{
  "environment": {
    "imageBasedLight": "thumbnail.jpg",
    "skyGainEV": 0,
    "exposureEV": 0,
    "horizonPitchDegrees": 0,
    "colorGrade": {"contrast": 1.15, "saturation": 1.2},
    "directSun": {"enabled": false, "illuminanceLux": 5000}
  }
}
```

| Field | Meaning |
|---|---|
| `imageBasedLight` | Separate 2:1 JPEG/PNG used only to light Room geometry and reflections. It must not reuse `panorama.path`; 1024×512 is recommended and a neutral renderer fallback is used when omitted. |
| `skyGainEV` | Finite EV gain applied only to the visible panorama. |
| `exposureEV` | Finite EV gain applied only to IBL. |
| `horizonPitchDegrees` | Finite authored horizon correction. |
| `colorGrade.contrast` | Optional SDR visible-panorama contrast from `0.5` through `2.0`; `1.0` is neutral. |
| `colorGrade.saturation` | Optional SDR visible-panorama saturation from `0.0` through `2.0`; `1.0` is neutral. |
| `directSun.enabled` | Whether a separate directional light is authored. |
| `directSun.azimuthDegrees`, `elevationDegrees` | Finite direction angles; both required when enabled. |
| `directSun.illuminanceLux` | Finite non-negative illuminance. |

Color grading affects only the displayed SDR panorama. It reuses that texture
and does not turn the View into HDR or add highlight detail that is absent from
the source. A disabled sun can still carry `5000` lux so **Add Sunlight** starts
at the app default without changing the package's authored off state.

`visibleSkyHDR` and `hdrManifest` are retired and rejected. An outer-package
EXR cannot be used as the visible View or Room-lighting map. OpenEXR remains an
allowed USDZ texture format for Room assets and is validated inside the model.

### Room: `space.json`

```json
{
  "formatVersion": 2,
  "id": "space.example-room",
  "title": "Example Room",
  "scene": "scene.usdz",
  "thumbnail": "thumbnail.jpg",
  "caption": "A quiet house arranged around a sunlit courtyard.",
  "previewCamera": {
    "yawDegrees": -28,
    "pitchDegrees": -10,
    "zoom": 1.0
  },
  "seatedOrigin": {
    "translationMeters": [0, 0, 0],
    "orientationXYZW": [0, 0, 0, 1]
  },
  "safeHeadVolume": {
    "centerMeters": [0, 1.2, 0],
    "sizeMeters": [1.2, 0.6, 1.2]
  },
  "destinationOpenings": [
    {
      "id": "front",
      "transform": {
        "translationMeters": [0, 1.2, -2],
        "orientationXYZW": [0, 0, 0, 1]
      },
      "widthMeters": 4,
      "heightMeters": 2.5
    }
  ],
  "collision": {"mode": "embedded"},
  "teleportCatalog": {"path": "teleport-points.json", "houseID": "example-room"},
  "quality": {
    "status": "unverified",
    "triangleCount": 0,
    "materialCount": 0,
    "entityCount": 0,
    "maxTextureDimension": 0
  },
  "provenance": "provenance.json"
}
```

| Field | Required | Meaning and validation |
|---|---:|---|
| `formatVersion` | yes | Integer `2`. |
| `id` | yes | Stable Room ID; equals its directory and envelope ID. |
| `title` | yes | Non-empty user-visible Room name. |
| `scene` | yes | Package-relative self-contained USDZ. `.blend` and other authoring files are not substitutes and cannot be bundled elsewhere. |
| `thumbnail` | no | Package-relative decoded JPEG or PNG shown on the Room card. If declared it must exist, decode completely, and shares the archive image budgets; omit it to use the fallback glyph. |
| `caption` | no | Non-empty user-facing copy for **About This Room**, up to 2,000 UTF-8 bytes. |
| `previewCamera.yawDegrees`, `pitchDegrees` | no | Finite starting angles for the bounded 3D preview. They do not affect immersive placement. |
| `previewCamera.zoom` | with camera | Finite positive starting scale for the bounded 3D preview. Reset returns to this authored pose; the viewer clamps it to the supported interaction range. |
| `seatedOrigin.translationMeters` | yes | Three finite meters locating the authored seated-floor reference. |
| `seatedOrigin.orientationXYZW` | yes | Four finite normalized quaternion components; the seated frame must remain upright (no pitch or roll). |
| `safeHeadVolume.centerMeters` | yes | Three finite meters in Room coordinates. |
| `safeHeadVolume.sizeMeters` | yes | Three finite, strictly positive dimensions. |
| `destinationOpenings` | yes | Rectangular opening array. A standalone Room-only import needs exactly one; zero or multiple openings require an authored `virtual-space` Experience in the same archive. |
| `destinationOpenings[].id` | per entry | Unique package ID used by Experience composition. |
| `destinationOpenings[].transform` | per entry | Required position/quaternion pose. |
| `destinationOpenings[].widthMeters`, `heightMeters` | per entry | Finite, strictly positive dimensions. |
| `collision.mode` | yes | `embedded` or `separate`. |
| `collision.path` | conditional | Forbidden for `embedded`; for `separate`, a required package-relative self-contained USDZ validated with the same member, texture, and geometry rules as `scene`. Its geometry and scene geometry share the Room budget. Renamed authoring sources are not valid. |
| `quality.status` | yes | `unverified` or `verified`. |
| `quality.triangleCount`, `materialCount`, `entityCount`, `maxTextureDimension` | yes | Non-negative author measurements. Zero means unmeasured; actual USD is checked independently. |
| `teleportCatalog.path` | yes | Package-relative teleport JSON. Its selected house must contain at least one point; otherwise the Room cannot enter Virtual Space. Its 1 MiB JSON budget is enforced by field role even if the filename does not end in `.json`; case or Unicode filesystem aliases do not bypass it. |
| `teleportCatalog.houseID` | yes | ID selecting one non-empty `houses` array in that JSON. |
| `spatialAdaptation.wallEntities` | no | Unique non-empty USD entity names for walls; this metadata does not hide them. |
| `spatialAdaptation.roofEntities` | no | Unique non-empty names disjoint from walls. |
| `spatialAdaptation.deskEntitiesByTeleportID` | no | Map from declared teleport ID to non-empty authored desk entity name. |
| `provenance` | yes | Package-relative provenance JSON. |

The USDZ is meter-scale, right-handed, +Y up, and contains supported runtime
USD, texture, and audio members only. USDZ members must be stored, not
compressed. The validator loads/flattens the actual stage and counts geometry;
small or zero `quality` values cannot hide an oversized model.

Required teleport JSON (the selected house must contain at least one point):

```json
{
  "houses": {
    "example-room": [
      {
        "id": "work-desk",
        "title": "Work desk",
        "anchorXZ": [0.5, 0.5],
        "sourceFloorOffset": 0,
        "eyeHeight": 1.15,
        "yawRadians": 0
      }
    ]
  }
}
```

`anchorXZ` is two finite normalized values in `0...1`; `sourceFloorOffset` is
finite and non-negative in authored model units; `eyeHeight` is positive,
finite, and measured in meters; `yawRadians` is a finite model rotation about
+Y in the world frame. Point IDs are unique and titles non-empty.

### Experience: `experience.json`

```json
{
  "formatVersion": 2,
  "id": "experience.example-combined",
  "title": "Example Room · Example View",
  "destinationID": "destination.example-view",
  "spaceID": "space.example-room",
  "supportedModes": ["virtual-space"],
  "composition": {
    "destinationOpeningID": "front",
    "destinationYawDegrees": 0,
    "destinationPitchDegrees": 0,
    "destinationExposureOffsetEV": 0
  },
  "compatibility": {
    "minimumViewerVersion": "1.0.0",
    "requiredCapabilities": ["world-tracking"]
  }
}
```

| Field | Required | Meaning and validation |
|---|---:|---|
| `formatVersion` | yes | Integer `2`. |
| `id` | yes | Stable Experience ID. |
| `title` | yes | Non-empty user-visible tile name. |
| `destinationID` | yes | Stable View ID in this ZIP or already installed. |
| `spaceID` | conditional | Stable Room ID; required by `virtual-space`, normally omitted for `room-portal`. |
| `supportedModes` | yes | Non-empty unique array containing only `virtual-space` or `room-portal`. |
| `composition.destinationOpeningID` | conditional | Required for `virtual-space`; names an opening in the referenced Room. |
| `composition.destinationYawDegrees` | no | Finite sky alignment offset for this pair. |
| `composition.destinationPitchDegrees` | no | Finite sky pitch offset for this pair. |
| `composition.destinationExposureOffsetEV` | no | Finite relative exposure offset for this pair. |
| `compatibility.minimumViewerVersion` | no | Declarative minimum viewer version string. |
| `compatibility.requiredCapabilities` | no | Declarative capability strings. |

View-only and Room-only ZIPs install reusable content and join the default
composition matrix. An explicit Experience is necessary only to override one
pair's opening, orientation, exposure, title, mode, or compatibility. References
may resolve within the same archive or against built-in/already-installed stable
IDs; unresolved references fail the whole import.

## Optional capabilities and translated labels

Add optional fields to their owning View or Room manifest, and include every
referenced asset beside that manifest. The [field reference](locus-asset-format/)
covers media and masks, sound and Room music, midground and wind, water, sky,
clouds, sun path, celestial bodies, near orbit, black holes, point lights,
GPU texture sidecars, seats and groups, lights, animations, video surfaces,
particles and baked light layers. It also defines `localizations`,
`provenanceDetail`, and the Room's `viewGroundFloorOffsetMeters`,
`viewGroundKeepOut`, and `viewMidgroundVisibility` controls.

For example, these optional fields belong in an otherwise complete Room
manifest, and require envelope `minimumAppVersion: "1.4.4"` or later:

```json
{
  "viewGroundFloorOffsetMeters": 0.2,
  "viewGroundKeepOut": false,
  "viewMidgroundVisibility": "terrainOnly"
}
```

They keep their meaning for imported, bundled and Library content. Library
capability names in the field reference belong to Library offers; do not add a
made-up `requiredCapabilities` field to `locusplace.json`. The complete package
import path checks its minimum app version and the typed content itself.

## Required provenance

Every imported Destination and Space points to a provenance JSON document.
It records the creator/agency, exactly one of a license or an
all-rights-reserved statement, requested credit, modification notes, whether
AI was used, and the AI provider when applicable. Source/original asset URLs
are optional but must be HTTPS without credentials or fragments. Missing, oversized or malformed provenance fails the whole import. See the
[provenance reference](locus-asset-format/#provenance).

```json
{
  "formatVersion": 1,
  "creatorOrAgency": "Your name or studio",
  "sourcePageURL": "https://example.com/project",
  "originalAssetURL": "https://example.com/original",
  "license": {
    "identifier": "YOUR-LICENSE-ID",
    "name": "Your license name",
    "url": "https://example.com/license"
  },
  "requestedCredit": "Credit line requested by the creator",
  "modificationNotes": "Converted and packaged for Locus.",
  "aiGenerated": false
}
```

| Field | Required | Meaning and constraints |
|---|---:|---|
| `formatVersion` | yes | Integer `1`. |
| `creatorOrAgency` | yes | Non-empty creator/studio name, at most 200 characters. |
| `sourcePageURL` | no | Public HTTPS project page; no credentials or fragment. |
| `originalAssetURL` | no | Public HTTPS source page; records origin without embedding the original file. |
| `license.identifier` | conditional | Non-empty identifier, at most 100 characters; required with `license`. Locus does not choose the asset's license. |
| `license.name` | conditional | Non-empty name, at most 200 characters; required with `license`. |
| `license.url` | conditional | Public HTTPS license URL; required with `license`. |
| `rights.statement` | conditional | Non-empty rights statement, at most 1,000 characters; use with `rights.url` instead of `license`. |
| `rights.url` | conditional | Public HTTPS rights-statement URL; exactly one of `license` or `rights` is required. |
| `requestedCredit` | yes | Non-empty credit line, at most 1,000 characters. |
| `modificationNotes` | yes | Non-empty preparation notes, at most 2,000 characters. |
| `aiGenerated` | yes | Boolean. |
| `aiProvider` | conditional | Required and non-empty when `aiGenerated` is `true`; forbidden when false; at most 200 characters. |
| `importSource` | no | Reserved for a View Locus creates directly from an image: `photos`, `files`, or `url`. Third-party packages should omit it. |

The document is limited to 64 KiB. Do not copy a starter's provenance after
replacing its assets. The repository's license and the user's asset license are
separate declarations.

The ZIP is runtime delivery, not an authoring backup. Every payload file must
be reachable from a recognized Package-v2 asset field; unreferenced files are
rejected even when they appear in `locusplace.json.files`. `.blend`, `.blend1`,
`.blend2`, `.fbx`, `.obj`, `.mtl`, `.gltf`, and `.glb` files are rejected even
when declared. Keep those source files outside the ZIP. A Room ships the final
USDZ; a packaged View ships the final 2:1 panorama and, optionally, one small
2:1 JPEG/PNG Room-lighting image.

## Security and resource budgets

Validation examines bytes, not extensions. It rejects traversal, absolute or
non-canonical paths, backslashes, control characters, case/Unicode collisions,
symlinks, duplicate entries, encrypted content, undeclared files, hash
mismatches, unsupported manifests, malformed images, invalid EXR textures
inside USDZ, malformed USDZ structure, compressed USDZ members, and
unsupported USDZ asset types. Room budgets are checked against the USD stage
that the system loader actually parses; the self-reported quality block is
authoring metadata and cannot reduce those counts.

The byte-level image allowlist is exact: imported panorama, `sourceImage`,
`thumbnail`, and `imageBasedLight` raster fields are JPEG or PNG; USDZ textures
may be JPEG, PNG, or OpenEXR. Other ImageIO-decodable formats are rejected
rather than accepted implicitly. Outer-package 3D authoring formats are also
rejected. A USDZ may contain only USD/USDA/USDC, JPEG, PNG, OpenEXR, M4A, WAV,
and MP3 members.

| Budget | v1 limit |
|---|---:|
| Download or local archive | 1 GiB |
| ZIP entries | 4,096 |
| Root manifest | 1 MiB |
| Any payload file | 768 MiB |
| Total expanded payload | 2 GiB |
| Compression ratio | 200:1 |
| Any imported JSON file | 1 MiB |
| Provenance JSON | 64 KiB |
| Image dimension | 32,768 px |
| One image | 150 million pixels |
| All View images | 500 million pixels |
| USDZ entries | 4,096 |
| USDZ file / expanded bytes | 768 MiB / 1.5 GiB |
| USDZ texture dimension / total pixels | 16,384 px / 500 million |
| Loaded Room geometry | 5 million triangles, 1,024 materials, 100,000 entities |

## Files and URL acquisition

For a View, the Imports page accepts one JPG, PNG, or HEIC from Photos, Files,
or a direct public HTTPS URL. Locus normalizes an image to a Destination-only
Package v2 payload and passes the transient package through the same validator
and atomic installer. Files and URL also accept complete Package-v2 ZIPs for
Views and Rooms, including combined packages when they contain the content kind
selected by the visitor. Existing flat View/Room ZIPs remain accepted as
compatibility inputs. A malformed archive that contains `locusplace.json` is
rejected as an invalid complete package; it never falls back to the flat parser.
URL imports reject
credentials, fragments, localhost, `.local`, and non-public DNS results. A
hostname is resolved once per request, every
answer must be public, and the TLS socket connects to that exact numeric IP
while authenticating the original hostname. Every redirect repeats this
resolution-and-pinning step before a new connection, at most five redirects
are followed, and both declared and streamed download sizes are bounded.

Validation and catalog resolution finish in a private same-volume staging
directory. A library-wide advisory lock serializes inventory, quota checks,
and commit. First installs use exclusive atomic rename; updates use an atomic
directory swap. Any failure removes staging and leaves the installed package
untouched.

## Package validation and examples

The commands below maintain the complete Package-v2 envelope used by publication
and feature-complete imports. The legacy flat tools remain documented in
[`locus-asset-format.md`](locus-asset-format/).

Validate either filename without installing:

```sh
python3 tools/validate_locusplace.py --current-app-version 1.4.4 MyPlace.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.4.4 MyPlace.zip
python3 tools/validate_locusplace.py --current-app-version 1.4.4 --json MyPlace.locusplace
```

The Python code uses the standard library, macOS ImageIO through `/usr/bin/sips`,
and the USD tools `usdchecker` and `usdcat` (installed with Xcode/Command Line
Tools). ImageIO performs a complete pixel decode after structural JPEG or PNG
validation; EXR validation is limited to textures inside USDZ, and the USD
tools load, flatten, and measure the actual Room stage.
It exits nonzero on failure and performs archive, integrity, Package-v2,
provenance, image/EXR, and USDZ checks.
The visionOS importer remains authoritative for installation and cross-catalog
resolution.

Pack an editable directory into an ordinary ZIP, recomputing every integrity
record and refusing to publish unless this validator accepts the result:

```sh
python3 tools/pack_locusplace.py --current-app-version 1.4.4 MyEditablePlace MyPlace.zip
```

Generate real View-only, Room-only, and combined example archives into a
temporary or ignored directory, then validate them:

```sh
python3 examples/locusplace/build_examples.py /tmp/locusplace-examples
for package in /tmp/locusplace-examples/*.locusplace; do
  python3 tools/validate_locusplace.py --current-app-version 1.4.4 "$package"
done
```

The examples are generated from source without downloading private assets or
calling a paid service. The builder and expected layouts are documented in
[the example README](../examples/locusplace/README.md).
