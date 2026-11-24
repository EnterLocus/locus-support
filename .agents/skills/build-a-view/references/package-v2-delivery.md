# Package v2 delivery for Views

Package v2 (`.locusplace` / `.zip`) is the canonical feature-complete import
format for Locus 1.2.1 and later. See the offline specs in this repository
(`reference/locusplace-format.md` and `reference/locus-asset-format.md`), the
JSON Schemas (`schemas/locusplace-v1.schema.json`,
`schemas/provenance-v1.schema.json`), and `examples/locusplace/build_examples.py`,
or the published
[complete Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
and [field reference](https://enterlocus.com/reference/locus-asset-format/).

## Public CLIs vs Python contract modules

Most validator files under `tools/` are importable Python libraries with no
`__main__` CLI; `tools/validate_locusplace.py` invokes them automatically when
checking a `.locusplace` archive:

- **Command-line tools**: `tools/pack_locusplace.py`,
  `tools/validate_locusplace.py`, `tools/pack_locus_asset.py`,
  `tools/validate_locus_asset.py`, `tools/skybox/skybox.py`,
  `tools/skybox/seam_patch.py`, `tools/black_hole/compose_sky.py`,
  `tools/black_hole/outpaint_fal.py`, `tools/black_hole/bake_view.py`,
  `tools/black_hole/pack_view.py`, `tools/black_hole/validate_view.py`,
  `tools/sun_free_sky_check.py` (requires `numpy` + `PIL`),
  `tools/audit_coplanar_surfaces.py` (runs inside Blender with `--python`),
  `tools/place_examples.py`, and `tools/external_assets.py`.
- **Importable Python modules** (import with `sys.path.insert(0, "tools")`):
  `tools/gpu_texture_sidecar.py`, `tools/ktx1.py`, `tools/water_contract.py`,
  `tools/water_reflection_mask.py`, `tools/water_layered_reflection_mask.py`,
  `tools/water_contact_proxy.py`, `tools/shore_contract.py`,
  `tools/procedural_sky.py`, `tools/clouds_contract.py`,
  `tools/sun_path_contract.py`, `tools/panorama_media.py`,
  `tools/fireflies_contract.py`, `tools/point_lights.py`,
  `tools/package_sound.py`, `tools/celestial_view.py`,
  `tools/celestial_rings.py`, `tools/celestial_advection.py`,
  `tools/near_orbit_profile.py`, `tools/black_hole_view.py`, and
  `tools/content_localization.py`.

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
  for Places cards, cropped free of any UI overlays. Never reuse an IBL or
  stretched `2:1` sphere.
- **Room IBL (`environment.imageBasedLight`)**: small `2:1` SDR map (e.g.
  `1024×512`) lighting Room geometry. Must be a separate file from
  `panorama.path`.
- **Environment tuning**: `skyGainEV`, `exposureEV`, `horizonPitchDegrees`,
  `colorGrade` (`contrast`, `saturation`), optional `condition` (`"day"`,
  `"dusk"`, `"night"`, or `"overcast"` — suggests the Room Lights master switch's
  initial position when entering the View; `"dusk"`/`"night"` default on,
  `"day"`/`"overcast"`/omitted default off), and optional `directSun`
  (`enabled`, `illuminanceLux`, `azimuthDegrees`, `elevationDegrees`).

## ASTC KTX1 GPU texture sidecars

Contract: `tools/gpu_texture_sidecar.py` (Python library module; requires macOS
with Xcode's `TextureConverter`).

- `gpuTexture` (`1.2.3+`): single object for `panorama.path` (`astc-6x6-srgb`
  `.ktx` with full mipmaps and `Repeat` horizontal wrap).
- `gpuTextures` (`1.3.0+`): array of sidecar objects (`source`, `path`, `format`,
  `width`, `height`, `mipmapLevels`, `sourceSHA256`). Never declare both
  `gpuTexture` and `gpuTextures`.
  - **Mandatory**: both `panorama.path` and `sunPath.panoramaBlend.path` when
    `sunPath.panoramaBlend` is declared (`astc-6x6-srgb`, `Repeat`), plus every
    declared `nearOrbit` v2 `tiles` entry (`astc-6x6-srgb`, `Clamp`) and
    `surface` tile (`astc-6x6-linear`, `Clamp`).
  - **Optional / recommended**: standalone `panorama.path`, `celestial`
    (`backgroundPanorama`, `dayTexture`, `nightTexture` as `astc-6x6-srgb`;
    `cloudTexture` as `astc-6x6-linear`, `Repeat`), and `nearOrbit` v2 globals
    (`dayTexture`, `nightTexture`, `fallbackPanorama`, `galaxyTexture` as
    `astc-6x6-srgb`; `cloudTexture` as `astc-6x6-linear`, `Repeat`; `skyMask`
    never takes a sidecar).
- Generate `<stem>.ktx` files and the exact `destination.json` field via Python
  instead of hand-writing metadata:
  ```python
  import json, pathlib, sys

  sys.path.insert(0, "tools")
  from gpu_texture_sidecar import build_gpu_textures_field

  dest_dir = pathlib.Path("MyEditableView/catalog/destinations/destination.example-view")
  manifest = json.loads((dest_dir / "destination.json").read_text(encoding="utf-8"))
  manifest["gpuTextures"] = build_gpu_textures_field(
      destination_dir=dest_dir, manifest=manifest
  )
  (dest_dir / "destination.json").write_text(json.dumps(manifest, indent=2) + "\n")
  ```
  (For `1.2.3+` single-panorama `gpuTexture`, call
  `build_gpu_texture_field(panorama_jpg=..., output_ktx=..., panorama_width=..., panorama_height=...)`.)
- **Direct `TextureConverter` flag-order trap**: if you invoke Xcode's
  `TextureConverter` outside `tools/gpu_texture_sidecar.py`, every `--long_flag`
  (`--compression_format=ASTC6x6`, optional `--srgb_format`,
  `--file_format=KTX`, `--max_mipmaps=15`, `--wrap_mode=Repeat|Clamp`,
  `--output=<out.ktx>`) **must precede** the positional `<source_image>`
  argument; placing flags after the input makes `TextureConverter` fall back to a
  legacy parser and reject long options.

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
