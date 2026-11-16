# Space, orbital, and black-hole Views

Covers the three space/orbital profiles: `blackHole` (`1.3.4+`), `celestial`
(`1.2.4+` / v2 `1.2.5+`), and `nearOrbit` (`1.3.0+` / v2 `1.3.2+`). See also
[Make your own black hole View](https://enterlocus.com/make-a-black-hole-view/)
and the [field reference](https://enterlocus.com/reference/locus-asset-format/).

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
  - `version: 1` (`1.2.4+`): fixed 700 m convention (`angularDiameterDegrees`).
  - `version: 2` (`1.2.5+`): explicit `distanceMeters` (`400..800`) +
    `radiusMeters` (`1..400`) or `angularDiameterDegrees`, satisfying
    `radius <= distance * 0.5` and `distance + radius <= 1100`.
- **Add-on floors**:
  - Cloud shell (`cloudHeightRatio`, `cloudDriftRatio`, `cloudShadowStrength`,
    `cloudEvolution`, `cloudEvolutionPeriodSeconds`), `sunDisc`, or shared `sky`:
    `minimumAppVersion >= "1.3.0"`.
  - Gas-giant `advection` (`tools/celestial_advection.py`): `>= "1.3.2"`.
  - Oblate `polarRadiusRatio` & planetary `rings` (`tools/celestial_rings.py`):
    `>= "1.3.4"`.
- **Sidecars**: supply `gpuTextures` v2 (`1.3.0+`) for `backgroundPanorama`,
  `dayTexture`, `nightTexture`, and `cloudTexture` (`astc-6x6-linear` for
  `cloudTexture`, `astc-6x6-srgb` for the others).
- `oceanGlint` is retired and rejected by public validation; never include it.
- **Worked example**: `destination.earth-from-space`.

---

## 3. Near-orbit profile (`nearOrbit`, App 1.3.0+ / v2 1.3.2+)

Contract: `tools/near_orbit_profile.py` and
`schemas/view-near-orbit-v1.schema.json` /
`schemas/view-near-orbit-v2.schema.json`.

- `version: 1` (`1.3.0+`): regional texture patch + globals (`dayTexture`,
  `nightTexture`, `cloudTexture`, `regionTexture`, `regionMask`,
  `fallbackPanorama`, `skyMask`, `galaxyTexture`, `starCatalog`).
- `version: 2` (`1.3.2+`): configurable `bodyRadiusKilometers`, optional
  equirectangular `tiles` manifest (up to 1024 square tiles), and optional
  per-tile `surface` slope/water-cover manifest (`8-bit` RGB PNGs with
  `astc-6x6-linear` KTX1 sidecars).
- `fallbackPanorama` must equal root `panorama.path`, and the package must carry
  a content-bound fallback proof JSON (`<= 16 KiB`) plus matching `gpuTextures`
  v2 sidecars. Keep camera and region parameters coupled to their baked proof.
- **Worked example**: `destination.low-orbit-earth`.
