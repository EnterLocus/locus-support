# Sky, clouds, and 24-hour daylight

Covers procedural night skies (`sky`), animated painted clouds (`clouds`), and
24-hour solar paths / day-night blends (`environment.sunPath`). See the public
[field reference](https://enterlocus.com/reference/locus-asset-format/) and
[Make a day-and-night View tutorial](https://enterlocus.com/make-a-day-night-view/).

## 1. Procedural night sky (`sky`, App 1.2.4+)

Contract: `tools/procedural_sky.py`. Requires a `2:1` 8-bit grayscale PNG
`sky.mask` (color type `0`, max width `4096`; white `255` admits the
procedural sky and black `0` keeps the painted panorama).

- `stars`: procedural seed/clusters/brightStars or a custom `catalog` JSON
  (`locus-star-catalog` v1, up to `20,000` stars in `equatorial` or
  `horizontal` coordinates), `twinkle`, `limitingMagnitude`, `twilight`,
  `realSky`, and `milkyWay` (`realistic` or `vivid`, plus optional
  `milkyWay.diffuseMap` requiring `minimumAppVersion >= "1.3.0"`).
- `moon`: `azimuthDegrees`, `elevationDegrees`, `illumination`, `brightness`,
  `maximumIllumination`, `sizeScale`, and optional `drawnDiameterDegrees`
  (`1.3.4+`).
- `aurora`: `classic`, `storm`, or `low-latitude` palette and `1..4` arcs
  (excluded by `celestial` and `sunPath.daySky`).
- `defaultMode`: visitor default Real vs Free sky.
- **Worked examples** in `data/place-examples.json`:
  `destination.aurora-black-ice-shore` (`procedural-sky` with aurora),
  `destination.galactic-ledge` (`procedural-sky` with stars & moon).

## 2. Painted clouds (`clouds`, App 1.3.0+)

Contract: `tools/clouds_contract.py`. Animates clouds painted in the panorama
using two matching `2:1` 8-bit PNGs (max width `4096`):

- `clouds.mask`: 8-bit grayscale PNG (color type `0`) selecting movable clouds.
- `clouds.fill`: 8-bit RGB PNG (color type `2`, identical dimensions) filling
  sky exposed behind moving clouds.
- Controls: `horizonDegrees`, `altitudeMeters`, `seaDepthMeters`,
  `windMetersPerSecond`, `windTowardDegrees`, `cycleSeconds`, `evolution`,
  `breathing`.
- Check overlap if paired with `sky.mask`; excluded when `sunPath.daySky`,
  `panoramaGrade`, or `light` are present.
- **Worked example**: `destination.sunlit-cloud-walkway`.

## 3. 24-hour sun path & day-night blends (`environment.sunPath`)

Contract: `tools/sun_path_contract.py` (`1.3.0+`).

### Base requirements (`1.3.0+`)
- Both `panorama.path` and `environment.imageBasedLight` must be **free of a
  painted sun and sun-centered glare**. Check with `tools/sun_free_sky_check.py`.
- Set `"sunFreeSky": true` in `environment.sunPath` and add a `"sun-free-sky"`
  entry to `provenanceDetail.components` with non-empty `notes`.
- Optional `disc.skyMask`: `2:1` 8-bit grayscale PNG (`<= 4096` wide) admitting
  the moving solar disc behind foreground edges.
- Cannot coexist with `environment.directSun`, `celestial`, or static
  `sunVisibility` bakes.

### Day/night atmosphere and paired panoramas (`1.4.9–1.4.11`)
- **`daySky`, `panoramaGrade`, `light` (`1.4.9+`)**:
  - `daySky` (`haze`, `exposure`) renders clear daylight sky through `sky.mask`.
  - `panoramaGrade` tints and dims the painted panorama across `2..16` strictly
    increasing `elevationDegrees` stops (`-90..90`) with linear RGB `color`
    (`0..4`).
  - `light` drives Room lighting and `ambientEV`; set `"midground": true` to
    illuminate `midground.path` dynamically.
  - Both `daySky` and `panoramaGrade` require root `sky` with `sky.mask`. They
    exclude `clouds`, root `water`, `midground.water`, `midground.flowingWater`,
    `sky.aurora`, and `media` (unless paired with `media.dayNight`).
- **`panoramaBlend` (`1.4.10+`)**:
  - Blends a distinct aligned full-frame `2:1` night panorama (`path`, exact same
    width/height as `panorama.path`) between `dayElevationDegrees` and
    `nightElevationDegrees` (`-18..10`, `night < day`) with optional
    `nightGrade`.
  - Requires `daySky`, root `sky`, and **`gpuTextures` v2** (`astc-6x6-srgb`
    KTX1) for both `panorama.path` and `panoramaBlend.path`. Legacy singular
    `gpuTexture` is rejected.
- **`shore` or `media.dayNight` alongside `panoramaBlend`**: requires
  `minimumAppVersion >= "1.4.11"`.
- **Keeping your own painted sky**: paint `sky.mask` all-black (`0`) while
  retaining required `sky` and `daySky` blocks; Locus hides procedural stars,
  Moon, and blue sky while preserving the 24-hour clock, `panoramaBlend`,
  `panoramaGrade`, and dynamic Room/midground light.
- **Worked example**: `destination.chalk-dune-dawn` (`1.4.0`, includes Blender
  source bundle in `data/place-examples.json`).
