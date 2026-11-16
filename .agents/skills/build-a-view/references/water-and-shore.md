# Realtime water and computed surf (`water` and `shore`)

Covers painted-water horizon rules, root `water` (`1.3.0–1.4.5`), and computed
breaking surf `shore` (`1.4.9–1.4.11`). See the public
[field reference](https://enterlocus.com/reference/locus-asset-format/).

## 1. Painted waterline rule (required for all water Views)

Locus draws computed View water as a horizontal plane below the seated eye, so
its distant edge converges slightly below the vertical midline (around `−0.35°`).
Painted water above that line remains static skybox pixels that rendered water
can never cover.

- Place the camera above the water surface, with distant shorelines and sea
  horizons sitting on or slightly below the image's vertical midline (`<= -0.8°`).
- Match the distant water color in `water` or `shore` to the painted sea at the
  horizon so the far fade is seamless.

## 2. Realtime water regions (`water`, App 1.3.0+)

Contract: `tools/water_contract.py` (`1..4` `regions`, total water texture
residency within `64 MiB`).

- **`motion`**: author `"ocean"` (GPU FFT waves, max **1** ocean region per
  package) or `"still"` (flat calm water). Legacy `"lake"`/`"stream"` labels
  remain readable aliases for older files; prefer `"ocean"` or `"still"` for new
  work.
- **Region blocks**: `id`, `pose` / bounds, `surface`, `optics`, `bed`, `blend`,
  and optional `glow` (`glow.mover` orbital disturbance adds a narrow capability).
- **Sub-feature version floors & tools**:
  - `bed.deepening` (`1.3.1+`), plus `macro` seabed map & `waveSlopeScale` /
    `chopSlope` open-water roughness (`1.4.5+`).
  - `reflectionRegistration`: `mask-image-v1` or `mask-layered-v1` (`1.3.1+`),
    checked by `tools/water_reflection_mask.py` and
    `tools/water_layered_reflection_mask.py`.
  - `contactCalibration` (`1.3.2+`, `layered-proxy-v1` with `.locusmesh` proxy
    and disoccluded background plate): authored/checked via
    `tools/water_contact_proxy.py`.
- **Worked examples** in `data/place-examples.json`:
  `destination.bioluminescent-mangrove-lagoon` (`water` + `fireflies`),
  `destination.tropical-shallow-bay` (`water` + `day-night` + `sound`),
  `destination.cloud-garden-isles` (`water` + `midground` + `sound`).

## 3. Computed breaking surf and open sea (`shore`, App 1.4.9+)

Contract: `tools/shore_contract.py`. Renders breaking surf on a `64 m × 64 m`
simulated shallow-water strip (`x: -32..32 m`, `z: -58..+6 m` in `shore.frame`,
`0.25 m` cells) extended analytically to the horizon.

- **Version floors & mutual exclusions**:
  - `shore`: `minimumAppVersion >= "1.4.9"`.
  - `shore.sand.wetBand` (presence of the boolean field, even `true`):
    `>= "1.4.10"`.
  - `shore` paired with `environment.sunPath.panoramaBlend`: `>= "1.4.11"`.
  - Cannot coexist with root `water`, `midground.water`, `celestial`,
    `nearOrbit`, `blackHole`, or any Room `ocean` region.
- **Authoring the bed and coast**:
  1. Model near dry ground (`midground.path`) and continuous seafloor within
     `~55 m` of seats; paint far coasts and distant sea into the panorama (surf
     fades into the panorama starting around `120 m`).
  2. Set `shore.frame` (`translationMeters` default `[0, -0.62, 0]`,
     `yawDegrees`) where surf breaks best, `-Z` seaward and `y` at still water.
  3. Bake `shore.bed.path` as a **16-bit grayscale PNG** (color type `0`,
     `2..2048` px per side) storing heights linearly across `heightRangeMeters`
     relative to still water. Ensure every column of the `64 m` strip crosses
     the still waterline cleanly once, the seaward start band (`z: -58..-45 m`)
     is at least `~3–4.5 m` deep, and slopes below `+2 m` stay `<= 1:2` so
     cells do not stair-step waves.
  4. Author all required linear-RGB blocks (`version: 1`, `swell`, `light`,
     `sky`, `water`, `sand`, `foam`, `sparkle`, `exposure`; no unknown keys or
     JSON `null`). Set `light.follow` to `"none"`, `"moon"` (requires
     `sky.moon`), or `"sun"` (requires `sunPath` or enabled `directSun`), and
     match `sand.dry` / `sand.wet` to your terrain material at the waterline.
