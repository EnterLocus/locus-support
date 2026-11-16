# Space, orbital, and black-hole Views

Covers the three space/orbital profiles: `blackHole` (`1.3.4+`), `celestial`
(`1.2.4+` / v2 `1.2.5+`), and `nearOrbit` (`1.3.0+` / v2 `1.3.2+`). See also
[Make your own black hole View](https://enterlocus.com/make-a-black-hole-view/)
and the [field reference](https://enterlocus.com/reference/locus-asset-format/).

- **Turnkey baker vs author-rendered fallbacks**: `blackHole` includes an
  end-to-end raytracing baker CLI (`tools/black_hole/bake_view.py`). For
  `celestial` and `nearOrbit`, `EnterLocus/locus-support` ships the complete
  JSON Schemas and Python contract/proof modules, while the author renders the
  matching `t = 0` `panorama.path` / `fallbackPanorama` (and any `nearOrbit`
  tiles) from their own renderer or 3D scene.

## Mutual exclusion rules

- `blackHole` and `nearOrbit` exclude `celestial`, `sky`, `media`, `midground`,
  `water`, `shore`, `fireflies`, `clouds`, `pointLights`, and
  `environment.sunPath`.
- `celestial` excludes `media`, `midground`, `fireflies`, `shore`, and
  `environment.sunPath`; if root `sky` is included (`minimumAppVersion >= "1.3.0"`),
  `sky` must declare `stars` and omit `aurora` and `moon`.

---

## 1. Black hole (`blackHole`, App 1.3.4+)

Contract: `tools/black_hole_view.py` and `schemas/view-black-hole-v1.schema.json`.
Public CLI pipeline under `tools/black_hole/`:

1. Compose an unlensed starry sky with `tools/black_hole/compose_sky.py` (using
   licensed nebula photos; optional paid edge outpainting via
   `tools/black_hole/outpaint_fal.py` with `FAL_KEY` requires creator approval
   and AI disclosure in `provenance.json`).
2. Copy and edit `tools/black_hole/recipes/ring.view.json` with your own
   `destinationID`, provenance, and `blackHole` parameters (`observerRadius`
   `8..200`, `disc`, `doppler`, `glow`, `drift`, optional `flares`).
3. Bake assets and preview frames/stills with `tools/black_hole/bake_view.py`:
   ```sh
   python3 tools/black_hole/bake_view.py my-ring.view.json --sky sky.png --out my-ring --stills 0,5,10
   ```
4. Pack and validate:
   ```sh
   python3 tools/black_hole/pack_view.py my-ring my-ring.locusplace
   python3 tools/black_hole/validate_view.py my-ring.locusplace
   ```
- Keep `drift.degreesPerSecond` gentle (e.g. `0.3 °/s`) to minimize vection on
  Apple Vision Pro, and inspect `panorama.jpg` (`t = 0`) for Motion-off state.
- **Worked example**: `destination.black-hole-ring`.

---

## 2. Far-field celestial body (`celestial`, App 1.2.4+ / v2 1.2.5+)

Contract: `tools/celestial_view.py` and `schemas/view-celestial-v1.schema.json`
/ `schemas/view-celestial-v2.schema.json`.

- **Versions**:
  - `version: 1` (`1.2.4+`): fixed `700 m` convention (`angularDiameterDegrees`).
  - `version: 2` (`1.2.5+`): explicit `distanceMeters` (`400..800`) +
    `radiusMeters` (`1..400`) or `angularDiameterDegrees`, satisfying
    `radius <= distance * 0.5` and `distance + radius <= 1100`.
- **Add-on floors**:
  - Cloud shell (`cloudHeightRatio`, `cloudDriftRatio`, `cloudShadowStrength`,
    `cloudEvolution`, `cloudEvolutionPeriodSeconds`), `sunDisc`, or shared `sky`:
    `minimumAppVersion >= "1.3.0"`.
  - Gas-giant `advection` (`tools/celestial_advection.py`): `>= "1.3.2"`.
  - Oblate `polarRadiusRatio` (`0.85..1`) & planetary `rings`
    (`tools/celestial_rings.py`): `>= "1.3.4"`.
- **Planetary `rings` contract & 1-px profile PNG (`1.3.4+`)**:
  - Declaration: `{"version": 1, "profileTexture": "rings.png", "innerRadiusRatio": 1.25, "outerRadiusRatio": 2.35, "brightness": 1.0, "unlitBrightness": 1.0}`
    (`1.05 <= inner`, `inner + 0.05 <= outer <= 4`, `brightness` `0..4`,
    `unlitBrightness` `0..2`).
  - Outer extent `R = outerRadiusRatio * radiusMeters` must satisfy
    `distanceMeters - R >= 200` and `distanceMeters + R <= 1100`. Excludes
    `nightTexture`, `cloudTexture`, cloud-shell fields, and `advection`.
  - `profileTexture` binary format: **8-bit RGBA PNG (`bit_depth = 8`,
    `color_type = 6`), exactly `1` pixel tall (`height == 1`) and `64..8192`
    pixels wide** (left column `0` = `innerRadiusRatio`, right column
    `width - 1` = `outerRadiusRatio`; RGB is sRGB color; straight alpha `< 1.0`
    encodes normal-incidence opacity `optical_depth = -ln(1 - min(alpha, 0.999))`).
    Does **not** use a `gpuTextures` sidecar.
- **Atmospheric `advection` flipbook PNG (`1.3.2+`)**:
  - Declaration: `{"version": 1, "flowTexture": "flow.png", "ageKeyframes": K, "maxAgeRotations": ..., "displacementRangeDegrees": D, "regenerationRotations": R, "crossfade": C}`
    (`K` int `2..16`, `D` `1..90`, `R` `0.1..4`, `C` `0.05..0.45`, and
    `maxAgeRotations >= (0.5 + C) * R`). Excludes `nightTexture`, `cloudTexture`,
    and cloud-shell fields.
  - `flowTexture` binary format: non-interlaced **big-endian (`>H`) 16-bit RGB
    PNG (`bit_depth = 16`, `color_type = 2`)** with even `width` (`64..1024`)
    and `height == (K + 1) * (width // 2)` stacking `K + 1` equirectangular
    `2:1` tiles vertically from age `0` (top tile `k = 0`) to `maxAgeRotations`
    (bottom tile `k = K`):
    ```python
    u16_dx = max(0, min(65535, round(32768 + 32767 * (dx_degrees / D))))  # R channel
    u16_dy = max(0, min(65535, round(32768 + 32767 * (dy_degrees / D))))  # G channel
    # Tile 0 B channel stores regeneration phase jitter 0..65535 (0 in tiles 1..K).
    ```
    Does **not** use a `gpuTextures` sidecar.
- **Sidecars**: optional/recommended `gpuTextures` v2 (`1.3.0+`) for
  `backgroundPanorama`, `dayTexture`, `nightTexture`, and `cloudTexture`
  (`astc-6x6-linear` for `cloudTexture`, `astc-6x6-srgb` for the others).
- `oceanGlint` is retired and rejected by public validation; never include it.
- **Worked example**: `destination.earth-from-space`.

---

## 3. Near-orbit profile (`nearOrbit`, App 1.3.0+ / v2 1.3.2+)

Contract: `tools/near_orbit_profile.py` and
`schemas/view-near-orbit-v1.schema.json` /
`schemas/view-near-orbit-v2.schema.json`.

- `version: 1` (`1.3.0+`): regional texture patch + globals (`dayTexture`,
  `nightTexture`, `cloudTexture`, `regionTexture` `1024×1024`, `regionMask`,
  `fallbackPanorama`, `skyMask`, `galaxyTexture`, `starCatalog`).
- `version: 2` (`1.3.2+`): configurable `bodyRadiusKilometers` (`1000..100000`),
  `cloudDriftRatio` (`0.5..2`), optional equirectangular `tiles` grid (up to
  `1024` square tiles), and optional per-tile `surface` slope/water-cover grid:
  - `starCatalog` must be a `locus-star-catalog` v1 JSON (`<= 1 MiB`) using
    `"frame": "horizontal"`.
  - **`tiles` (`tiles.json`)**: `tiles` object in `destination.json` declares
    `{"manifest": "tiles.json", "columns": C, "rows": R, "latitudeSouthDegrees": S, "tileSize": N}`
    (`360 % C == 0`, `R * C <= 1024`, `S + R * (360 / C) <= 90`, `N` `16..4096`;
    row `0` is northernmost, column `0` starts at `-180°`). `tiles.json` holds
    `{"formatVersion": 1, "columns": C, "rows": R, "tileSize": N, "latitudeSouthDegrees": S, "tiles": [...]}`
    with entries `{"row": r, "column": c, "path": "...", "sha256": "...", "byteCount": ...}`
    covering all `R * C` tiles sorted by `(row, column)`. Every tile requires an
    `astc-6x6-srgb` `Clamp` KTX1 entry in `gpuTextures`.
  - **`surface` (`surface.json`, `1.3.2+`)**: declares
    `{"manifest": "surface.json", "tileSize": N}`. `surface.json` adds
    `"encoding": "slope-east-north-water-v1"`, references lossless `8-bit` RGB
    `.png` tiles sorted by `(row, column)`, and requires an `astc-6x6-linear`
    `Clamp` KTX1 entry in `gpuTextures` for every tile.
- **Mandatory content-bound fallback proof (`<fallbackPanorama stem>.proof.json`)**:
  `fallbackPanorama` must equal root `panorama.path`, and `<stem>.proof.json`
  (`<= 16 KiB`) must match `tools/near_orbit_profile.py` byte-for-byte after any
  manifest or texture change:
  ```python
  import hashlib, json, pathlib, sys

  sys.path.insert(0, "tools")
  from near_orbit_profile import material_revision, profile_token, proof_path

  dest_dir = pathlib.Path("MyEditableView/catalog/destinations/destination.example-orbit")
  read_asset = lambda rel: (dest_dir / rel).read_bytes()
  proof = {
      "materialRevision": material_revision(near_orbit),
      "profileToken": profile_token(near_orbit, read_asset),
      "fallbackSHA256": hashlib.sha256(read_asset(near_orbit["fallbackPanorama"])).hexdigest(),
  }
  (dest_dir / proof_path(near_orbit)).write_text(json.dumps(proof, indent=2) + "\n")
  ```
- **Worked example**: `destination.low-orbit-earth`.
