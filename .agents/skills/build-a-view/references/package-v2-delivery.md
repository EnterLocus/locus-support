# Package v2 delivery for Views

Package v2 (`.locusplace` / `.zip`) is the canonical feature-complete import
format for Locus 1.2.1 and later. See the public
[complete Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
and [field reference](https://enterlocus.com/reference/locus-asset-format/) for
every field and constraint.

## Archive layout and independent packaging

Deliver a View as a View-only archive with its own stable `packageID` (separate
from any companion Room archive, so either can be updated or removed
independently):

```text
my-view.locusplace
├── locusplace.json
└── catalog/
    └── destinations/
        └── destination.example-view/
            ├── destination.json
            ├── provenance.json
            ├── panorama.jpg
            ├── thumbnail.jpg
            └── lighting-ibl.jpg
```

- `locusplace.json` conforms to `schemas/locusplace-v1.schema.json`. Authors can
  omit `files` and `contentHash` while editing; `tools/pack_locusplace.py`
  computes both from disk bytes and validates the result.
- Set `minimumAppVersion` in `locusplace.json` to at least the highest version
  floor across every capability declared in `destination.json`.
- Keep stable `packageID` and `destination.<id>` across updates and increment
  `contentVersion` (`major.minor.patch`) whenever archive bytes change.

## Image roles and coordinate convention

- **Coordinate convention**: `2:1` equirectangular, `u = 0.5` is yaw `0`
  (initial forward `-Z`), increasing `u` points east (`+X`), and left/right
  edges meet at `±180°`.
- **Visible sky (`panorama.path`)**: `2:1` SDR JPEG or PNG (e.g. `8192×4096` or
  `12288×6144`). EXR / HDR panoramas are unsupported.
- **Catalog card (`thumbnail`)**: separate `16:9` rectilinear forward snapshot
  for Places cards. Never reuse an IBL or stretched `2:1` sphere.
- **Room IBL (`environment.imageBasedLight`)**: small `2:1` SDR map (e.g.
  `1024×512`) lighting Room geometry. Must be a separate file from
  `panorama.path`.
- **Environment tuning**: `skyGainEV`, `exposureEV`, `horizonPitchDegrees`,
  `colorGrade` (`contrast`, `saturation`), and optional `directSun`
  (`enabled`, `illuminanceLux`, `azimuthDegrees`, `elevationDegrees`).

## ASTC KTX1 GPU texture sidecars

Contract: `tools/gpu_texture_sidecar.py`. Requires macOS with Xcode's
`TextureConverter`.

- `gpuTexture` (`1.2.3+`): single object for `panorama.path` (`astc-6x6-srgb`
  `.ktx` with full mipmaps and `Repeat` horizontal wrap).
- `gpuTextures` (`1.3.0+`): array of sidecar objects (`source`, `path`, `format`,
  `width`, `height`, `mipmapLevels`, `sourceSHA256`). Required for
  `sunPath.panoramaBlend`, `celestial`, and `nearOrbit`. Never declare both
  `gpuTexture` and `gpuTextures`.
- Use `astc-6x6-srgb` for visible color images and `astc-6x6-linear` for linear
  data maps (`celestial.cloudTexture`, `nearOrbit` `cloudTexture` & `surface`
  tiles).

## Provenance and localized display text

- **`provenance.json`**: validate against `schemas/provenance-v1.schema.json`.
  Set `aiGenerated: true` and list generating providers in `aiProvider` when AI
  contributed pixels or assets. Optional `provenanceDetail` records
  component-level attribution (required for `sunPath`'s `sun-free-sky` entry).
- **`localizations`**: validated via `tools/content_localization.py`. Provide
  language-tagged entries (`en`, `zh-Hans`, `ja`, etc.) for `title`, `caption`,
  `libraryCaption`, `searchTerms`, `soundTitles`, and `mediaTitles`.

## Pack, validate, and test on Apple Vision Pro

```sh
python3 tools/pack_locusplace.py --current-app-version <target-version> \
  /path/to/MyEditableView /path/to/MyView.locusplace

python3 tools/validate_locusplace.py --current-app-version <target-version> \
  --json /path/to/MyView.locusplace
```

- Pass `--current-app-version` explicitly (it defaults conservatively to
  `1.0.0`).
- Legacy flat compatibility ZIPs (`view.json` via `tools/pack_locus_asset.py`
  and `tools/validate_locus_asset.py`) assign a new UUID on each import and
  cannot carry Package-v2-only blocks such as `midground`, `water`, `shore`,
  `clouds`, `sunPath`, `celestial`, `nearOrbit`, `blackHole`, or `gpuTextures`.
- Transfer the validated `.locusplace` archive to Apple Vision Pro (AirDrop or
  iCloud Drive), open **Places → Import → Import a View → Files**, pair with
  several Rooms, inspect seams, poles, **Edit View** sliders, **Animated View**
  off / **Reduce Motion**, and record what remains unverified until headset
  review.
