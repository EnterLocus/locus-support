# Panorama video, atmosphere, and spatial sound

Covers localized looping video (`media`, `1.1.2+`, plus `media.dayNight`
`1.4.11+`), shader fireflies (`fireflies`, `1.3.0+`), distant point lights
(`pointLights`, `1.2.5+`), and View spatial audio (`sound`, `1.1.4+`).

## 1. Looping panorama video (`media`, App 1.1.2+)

Contract: `tools/panorama_media.py`. Embeds localized `.mp4` (HEVC/AVC) motion
regions anchored to `panorama.path` via `sourcePanoramaSHA256`:

```json
{
  "media": {
    "version": 1,
    "sourcePanoramaSHA256": "<64-char hex sha256 of panorama.path>",
    "mask": "media-mask.png",
    "sources": [
      {"id": "surf-loop", "title": "Shore Surf", "video": "surf-loop.mp4", "gain": 0.0}
    ],
    "regions": [
      {
        "id": "shore-band",
        "source": "surf-loop",
        "bounds": [0.35, 0.65, 0.48, 0.72],
        "mappingBounds": [0.34, 0.66, 0.47, 0.73],
        "sourceRect": [0.0, 0.0, 1.0, 1.0]
      }
    ],
    "dayNight": {
      "version": 1,
      "nightPanoramaSHA256": "<64-char hex sha256 of sunPath.panoramaBlend.path>",
      "sources": [
        {"source": "surf-loop", "lighting": "surf-lighting.png", "emission": "surf-emission.png"}
      ]
    }
  }
}
```

- `mask`: `2:1` 8-bit grayscale PNG feathering moving video into the static
  panorama.
- `sources`: `1..4` entries (`<= 2` video sources, total `gain <= 1`), each
  referencing an **8-bit 4:2:0 limited-range HEVC/H.264** `.mp4` `"video"` (no
  4:4:4 or full-range encoding) or legacy `.m4a`/`.mp3` `"audio"` clip with
  required `"title"` and localized `mediaTitles`.
- `regions`: `1..8` non-overlapping equirectangular rectangles (`bounds`,
  `mappingBounds` containing `bounds`, and normalized `sourceRect` `[x, y, w, h]`),
  respecting wrap across `u = 0 / 1`.
- **Loop quality**: trim source easing frames before searching loop cuts, use a
  short forward dissolve only where smooth, never reverse-loop water, and test
  four consecutive repeats.
- **`media.dayNight` (`1.4.11+`, omit for static daytime `media`)**: the only
  `media` shape allowed with `sunPath.panoramaBlend` (also requires `daySky`,
  `sky.mask`, and `gpuTextures` v2 sidecars). Video tracks must have a
  nonrotated preferred transform; supply `nightPanoramaSHA256` and one `lighting`
  PNG (**raw linear RGB8** multipliers) plus `emission` PNG (**sRGB RGB8**) per
  video source — both 8-bit RGB PNGs **without alpha**, exact video pixel
  dimensions (`<= 4096×2048`, aggregate decode budget `<= 4096×2048`).
- **Worked examples** in `data/place-examples.json`: `destination.emerald-grotto`,
  `destination.desert-canyon-oasis`, `destination.graniteperch`.

## 2. Shader fireflies (`fireflies`, App 1.3.0+)

Contract: `tools/fireflies_contract.py`. Pure-data shader volume declaration
(no external assets; excluded by `celestial`, `nearOrbit`, `blackHole`; obeys
Animated View off / Reduce Motion):

> **Important**: `destination.json` must wrap the array in `{"volumes": [...]}`.
> Do **not** use a bare `"fireflies": [{...}]` array — older format notes
> sometimes omit `"volumes"`, and `tools/fireflies_contract.py` rejects bare
> arrays.

```json
{
  "fireflies": {
    "volumes": [
      {
        "id": "glade-fireflies",
        "centerMeters": [0.0, 0.8, -8.5],
        "sizeMeters": [12.0, 3.0, 8.0],
        "count": 80,
        "color": [0.75, 1.0, 0.35],
        "sizeMillimeters": 6,
        "blink": {"periodSeconds": 3.0, "duty": 0.35, "jitter": 0.5},
        "driftMetersPerSecond": 0.15
      }
    ]
  }
}
```

- `fireflies.volumes`: `1..4` entries, total `count <= 400`.
- Per volume bounds: `centerMeters` (`-100..100`), `sizeMeters` (`0.1..100`),
  `count` (`1..400`), optional `color` (`[r, g, b]` `0..1`), `sizeMillimeters`
  (`1..20`), `blink` (`periodSeconds` `1.5..20`, `duty` `0.05..0.8`, `jitter`
  `0..1`), and `driftMetersPerSecond` (`0..0.5`).
- **Worked example**: `destination.bioluminescent-mangrove-lagoon`.

## 3. Distant point lights (`pointLights`, App 1.2.5+)

Contract: `tools/point_lights.py`. Animates up to `4,000` distant horizon lights
without video encoding:

- Declare `"pointLights": {"table": "point-lights.json"}` in `destination.json`.
- `point-lights.json` (`<= 1 MiB`): `1..64` groups, each with exact keys `id`,
  `color` (`0..1` RGB), `behavior` (`blink` or `twinkle`), and `lights` rows
  `[u, v, angularSizeDegrees, intensity]` (`u` in `[0, 1)`, `v` in `[0, 1]`,
  `angularSizeDegrees` `0.001..0.5`, `intensity` `0..4`):
  ```json
  {
    "format": "locus-point-lights",
    "version": 1,
    "groups": [
      {
        "id": "buoy-beacons",
        "color": [1.0, 0.35, 0.1],
        "behavior": {
          "type": "blink",
          "periodSeconds": 4.0,
          "phaseSeconds": 0.5,
          "minimum": 0.05,
          "softness": 1.2
        },
        "lights": [[0.42, 0.52, 0.08, 1.8]]
      },
      {
        "id": "harbor-lights",
        "color": [1.0, 0.85, 0.55],
        "behavior": {"type": "twinkle", "amplitude": 0.18, "speed": 0.7},
        "lights": [[0.58, 0.51, 0.04, 1.2]]
      }
    ]
  }
  ```
  - `blink` requires exact keys `type`, `periodSeconds` (`1..20`),
    `phaseSeconds` (`0 <= phase < periodSeconds`), `minimum` (`0..1`),
    `softness` (`0.2..4`).
  - `twinkle` requires exact keys `type`, `amplitude` (`0..0.3`), `speed`
    (`0.05..2`).
- Excluded by `nearOrbit` and `blackHole`.

## 4. View spatial sound (`sound`, App 1.1.4+)

Contract: `tools/package_sound.py`.

```json
{
  "sound": {
    "version": 2,
    "backgroundPriority": 0,
    "sources": [
      {
        "id": "surf-ambience",
        "title": "Surf Ambience",
        "role": "background",
        "gain": 0.55,
        "clips": ["audio/surf.m4a"],
        "placement": {"type": "ambient"},
        "playback": {"type": "loop", "fadeInSeconds": 1.5, "fadeOutSeconds": 1.5}
      },
      {
        "id": "coastal-gulls",
        "title": "Coastal Gulls",
        "role": "effect",
        "gain": 0.3,
        "clips": ["audio/gull-1.wav", "audio/gull-2.wav"],
        "placement": {
          "type": "region",
          "frame": "view",
          "azimuthCenterDegrees": -20,
          "azimuthSpanDegrees": 90,
          "elevationRangeDegrees": [5, 30],
          "distanceRangeMeters": [18, 45]
        },
        "playback": {
          "type": "random",
          "intervalSeconds": [6, 18],
          "maxConcurrent": 1,
          "avoidImmediateRepeat": true
        }
      }
    ]
  }
}
```

- In a complete Package v2 View, embed `"sound": {...}` directly inside
  `destination.json` (flat compatibility Views use a top-level `sound.json`).
- **Required envelope**: `version` (`1` or `2`), `backgroundPriority`
  (`0..100`; use `0` on Views so Room backgrounds take priority when paired),
  and `sources` (`1..8` entries, sum of `gain <= 1.0`).
- **View roles**: `"background"` or `"effect"` (`"music"` is **Room-only**).
  Clips use `.m4a`, `.mp3`, or `.wav`, each `<= 128 MiB`.
- **v2 spatial placement (`frame: "view"`) & mono rule**:
  - `"ambient"` (`{"type": "ambient"}`) may be stereo.
  - `"point"` (`{"type": "point", "frame": "view", "point": {"azimuthDegrees": ..., "elevationDegrees": ..., "distanceMeters": ...}}`),
    `"points"` (`2..16` unique positions), and View-only `"region"` (`azimuthCenterDegrees`,
    `azimuthSpanDegrees`, `elevationRangeDegrees`, `distanceRangeMeters`,
    optional `rolloff` `0..4`) **must use mono clips** so RealityKit can
    spatialize each emitter. Check stereo vs L/R channels before downmixing to
    avoid phase-cancellation surges.
  - `playback`: `"loop"` (single clip with optional `fadeInSeconds` /
    `fadeOutSeconds` `0..5`, `ambient` or `point` only) or `"random"`
    (`intervalSeconds` `[0.25, 600]`, `maxConcurrent: 1`, optional
    `avoidImmediateRepeat`).
  - Translate source titles in `localizations.<lang>.soundTitles` keyed by `id`.
