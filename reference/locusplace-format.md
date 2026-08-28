# Locus Place ZIP archive format v1

Status: Prototype v0 import and authoring contract.

A `.zip` or `.locusplace` file is one ordinary ZIP archive used by the current
**Import a Room** action. It must contain at least one Package-v2 Space (product
name: Room). It may also contain the Destination (View) and Experience that
pair with that Room. It is only a secure transport and integrity envelope. It
does not add a fourth content model, and the viewer never reads provider
responses or renderer assets directly.

The current product has exactly two author-facing import paths:

- **Import a View:** one complete 2:1 JPEG, PNG, or HEIC image from Photos,
  Files, or a direct public HTTPS URL. No archive or manifest is selected.
- **Import a Room:** one `.locusplace` or `.zip` archive from Files or a direct
  public HTTPS URL. At least one Room is required. A paired View and Experience
  may travel in the same archive.

Author one Room per archive; include its View and Experience when they form one
atomic bundle.

The two filename extensions are equivalent. `.locusplace` is the branded
extension and conforms to the public ZIP type; ordinary `.zip` is accepted so
authors can use standard archive tools. Validation is based on the archive
bytes and manifests, never the extension. Author instructions and an automatic
integrity-field packer are in the
[public author guide](../create-your-own-place/).

This document includes the authorable Package-v2 content fields. The
machine-readable transport schema is
[`locusplace-v1.schema.json`](../schemas/locusplace-v1.schema.json);
imported ownership metadata uses
[`locusplace-provenance-v1.schema.json`](../schemas/locusplace-provenance-v1.schema.json).

## Archive layout

```text
example.locusplace
├── locusplace.json
└── catalog/
    ├── spaces/<space-id>/              # at least one is required
    │   ├── space.json
    │   ├── provenance.json
    │   └── ...
    ├── destinations/<destination-id>/  # optional paired View
    │   ├── destination.json
    │   ├── provenance.json
    │   └── ...
    └── experiences/<experience-id>/    # optional pairing
        └── experience.json
```

Every non-directory member other than the root `locusplace.json` must be
declared in `files`. Every declared file must exist. The archive may contain
only the three known catalog collections, and every file must be inside a
package ID declared by `contents`. Package-v2 manifests remain
forward-compatible with unknown fields, but unknown envelope fields,
provenance fields, format versions, collections, and content modes fail closed.

A Room-only archive is accepted by **Import a Room**. A View-only archive is a
useful validator fixture but is rejected by that product action because it has
no Room. To make a Room and View appear as an explicit pair, include an
Experience that references content in the same archive or stable content
already present in the built-in/imported library.

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

All package asset paths are relative to the directory containing their
manifest, not to the ZIP root. Every reference resolves to a regular file
inside that package. Package-v2 manifests ignore unknown JSON fields for
forward compatibility; the outer envelope and provenance documents reject
unknown fields.

Coordinates are right-handed, meters, +Y up, and −Z forward. Quaternions are
`[x, y, z, w]`. A transform can contain `translationMeters` (three finite
numbers), `orientationXYZW` (four finite numbers with non-zero length), and
`scale` (three finite positive numbers).

### View: `destination.json`

```json
{
  "formatVersion": 2,
  "id": "destination.example-skybox",
  "title": "Example Skybox",
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
| `sourceImage` | no in Package v2; unsupported in public ZIP imports | Built-in catalogs may retain a package-relative JPEG/PNG audit image. Public authoring keeps every original outside the runtime ZIP, so the importer rejects this field. |
| `thumbnail` | no | Package-relative JPEG/PNG catalog image. |
| `caption` | no | Human-readable description. |
| `generation.generator` | no | Truthful generator or tool name. |
| `generation.model` | no | Optional model/workflow version. |
| `generation.generatedAt` | no | Optional timestamp; RFC 3339 UTC is recommended. |
| `depthLayers[]` | no in Package v2; unsupported in public ZIP imports | Reserved ordered depth assets. Public import rejects the field until a product runtime and byte-level validator consume its encoding. |
| `midground.path` | no in Package v2; unsupported in public ZIP imports | Reserved runtime midground asset. Public import rejects the field until its model type is product-supported and byte-validated. |
| `midground.transform` | no in Package v2; unsupported in public ZIP imports | Optional transform for the reserved midground contract. |
| `splat.variants`, `splat.ply` | no in Package v2; unsupported in public ZIP imports | Reserved future asset references. The splat backend has been removed, so public import rejects the entire field. |
| `splat.metricScaleFactor` | no in Package v2; unsupported in public ZIP imports | Positive finite scale in the reserved contract. |
| `splat.groundPlaneOffset` | no in Package v2; unsupported in public ZIP imports | Finite authored ground offset in the reserved contract. |
| `splat.placement` | no in Package v2; unsupported in public ZIP imports | Optional shared transform in the reserved contract. |
| `environment` | no | Optional image-based-lighting and sun defaults below. Omit entirely for a plain SDR View. |
| `audio.path` | no in Package v2; unsupported in public ZIP imports | Reserved runtime audio file. Public import rejects the field until complete audio byte validation and playback are product-supported. |
| `audio.loops` | with Package-v2 audio; unsupported in public ZIP imports | Boolean controlling repetition in the reserved contract. |
| `provenance` | yes for imports | Package-relative provenance JSON. |

The public ZIP profile deliberately accepts only fields the current product
actually consumes and validates completely. `sourceImage`, `depthLayers`,
`midground`, `splat`, and `audio` remain in the broader Package-v2 model for
built-in/future catalogs, but any non-null value makes a user-authored ZIP fail.
This prevents an original HDR, DCC source, or renamed arbitrary bytes from
becoming “valid” merely by pointing a type-blind metadata field at them.

**12,288×6,144 (12K) is recommended, not required.** Lower resolutions such
as 8,192×4,096, 6,144×3,072, or 4,096×2,048 are valid when strictly 2:1 and
declared with their real decoded dimensions. Do not upscale a smaller source
merely to claim 12K: it invents no detail and wastes memory.

Panorama coordinates are fixed: `u = 0.5` is yaw 0 and initial forward/world
−Z; `u` increases eastward toward +X; the seam is `u = 0/1`, yaw ±180°; and the
top image row is the zenith. `initialYawDegrees` rotates the image inside this
frame and does not redefine it.

Optional environment (lighting only — the visible sky is always the SDR
panorama):

```json
{
  "environment": {
    "imageBasedLight": "hdr/lighting-ibl.exr",
    "exposureEV": 0,
    "horizonPitchDegrees": 0,
    "directSun": {"enabled": false, "illuminanceLux": 0}
  }
}
```

| Field | Meaning |
|---|---|
| `imageBasedLight` | Optional scene-linear OpenEXR used only to light Room geometry. It must not be the SDR panorama. A 1024×512 diffuse IBL is recommended. |
| `exposureEV` | Finite EV gain applied only to IBL. |
| `horizonPitchDegrees` | Finite authored horizon correction. |
| `directSun.enabled` | Whether a separate directional light is authored. |
| `directSun.azimuthDegrees`, `elevationDegrees` | Finite direction angles; both required when enabled. |
| `directSun.illuminanceLux` | Finite non-negative illuminance. |

**Retired fields.** `visibleSkyHDR` and `hdrManifest` were part of an
earlier HDR-sky pipeline that has been removed from the product. The
validator now rejects any archive that declares either field, and
`skyGainEV` has no effect without a visible HDR sky. A previously valid
archive that used them must drop the fields (and the sky EXR) to import.

Public EXRs use a simple interchange subset: OpenEXR v2, single-part scanline layout, full-resolution half-float
`R`, `G`, and `B` channels with an optional half-float `A`, using uncompressed,
ZIPS, or ZIP scanline blocks. ZIP-compressed chunks are decompressed to their
declared full pixel byte count before ImageIO decode. Tiled, deep, multipart, subsampled,
integer-channel, float32-channel, or auxiliary-channel EXRs are rejected. The
chunk offset table, every scanline block, complete file extent, and ImageIO
decode are checked before installation.

A plain SDR View — the JPEG/PNG panorama with no `environment` at all — is
the normal case. The only EXR a View may carry is the optional
`imageBasedLight`; a tone-mapped SDR image renamed to `.exr` is not a
lighting asset and will fail EXR validation.

### Room: `space.json`

```json
{
  "formatVersion": 2,
  "id": "space.example-house",
  "title": "Example House",
  "scene": "scene.usdz",
  "thumbnail": "thumbnail.jpg",
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
| `seatedOrigin.translationMeters` | yes | Three finite meters locating the authored seated-floor reference. |
| `seatedOrigin.orientationXYZW` | yes | Four finite, non-zero-length quaternion components. |
| `safeHeadVolume.centerMeters` | yes | Three finite meters in Room coordinates. |
| `safeHeadVolume.sizeMeters` | yes | Three finite, strictly positive dimensions. |
| `destinationOpenings` | yes | Rectangular opening array; may be empty unless `virtual-space` references it. |
| `destinationOpenings[].id` | per entry | Unique package ID used by Experience composition. |
| `destinationOpenings[].transform` | per entry | Required position/quaternion pose. |
| `destinationOpenings[].widthMeters`, `heightMeters` | per entry | Finite, strictly positive dimensions. |
| `collision.mode` | yes | `embedded` or `separate`. |
| `collision.path` | conditional | Forbidden for `embedded`; for `separate`, a required package-relative self-contained USDZ validated with the same member, texture, and geometry rules as `scene`. Its geometry and scene geometry share the Room budget. Renamed authoring sources are not valid. |
| `quality.status` | yes | `unverified` or `verified`. |
| `quality.triangleCount`, `materialCount`, `entityCount`, `maxTextureDimension` | yes | Non-negative author measurements. Zero means unmeasured; actual USD is checked independently. |
| `teleportCatalog.path` | yes | Package-relative teleport JSON. Its 1 MiB JSON budget is enforced by field role even if the filename does not end in `.json`; case or Unicode filesystem aliases do not bypass it. |
| `teleportCatalog.houseID` | yes | ID selecting a non-empty `houses` array in that JSON. |
| `spatialAdaptation.wallEntities` | no | Unique non-empty USD entity names for walls; this metadata does not hide them. |
| `spatialAdaptation.roofEntities` | no | Unique non-empty names disjoint from walls. |
| `spatialAdaptation.deskEntitiesByTeleportID` | no | Map from declared teleport ID to non-empty authored desk entity name. |
| `provenance` | yes | Package-relative provenance JSON. |

The USDZ is meter-scale, right-handed, +Y up, and contains supported runtime
USD, texture, and audio members only. USDZ members must be stored, not
compressed. The validator loads/flattens the actual stage and counts geometry;
small or zero `quality` values cannot hide an oversized model.

Required teleport JSON:

```json
{
  "houses": {
    "example-house": [
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

The selected house must contain at least one teleport point. `anchorXZ` is two finite normalized values in `0...1`; `sourceFloorOffset` is
finite and non-negative in authored model units; `eyeHeight` is positive,
finite, and measured in meters; `yawRadians` is a finite model rotation about
+Y in the world frame. Point IDs are unique and titles non-empty.

### Experience: `experience.json`

```json
{
  "formatVersion": 2,
  "id": "experience.example-place",
  "title": "Example House · Example Skybox",
  "destinationID": "destination.example-skybox",
  "spaceID": "space.example-house",
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

Room-only ZIPs install reusable Room content. An Experience can explicitly
compose that Room with a View. References may resolve within the same archive
or against built-in/already-installed stable IDs; unresolved references fail
the whole import. A View-only ZIP can pass the format validator but is not a
supported product import; import that panorama directly as an image instead.

## Required provenance

Every imported Destination and Space points to a provenance JSON document.
It records the creator/agency, license identifier/name/HTTPS URL, requested
credit, modification notes, whether AI was used, and the AI provider when
applicable. Source/original asset URLs are optional but must be HTTPS without
credentials or fragments. Missing, oversized, malformed, or unknown
provenance fails the whole import. A future richer credits UI would not relax
this publication gate.

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
| `license.identifier` | yes | Non-empty identifier, at most 100 characters. Locus does not choose the asset's license. |
| `license.name` | yes | Non-empty name, at most 200 characters. |
| `license.url` | yes | Public HTTPS license URL. |
| `requestedCredit` | yes | Non-empty credit line, at most 1,000 characters. |
| `modificationNotes` | yes | Non-empty preparation notes, at most 2,000 characters. |
| `aiGenerated` | yes | Boolean. |
| `aiProvider` | conditional | Required and non-empty when `aiGenerated` is `true`; forbidden when false; at most 200 characters. |

The document is limited to 64 KiB. Do not copy a starter's provenance after
replacing its assets. The repository's license and the user's asset license are
separate declarations.

The ZIP is runtime delivery, not an authoring backup. Every payload file must
be reachable from a recognized Package-v2 asset field; unreferenced files are
rejected even when they appear in `locusplace.json.files`. `.blend`, `.blend1`,
`.blend2`, `.fbx`, `.obj`, `.mtl`, `.gltf`, and `.glb` files are rejected even
when declared. Keep those source files outside the ZIP. A Room ships the final
USDZ; a View ships the final 2:1 panorama and, at most, the optional
image-based-lighting EXR it actually uses.

## Security and resource budgets

Validation examines bytes, not extensions. It rejects traversal, absolute or
non-canonical paths, backslashes, control characters, case/Unicode collisions,
symlinks, duplicate entries, encrypted content, undeclared files, hash
mismatches, unsupported manifests, malformed images, invalid EXR
headers/channel layouts/chunk tables, malformed USDZ structure, compressed USDZ members, and
unsupported USDZ asset types. Room budgets are checked against the USD stage
that the system loader actually parses; the self-reported quality block is
authoring metadata and cannot reduce those counts.

The byte-level image allowlist is exact: imported panorama and `thumbnail`
raster fields are JPEG or PNG; `imageBasedLight` is OpenEXR; USDZ textures
may be JPEG, PNG, or OpenEXR. Public ZIPs reject the
reserved Package-v2 `sourceImage` field. Other ImageIO-decodable formats are
rejected rather than accepted implicitly. Outer-package 3D authoring formats
are also rejected. A USDZ may contain only USD/USDA/USDC, JPEG, PNG, OpenEXR,
M4A, WAV, and MP3 members.

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

The Places window's Import menu accepts a Files selection or an HTTPS URL.
Both sources become a private local archive and enter the same validator and
installer. URL imports reject credentials, fragments, localhost, `.local`,
and non-public DNS results. A hostname is resolved once per request, every
answer must be public, and the TLS socket connects to that exact numeric IP
while authenticating the original hostname. Every redirect repeats this
resolution-and-pinning step before a new connection, at most five redirects
are followed, and both declared and streamed download sizes are bounded.

Validation and catalog resolution finish in a private same-volume staging
directory. A library-wide advisory lock serializes inventory, quota checks,
and commit. First installs use exclusive atomic rename; updates use an atomic
directory swap. Any failure removes staging and leaves the installed package
untouched.

## Author validation and examples

Validate either filename without installing:

```sh
python3 tools/validate_locusplace.py MyPlace.locusplace
python3 tools/validate_locusplace.py MyPlace.zip
python3 tools/validate_locusplace.py --current-app-version 1.2.0 --json MyPlace.locusplace
```

The Python code uses the standard library, macOS ImageIO through `/usr/bin/sips`,
and the USD tools `usdchecker` and `usdcat` (installed with Xcode/Command Line
Tools). ImageIO performs a complete pixel decode after structural JPEG, PNG, or
EXR validation; the USD tools load, flatten, and measure the actual Room stage.
It exits nonzero on failure and performs archive, integrity, Package-v2,
provenance, image/EXR, and USDZ checks.
The visionOS importer remains authoritative for installation and cross-catalog
resolution.

Pack an editable directory into an ordinary ZIP, recomputing every integrity
record and refusing to publish unless this validator accepts the result:

```sh
python3 tools/pack_locusplace.py MyEditablePlace MyPlace.zip
```

Generate Room-only and combined product examples plus a View-only validator
fixture into a temporary or ignored directory, then validate them:

```sh
python3 examples/build_examples.py /tmp/locusplace-examples
for package in /tmp/locusplace-examples/*.locusplace; do
  python3 tools/validate_locusplace.py "$package"
done
```

The examples are generated rather than committed as binaries, matching the
repository rule that Git stores source and small metadata while binary assets
live outside Git. The builder source and expected layouts are documented in
[`examples/locusplace/README.md`](examples/locusplace/README.md).
