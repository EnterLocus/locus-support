# Sky, clouds, and 24-hour daylight

Covers procedural night skies (`sky`), animated painted clouds (`clouds`), and
24-hour solar paths / day-night blends (`environment.sunPath`). See the public
[field reference](https://enterlocus.com/reference/locus-asset-format/) and
[Make a day-and-night View tutorial](https://enterlocus.com/make-a-day-night-view/).

## 1. Procedural night sky (`sky`, App 1.2.4+)

Contract: `tools/procedural_sky.py`. Requires a `2:1` 8-bit grayscale PNG
`sky.mask` (color type `0`, max width `4096`; white `255` admits the
procedural sky and black `0` keeps the painted panorama).

- `stars`: procedural `seed` / `clusters` / `brightStars` or a custom `catalog`
  JSON file (`locus-star-catalog` v1, up to `20,000` stars, `<= 1 MiB`),
  `twinkle`, `limitingMagnitude`, `twilight`, `realSky` (`latitudeDegrees`,
  `siderealTimeHours`), and `milkyWay` (`realistic` or `vivid`, plus optional
  `milkyWay.diffuseMap` requiring `minimumAppVersion >= "1.3.0"`).
  - When `stars.catalog` is set, omit `seed`, `clusters`, and `brightStars`.
    When `stars.realSky` is set, omit `milkyWay.centerAzimuthDegrees`,
    `milkyWay.centerElevationDegrees`, and `milkyWay.tiltDegrees`.
  - **`locus-star-catalog` v1 JSON** (`frame: "equatorial"` requires
    `sky.stars.realSky` with RA `[0, 360)` and Dec `[-90, 90]`;
    `"horizontal"` uses azimuth `[-180, 180]` and elevation `[-90, 90]`;
    `magV` `-2..8`, `B-V` `-0.5..2.5`):
    ```json
    {
      "format": "locus-star-catalog",
      "version": 1,
      "frame": "horizontal",
      "source": "Custom catalog",
      "stars": [
        [15.0, 42.5, -1.46, 0.0],
        [-110.0, 28.0, 1.25, 0.85]
      ]
    }
    ```
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
  entry to `destination.json`'s `provenanceDetail.components` with non-empty
  `notes` (if `aiGenerated: true`, `providers` is also required):
  ```json
  {
    "provenanceDetail": {
      "formatVersion": 1,
      "components": [
        {
          "component": "sun-free-sky",
          "aiGenerated": false,
          "notes": "Verified panorama and IBL with tools/sun_free_sky_check.py"
        }
      ]
    }
  }
  ```
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

```json
{
  "environment": {
    "imageBasedLight": "lighting-ibl.jpg",
    "sunPath": {
      "sunFreeSky": true,
      "startHour": 9,
      "dayDurationSeconds": 3600,
      "maxElevationDegrees": 60,
      "daySky": {"haze": 0.25, "exposure": 1.0},
      "panoramaGrade": {
        "stops": [
          {"elevationDegrees": -12, "color": [0.18, 0.22, 0.34]},
          {"elevationDegrees": 15, "color": [1.0, 0.96, 0.92]}
        ]
      },
      "light": {
        "midground": true,
        "stops": [
          {"elevationDegrees": -12, "color": [0.1, 0.14, 0.28], "ambientEV": -2.5},
          {"elevationDegrees": 30, "color": [1.2, 1.15, 1.05], "ambientEV": 0.0}
        ]
      },
      "panoramaBlend": {
        "path": "panorama-night.jpg",
        "dayElevationDegrees": 2,
        "nightElevationDegrees": -10,
        "nightGrade": [1.0, 1.0, 1.0]
      }
    }
  }
}
```
