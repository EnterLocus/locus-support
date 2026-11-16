# Panorama video, atmosphere, and spatial sound

Covers localized looping video (`media`, `1.1.2+`, plus `media.dayNight`
`1.4.11+`), shader fireflies (`fireflies`, `1.3.0+`), distant point lights
(`pointLights`, `1.2.5+`), and View spatial audio (`sound`, `1.1.4+`).

## 1. Looping panorama video (`media`, App 1.1.2+)

Contract: `tools/panorama_media.py`. Embeds localized `.mp4` motion regions
anchored to `panorama.path` via `sourcePanoramaSHA256`:

- `mask`: `2:1` 8-bit grayscale PNG feathering moving video into the static
  panorama.
- `sources`: `1..4` entries (`<= 2` video sources, total `gain <= 1`), each
  referencing an `.mp4` video or legacy audio clip with localized `mediaTitles`.
- `regions`: `1..8` non-overlapping equirectangular rectangles (`bounds`,
  `mappingBounds`, `sourceRect`), respecting wrap across `u = 0 / 1`.
- **Loop quality**: trim source easing frames before searching loop cuts, use a
  short forward dissolve only where smooth, never reverse-loop water, and test
  four consecutive repeats.
- **`media.dayNight` (`1.4.11+`)**: the only `media` shape allowed with
  `sunPath.panoramaBlend` (also requires `daySky`, `sky.mask`, and `gpuTextures`
  v2 sidecars). Supply `nightPanoramaSHA256` and one `lighting` PNG (**raw
  linear RGB8** multipliers) plus `emission` PNG (**sRGB**) per video source
  (`<= 4096×2048`, aggregate decode budget `<= 4096×2048×30.1`).
- **Worked examples** in `data/place-examples.json`: `destination.emerald-grotto`,
  `destination.desert-canyon-oasis`, `destination.graniteperch`.

## 2. Shader fireflies (`fireflies`, App 1.3.0+)

Contract: `tools/fireflies_contract.py`. Pure-data shader volume declaration
(no external assets; excluded by `celestial`, `nearOrbit`, `blackHole`; obeys
Animated View off / Reduce Motion):

- `fireflies.volumes`: `1..4` entries, total `count <= 400`.
- Per volume: `id`, `centerMeters` (`-100..100`), `sizeMeters` (`0.1..100`),
  `count` (`1..400`), optional `color` (`[r, g, b]` `0..1`), `sizeMillimeters`
  (`1..20`), `blink` (`periodSeconds` `1.5..20`, `duty` `0.05..0.8`, `jitter`
  `0..1`), and `driftMetersPerSecond` (`0..0.5`).
- **Worked example**: `destination.bioluminescent-mangrove-lagoon`.

## 3. Distant point lights (`pointLights`, App 1.2.5+)

Contract: `tools/point_lights.py`. Animates up to `4,000` distant horizon lights
without video encoding:

- Declare `"pointLights": {"table": "point-lights.json"}` in `destination.json`.
- `point-lights.json` (`<= 1 MiB`): `{"format": "locus-point-lights", "version": 1, "groups": [...]}`
  with `1..64` groups. Each group sets `id`, `color` (`0..1` RGB), `behavior`
  (`blink` or `twinkle`), and `lights` rows `[u, v, angularSizeDegrees, intensity]`
  (`u` in `[0, 1)`, `v` in `[0, 1]`, `angularSizeDegrees` `0.001..0.5`,
  `intensity` `0..4`).
- Excluded by `nearOrbit` and `blackHole`.

## 4. View spatial sound (`sound`, App 1.1.4+)

Contract: `tools/package_sound.py`.

- In a complete Package v2 View, embed `"sound": {...}` directly inside
  `destination.json` (flat compatibility Views use a top-level `sound.json`).
- **Required envelope**: `version` (`1` or `2`), `backgroundPriority`
  (`0..100`; use `0` on Views so Room backgrounds take priority when paired),
  and `sources` (`1..8` entries, sum of `gain <= 1.0`).
- **View roles**: `"background"` or `"effect"` (`"music"` is **Room-only**).
  Clips use `.m4a`, `.mp3`, or `.wav`, each `<= 128 MiB`.
- **v2 spatial placement (`frame: "view"`) & mono rule**:
  - `"ambient"` placement may be stereo.
  - `"point"` (`{azimuthDegrees, elevationDegrees, distanceMeters}`), `"points"`
    (`2..16` unique positions), and View-only `"region"` (`azimuthCenterDegrees`,
    `azimuthSpanDegrees`, `elevationRangeDegrees`, `distanceRangeMeters`)
    **must use mono clips** so RealityKit can spatialize each emitter. Check
    stereo vs L/R channels before downmixing to avoid phase-cancellation surges.
  - `playback`: `"loop"` (single clip with optional fade in/out, `ambient` or
    `point` only) or `"random"` (`intervalSeconds` `[0.25, 600]`,
    `maxConcurrent: 1`, optional `avoidImmediateRepeat`).
  - Translate source titles in `localizations.<lang>.soundTitles` keyed by `id`.
