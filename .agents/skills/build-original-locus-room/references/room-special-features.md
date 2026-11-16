# Room special features and atmosphere

Use this reference when a Room brief includes architectural fire, water, sound,
looping video, experimental animations, or tight indoor/outdoor integration
with a paired View. Every feature below requires complete Package v2 (except
legacy flat-format floors explicitly noted in the
[field reference](https://enterlocus.com/reference/locus-asset-format/)). Set
`minimumAppVersion` in `locusplace.json` to at least the highest floor of all
features you use, and verify entity bindings with `tools/check_room.py`.

---

## 1. Fireplace and burner flames (`particleEffects`, 1.2.1+)

Do **not** build 2D flame cards, alpha billboards, or glowing flame meshes
inside a firebox. Leave the firebox geometry clean and export a transform-only
Xform anchor (for example a Blender Empty named `Fireplace_Fire_Emitter`) at
the burner surface or top of the logs:

```json
"particleEffects": [
  {
    "id": "fireplace-fire",
    "displayName": "Fireplace Fire",
    "preset": "fire",
    "anchorEntity": "Fireplace_Fire_Emitter",
    "sizeMeters": [0.62, 0.04, 0.22]
  }
]
```

- At most **4** entries per Room. `preset` is currently `"fire"` only.
- `sizeMeters` is `[width, height, depth]` in `(0, 3]` meters in the anchor's
  local `+Y`-up frame. Flames originate at the anchor origin and rise along its
  local `+Y` — widen X/Z for a long linear burner rather than scaling an image.
- Runs continuously; never tied to `luminaireGroups` and carries no sound. Pair
  it with an emitter in `sound.json` if crackling audio is wanted.
- Translate `displayName` via `localizations.<lang>.particleTitles` keyed by
  `id`.

---

## 2. Pools and reflecting basins (`water`, 1.3.0+)

Outdoor oceans, distant lakes, and horizon water belong to the paired View.
For a **Room-owned pool, plunge basin, or reflecting tray** declared in
`space.json`:

- Model the empty concrete/stone basin in Blender with its bed material and
  lighting baked into the basin floor/walls. Do **not** export a flat water
  plane mesh inside `scene.usdz` covering that basin.
- Declare top-level `water` in `space.json` (`1...4` `regions`, each with `id`,
  `pose` `{translationMeters, orientationXYZW}`, and `sizeMeters`, plus optional
  `shape`, `surface`, `optics`, `bed`, `blend`, `glow`, and
  `reflectionRegistration`; keep water texture budgets within 64 MiB).
- Set `minimumAppVersion` to `"1.3.0"` or later (higher if subfields require it;
  check with `tools/validate_locusplace.py`).
- If outdoor View water passes beneath a Room terrace or infinity pool, prefer
  `viewGroundFootprint` (Section 6) so the View ground is clipped strictly to
  solid occupied areas rather than a loose bounding box.

---

## 3. Waterfalls, cascades, streams, and scrolling textures

### `flowingWater` (1.4.9+, Package v2 only)

Use `flowingWater` for waterfall curtains, tiered cascades, spillways, and
streams modeled inside `scene.usdz`:

```json
"flowingWater": [
  {
    "entities": ["Terrace_Spillway_Water"],
    "speed": 1.0,
    "ripple": 0.45,
    "whiteness": 0.8,
    "brightness": 1.0,
    "shells": 1,
    "mist": 0.6,
    "spray": 0.4,
    "plunges": [
      {
        "position": [2.4, 0.05, -4.8],
        "width": 1.8,
        "height": 1.6,
        "yawDegrees": 0
      }
    ]
  }
]
```

- Requires `minimumAppVersion >= "1.4.9"` and renders in Virtual Space only.
- 1–16 entries. Every name in `entities` must be an exact, unique mesh-bearing
  entity in `scene.usdz`, never nested inside another `flowingWater` entity and
  disjoint from `textureFlow`.
- Author flow UVs on the exported mesh (`primvars:st`, `u` across width, `v`
  along flow) and optional vertex-color foam mask (`primvars:displayColor`).
- Optional parameters: `whiteness` (`0...1.5`), `shells` (`0...2`), `color`
  (`[r, g, b]` in `0...1`), `ripple` (`0...1`), `speed` (`0.25...2`),
  `brightness` (`0...4`), `mist` (`0...2`), `spray` (`0...2`), and up to 8
  `plunges` (`position` in `scene.usdz` meters, `width` `0.2...20`, `height`
  `0.3...30`, optional `yawDegrees` within `±360`).

### `textureFlow` (1.4.5+, Package v2 only)

For simple continuous UV-scrolling surfaces (for example animated water channels
or decorative bands that do not need `flowingWater` plunges/mist), declare
1–16 `textureFlow` entries:

```json
"textureFlow": [
  {
    "entities": ["Fountain_Runnel"],
    "uvVelocity": [0.0, -0.35]
  }
]
```

- Requires `minimumAppVersion >= "1.4.5"`. `uvVelocity` values are finite in
  `-2...2`, not both `0`.
- Runs when the paired View's Animated View switch is on and Reduce Motion is off.

---

## 4. Looping video surfaces (`videoSurfaces`, 1.2.1+) vs. Room TVs (`tvs`)

- **Use [`tvs`](room-tvs.md) (1.4.9+)** for interactive 16:9 screens where
  visitors browse and play live web pages from Locus Browser.
- **Use `videoSurfaces` (1.2.1+, flat ZIP `formatVersion: 7`)** only for short,
  self-contained `.mp4` loops baked into the archive (at most **2** per Room):

```json
"videoSurfaces": [
  {
    "id": "hearth-loop",
    "displayName": "Hearth Glow",
    "entityName": "Hearth_Video_Quad",
    "video": "hearth-loop.mp4",
    "luminaireGroupID": "fireplace"
  }
]
```

- `video` must be a bare root `.mp4` filename matching the archive's `.mp4`
  files 1-to-1; every entity must be disjoint from `tvs` and other bound
  subtrees. Translate `displayName` via `localizations.<lang>.videoTitles`.

---

## 5. Spatial audio and Room music (`sound.json`, 1.1.4+ / music 1.4.1+)

Place `sound.json` and its referenced `.m4a`, `.mp3`, or `.wav` files (each
at most 128 MiB; no unreferenced audio files) in the Room root directory:

```json
{
  "version": 2,
  "backgroundPriority": 60,
  "sources": [
    {
      "id": "fireplace-crackle",
      "title": "Fireplace",
      "role": "background",
      "gain": 0.45,
      "clips": ["fireplace.m4a"],
      "placement": {
        "type": "point",
        "frame": "room",
        "point": {"positionMeters": [0.0, 0.4, -3.2]},
        "rolloff": 1.0
      },
      "playback": {"type": "loop", "fadeInSeconds": 1.0, "fadeOutSeconds": 1.0}
    },
    {
      "id": "villa-music",
      "title": "Evening Jazz",
      "role": "music",
      "gain": 0.35,
      "clips": ["evening-jazz.m4a"],
      "placement": {"type": "ambient"},
      "playback": {"type": "loop"}
    }
  ]
}
```

- Total `gain` across all `1...8` sources must be `<= 1.0`.
- `role`: `"background"` (arbitrates by `backgroundPriority` `0...100` against
  the paired View), `"effect"` (point/points loops or `random` cues with
  `intervalSeconds` in `[0.25, 600]` and `maxConcurrent: 1`), or **`"music"`**
  (Room-only, at most **1** per Room, requires `version: 2`, `ambient`
  placement, `loop` playback, and `minimumAppVersion >= "1.4.1"`).
- Translate `title` via `localizations.<lang>.soundTitles` keyed by `id`.

---

## 6. Outdoor View ground, keep-out, and forward yaw (`viewGround*`, `viewForwardYawRadians`)

Never widen `scene.usdz` with a huge fake terrain slab just to cover the paired
View. Instead declare the Room's exact indoor/outdoor relationship in
`space.json`:

- **`viewGroundFloorOffsetMeters`** (`1.4.4+`, `0...100` m above Room min-Y):
  anchors the paired View's water and midground height relative to the Room.
- **`viewGroundFootprint`** (`1.4.5+`, flat ZIP `12`/`13`): replaces the rough
  rectangular bounding-box keep-out with 1–32 Room-local X/Z polygons
  (`[-200, 200]`, 3–128 vertices each, total `<= 512`). Add optional
  `bottomHeightsMeters` (1 per polygon) so View water stays visible beneath
  elevated decks, piers, or glass bridges.
- **`viewGroundKeepOut`** (`1.4.4+`, default `true`): keep `true` for normal
  ground clipping; only set `false` when all occupied floors sit above the View
  ground and opaque Room geometry handles depth occlusion.
- **`viewMidgroundVisibility`** (`1.4.4+`): `"all"` (default), `"terrainOnly"`,
  or `"hidden"`. If hiding View terrain, cover exposed ground under the Room's
  architecture yourself.
- **`viewForwardYawRadians`** (`1.2.1+`, `-π...π`): decouples the View's
  straight-ahead sky/sun direction from the first seat's facing `yawRadians`.

---

## 7. Experimental animations and illuminated surfaces

- **Experimental Room animations (`ambientAnimations`, v4):** documented in full
  in [Room interface — Experimental Room v4 animations](room-interface.md#experimental-room-v4-animations).
  Because playback, speed (`0.25...2`), and replay intervals (`0...3600` s) are
  marked experimental, keep this opt-in, translate `animationTitles`, and test
  all motion switches on device.
- **Illuminated surfaces (`illuminatedEntities`, 1.2.1+):** attach static wall
  or cove-wash subtrees to a `luminaireGroups` entry without making those wall
  meshes switchable themselves; see the
  [field reference](https://enterlocus.com/reference/locus-asset-format/#room-illuminated-surfaces-and-view-forward-yaw-formatversion-8).
