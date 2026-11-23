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

```json
{
  "water": {
    "preset": "tropical-lagoon",
    "regions": [
      {
        "id": "lagoon",
        "shape": "disc",
        "pose": {
          "translationMeters": [0, -0.62, 0],
          "orientationXYZW": [0, 0, 0, 1]
        },
        "sizeMeters": [360, 360],
        "surface": {
          "motion": "ocean",
          "waveHeightMeters": 0.12,
          "waveLengthMeters": 24,
          "waveSpeed": 0.85,
          "directionDegrees": 15,
          "roughness": 0.16,
          "detailFadeMeters": [30, 140]
        },
        "optics": {
          "color": [0.02, 0.24, 0.28],
          "absorptionPerMeter": [0.65, 0.18, 0.10],
          "reflectionBlur": 1.2,
          "sunGlint": 1.4
        },
        "bed": {
          "albedo": "water-bed-albedo.png",
          "depthMeters": 1.8,
          "reliefMeters": 0.4,
          "tileMeters": 8.0,
          "caustics": 0.8,
          "deepening": {
            "startMeters": 45,
            "endMeters": 140,
            "depthMeters": 16.0,
            "color": [0.01, 0.08, 0.12],
            "rmsSlope": 0.05,
            "shoreSlope": 0.08,
            "waveSlopeScale": 2.2,
            "chopSlope": 0.12,
            "macro": {
              "map": "water-macro.png",
              "shallowMeters": 2.4,
              "tileMeters": 240,
              "coverage": 0.55,
              "fadeMeters": [20, 110]
            }
          }
        },
        "blend": {
          "panoramaMask": "water-mask.png",
          "horizonSkirt": true,
          "roomKeepOut": true
        },
        "glow": {
          "color": [0.1, 0.85, 1.0],
          "strength": 1.1,
          "mover": [0, -6, 3.5, 0.35]
        }
      }
    ]
  }
}
```

- **`surface.motion`**: author `"ocean"` (GPU FFT waves, max **1** ocean region
  per package) or `"still"` (flat calm water). Keep `waveLengthMeters >= max(0.05, 2 * cellMeters / 0.61)`
  where `cellMeters` is `pi * sizeMeters[0] / 64` for a disc (`256` with
  `contactCalibration`) or `max(sizeMeters) / 64` for a rectangle.
- **`bed`**:
  - `bed.albedo`: non-interlaced **8-bit RGBA PNG** (`color_type = 6`) where
    RGB is seabed albedo and the **Alpha channel** stores normalized bed relief
    scaled by `reliefMeters` (`0..50`).
  - `bed.tileMeters` (`0.1..1000`) and `bed.extentMeters` (`[minX, minZ, maxX, maxZ]`)
    are **mutually exclusive**. `bed.sunVisibility` requires `extentMeters` and
    no `sunPath`; `bed.deepening` (`1.3.1+`) requires a tiled bed (no
    `extentMeters`) with `startMeters < endMeters` and `depthMeters >= bed.depthMeters`.
  - `deepening.macro` (`1.4.5+`): `macro.map` is a **square 8-bit grayscale
    PNG** (`<= 2048`), with `bed.depthMeters <= macro.shallowMeters < deepening.depthMeters`;
    `waveSlopeScale` (`1..8`) and `chopSlope` (`0..0.5`) control open-water
    wave roughness (`1.4.5+`).
- **`blend` & `glow.mover`**: `blend.horizonSkirt: true` requires
  `shape: "disc"`; `blend.panoramaMask` is a `2:1` 8-bit grayscale PNG. Optional
  View-only `glow.mover` takes `[centerX, centerZ, orbitRadiusMeters, angularSpeedRadPerSec]`
  (`orbitRadiusMeters` `0.1..25`, `angularSpeedRadPerSec` `0..1`).
- **Sub-feature version floors & tools**:
  - `bed.deepening` (`1.3.1+`); `macro`, `waveSlopeScale`, `chopSlope` (`1.4.5+`).
  - `reflectionRegistration`: `mask-image-v1` or `mask-layered-v1` (`1.3.1+`,
    requires `blend.panoramaMask`), checked by `tools/water_reflection_mask.py`
    and `tools/water_layered_reflection_mask.py`.
  - `contactCalibration` (`1.3.2+`, `layered-proxy-v1`, single floor-centered
    `disc` region with `blend.horizonSkirt: true` and `.locusmesh` proxy):
    authored and validated via `tools/water_contact_proxy.py` (`bake_patch`,
    `far_reflection_plate`, `reflection_plate`, `validate_assets`). Pairing root
    `water` (or `contactCalibration` without `sky.aurora`) with
    `environment.sunPath` (`daySky`, `panoramaGrade`, `light`) requires
    `minimumAppVersion >= "1.5.1"` (`locus.view.water.day-night.v1`).
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
- **Coordinate frame and `shore.bed.path` baking contract**:
  1. `shore.frame` (`translationMeters = [tx, ty, tz]` default `[0, -0.62, 0]`,
     `yawDegrees = a`) places the surf frame in View space: `+X` is alongshore
     east, `+Y` is up (`0` = still water `ty`), **`-Z` is seaward**, and **`+Z`
     is landward**. Map a shore sample `(sx, sz)` into View coordinates `(vx, vz)`
     before sampling terrain elevation:
     ```text
     vx = tx + sx * cos(rad(a)) - sz * sin(rad(a))
     vz = tz + sx * sin(rad(a)) + sz * cos(rad(a))
     relativeHeight = terrainY(vx, vz) - ty
     ```
  2. For `bed.sizeMeters = [W, D]` (`8..4000`), `bed.centerMeters = [cx, cz]`
     (`-4000..4000`), and image dimensions `width × height` (`2..2048` px per
     side), sample cell centers with **column `0` at `-X` (west)** and **row `0`
     (top PNG row) at `-Z` (farthest seaward)**:
     ```text
     sx = cx - W / 2 + (col + 0.5) * (W / width)     # col = 0 .. width - 1
     sz = cz - D / 2 + (row + 0.5) * (D / height)    # row = 0 .. height - 1
     ```
  3. Encode `shore.bed.path` as a non-interlaced **big-endian (`>H`) 16-bit
     grayscale PNG** (`bit_depth = 16`, `color_type = 0`). Given
     `heightRangeMeters = [lo, hi]` (`-200 <= lo < hi <= 200`):
     ```python
     u16 = max(0, min(65535, round((relativeHeight - lo) / (hi - lo) * 65535)))
     ```
  4. Ensure every column of the `64 m` strip crosses `0 m` cleanly once, the
     seaward start band (`z: -58..-45 m`) is at least `~3–4.5 m` deep, and slopes
     below `+2 m` stay `<= 1:2` so cells do not stair-step waves.
- **Required linear-RGB manifest shape** (all top-level keys below except `frame`
  and `bed` are required; no unknown keys or `null` values):
  ```json
  {
    "shore": {
      "version": 1,
      "frame": {"translationMeters": [0, -0.62, 0], "yawDegrees": 0},
      "bed": {
        "path": "shore-bed.png",
        "sizeMeters": [64, 64],
        "centerMeters": [0, -26],
        "heightRangeMeters": [-6, 4]
      },
      "swell": {"height": 0.9, "period": 1.0, "windChop": 0.4, "curl": 0.8},
      "light": {
        "azimuthDegrees": -35,
        "elevationDegrees": 32,
        "color": [1.0, 0.95, 0.88],
        "night": 0.05,
        "follow": "sun"
      },
      "sky": {"zenith": [0.16, 0.36, 0.68], "horizon": [0.56, 0.72, 0.86]},
      "water": {
        "deep": [0.015, 0.09, 0.14],
        "shallowScatter": [0.05, 0.32, 0.34],
        "crestScatter": [0.08, 0.38, 0.38],
        "absorption": [0.48, 0.16, 0.11],
        "clarity": 1.05
      },
      "sand": {
        "dry": [0.46, 0.40, 0.32],
        "wet": [0.18, 0.15, 0.12],
        "wetBand": true
      },
      "foam": 1.0,
      "sparkle": 0.9,
      "exposure": 1.0
    }
  }
  ```
  Set `light.follow` to `"none"`, `"moon"` (requires `sky.moon`; moonlight
  water and wet-sand reflection width scales automatically with Moon Size in
  Locus 1.6.0+), or `"sun"` (requires `environment.sunPath` or an enabled
  `environment.directSun`), and match `sand.dry` / `sand.wet` to your terrain
  material at the waterline. For expansive open-sea horizons, pair `shore` with
  `skyRadiusMeters: 1600` (`1.5.1+`) and 3D coastal `midground.path` relief.
