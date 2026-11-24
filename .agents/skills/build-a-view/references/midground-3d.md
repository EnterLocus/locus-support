# 3D midground, large-scale worlds, and flowing water

Covers `midground` USDZ scenery (`1.2.1+`), large-scale `skyRadiusMeters`
(`80..1600`, Locus 1.6.0+ / protocol `1.5.1+`), dynamic midground capabilities
(`windSway`, `wavelengthMeters`, `textureFlow`, `skyEntities`, `flowingWater`),
and midground `ambientAnimations` / `interactiveStates` (Locus 1.6.0+ /
protocol `1.5.2+`). See the public
[field reference](https://enterlocus.com/reference/locus-asset-format/).

## Coordinate contract, USDZ packaging, and budgets

- Export one self-contained `midground.usdz` in meters (`metersPerUnit = 1`,
  `upAxis = "Y"`), `-Z` forward, with origin `(0, 0, 0)` at the View ground
  level under a Room's first seat.
- **Blender-to-USD axis mapping**: Blender `(bx, by, bz)` exports to `+Y`-up
  USD / RealityKit `(rx, ry, rz) = (bx, bz, -by)` (Blender `+Y` becomes `-Z`
  forward; runtime `(rx, ry, rz)` corresponds to Blender `(rx, -rz, ry)`).
- **USDZ archive rules**: include a root `.usd`/`.usda`/`.usdc` layer, store
  every member **uncompressed (`ZIP_STORED`)** with 64-byte alignment
  (`pxr.UsdUtils.CreateNewUsdzPackage` handles this automatically), avoid USD
  native instances (`instanceable = true`), procedural primitives
  (`PointInstancer`, `Sphere`, `Capsule`, `Cylinder`, `Cone`), and time-sampled
  topology, and verify with `xcrun usdchecker --arkit midground.usdz`.
- **Coplanar z-fighting audit**: inspect the exported USDZ for overlapping
  coplanar triangles with Blender before packaging:
  ```sh
  blender -b --python tools/audit_coplanar_surfaces.py -- --usdz midground.usdz --json coplanar-report.json
  ```
- Keep all geometry inside the sky sphere with margin: `<= 76 m` at the default
  `80 m` radius, or up to the authored `skyRadiusMeters` (`80..1600` m, Locus
  1.6.0+ / protocol `minimumAppVersion >= "1.5.1"`, capability
  `locus.view.sky-radius.v1`; incompatible with `celestial`, `nearOrbit`, and
  `blackHole`). For large-scale coastal or landscape worlds
  (`skyRadiusMeters: 1600`), keep near land and interactive props close, model
  3D headlands/ridges out to hundreds of meters, use lightweight distant-impostor
  or 3D-baked horizon silhouettes where helpful, and keep the outer `2:1`
  panorama as distant sky/horizon only.
- Declare ground unit names in `terrainEntities` and separate prop units
  outside `terrainEntities`.

## Room compatibility and lighting

Rooms grade `terrainEntities` and hide overlapping non-terrain units using
`viewGroundFloorOffsetMeters`, `viewGroundKeepOut` (default `true`), and
`viewGroundFootprint` (`tools/view_ground_footprint.py`). Room
`viewMidgroundVisibility` (`terrainOnly`/`hidden`) is **deprecated** for new
Rooms because large-scale (`skyRadiusMeters: 1600`) Views keep all of their
land in `midground.path` rather than the panorama:

- **Flat keep-out pad** (e.g. `destination.cloud-garden-isles`): reserve a flat
  empty pad around the origin large enough for expected Rooms.
- **Hideable prop units** (e.g. `destination.ancient-forest`): split props into
  many small independent units with tight bounding boxes so Rooms hide only
  overlapping units.
- **Self-sufficient panorama (for 80 m Views)**: ensure the `2:1` panorama
  reads cleanly on its own if a legacy Room hides the midground.
- **Lighting & alpha-cutout foliage (`1.5.2+`)**: Room `directSun` shadow
  frustums fit the Room only, not midground geometry. Bake gentle shading into
  texture/vertex color for static Views, or pair with `environment.sunPath.light`
  (`"midground": true`, `1.4.9+`) for 24-hour sunlight response. For thin foliage
  cards and horizon standees, export `UsdPreviewSurface` with
  `inputs:opacityThreshold = 0.5` (`> 0`) and `uniform bool doubleSided = 1`:
  under `sunPath.light.midground: true`, Locus 1.6.0+ (`1.5.2+`) automatically
  upgrades those materials to two-sided hardware alpha-cutout shading with full
  24-hour solar and ambient lighting.

## Large-scale 4-layer parallax, terrain, geology, and GPU/VRAM craft

Practical lessons distilled from building large coastal, alpine, and stylized
3D midground Views:

- **4-layer distance architecture (`skyRadiusMeters: 1600`)**:
  Visitor locomotion (`Glide` / `Move`) stays within a playable envelope of
  roughly `60 m` horizontal radius and `+45 m` altitude (or Room bounds + margin).
  Partition geometry around that envelope so visitors never walk into or peek
  behind flat cards:
  1. **Zone 1 & 2 (`0 .. < 150 m`) — 100% real 3D**: watertight multi-zone
     terrain (`terrainEntities`), 3D trees, foliage, boulders, driftwood, and
     bluffs. **Never place 2D cutout standee billboards inside `< 150 m`.**
  2. **Zone 3 (`>= 150 m`, e.g. `172–288 m`) — mid-field standees & outer
     landforms**: curved multi-rank tree-line standee strips and distant islets,
     giving crisp multi-layer parallax against the far skybox when rising to
     `+25..+45 m`.
  3. **Zone 4 (`skyRadiusMeters: 1600`) — far-only 2:1 panorama**: distant
     mountain peaks, sky, and open horizon water — stripped of foreground trees,
     beaches, near stacks, and painted sun discs.
- **3D-baked standees (never crop-upscale from a panorama)**:
  Cropping and upscaling slices from a 12K panorama for standees produces
  blockiness, bright cutout halos, and cloned silhouettes at elevated viewpoints.
  Instead, render transparent strips (`2048×512`–`4096×1024`) in headless
  Blender directly from the **same** 3D tree species used in the foreground
  (hundreds of instances staggered across 4–5 depth ranks plus a dark interior
  core closing sky slits), curve stacked bands outward with progressive
  atmospheric Rayleigh haze, and tuck flank endpoints underground behind 3D
  headlands so side views never show floating strip edges. Remove offshore islet
  cards that fail visual scrutiny rather than leaving unconvincing cutouts.
- **Natural landform vs circular platforms**:
  Avoid floating round "stage" pads. Measure landmark elevation angles from the
  panorama (near ridge lips, rear knolls) alongside expected Room footprints,
  then sculpt continuous terrain with natural erosion and fall-line gullies:
  - Let the rear 3D skyline cover the panorama's near ridge/knoll with a small
    positive margin so movement never reveals a double silhouette.
  - Keep the front brow as low as the Room footprint permits so valleys and
    vistas open up naturally; keep terrain just outside the Room footprint at or
    below the Room floor so Room grading never carves a visible ring-cut.
  - Submerge outer terrain flanks and behind-ridge shoulders below sea level or
    the panorama horizon so `+45 m` overlooks never expose cut mesh cliffs.
  - Wrap bay/coastal midground continuously around the entire shoreline (left
    and right wings plus rear beach), not just the forward cone, and keep
    Room-adjacent terrain mesh chunks moderate (e.g. `<= 32 m` spans).
- **Anti-tiling textures & seamless zone transitions**:
  Large sand, grass, or turf surfaces tiled naively show obvious repetition, and
  hard boundaries between sand, grass, and forest floor look artificial. Use
  large seamless scans with world-space UV phase variation, contour-aligned wide
  opacity-fade blend strips (e.g. `~3 m` fade or quintic Eikonal strips),
  world-mapped baked canopy ambient occlusion on upland forest humus, and clean
  8-bit linear tangent-space normal PNGs (containing only `IHDR`/`IDAT`/`IEND`
  chunks).
- **Photogrammetry rock skirt-ratio audit**:
  Before placing scanned boulders in shallow water, wet sand, or bare spits,
  measure the mesh's base-to-mid footprint width ratio (`w_low / w_mid`). Scanned
  rocks with wide flat dirt/moss plinth skirts (`w_low / w_mid > 1.35`) look
  pasted-on over sand or water — restrict them to deep inland forest humus
  (sunk slightly into the ground) and place only closed, inward-tapered bare
  rocks (`<= 1.1–1.35`) along beaches and intertidal coastlines.
- **Foliage diversity, distance-graded LOD & GPU texture VRAM discipline**:
  Repeating one tree model reads like an early-2000s game. Mix multiple scanned
  age/size variations, broadleaf accents, weathered snags/driftwood, understory
  ferns/shrubs, and root-pivoted `windSway` grasses in the hero zone
  (`r < 95 m`, tight individual bounds for clean Room keep-out), and
  sector-batch upland canopy (`95..148 m`). Keep `midground.usdz` within hard
  budgets (`<= 195 MiB`, `<= 1,650,000` triangles, flattened `.usda <= 256 MiB`)
  and **watch uncompressed GPU texture VRAM** so the View stays smooth alongside
  large Rooms on Apple Vision Pro:
  - Cap terrain albedos around `1536–2048²`, terrain normals around `768–1024²`
    (renormalize unit vectors after downscaling), distant standees around
    `2048×512`, and foliage/prop textures around `512²` (bringing total
    uncompressed RGBA+mips from ~800 MB down to ~185 MB on complex forests).
  - Always downscale RGBA alpha-cutout foliage textures using
    **premultiplied-safe alpha resizing + 3–4 px RGB edge color dilation** into
    transparent texels so mipmaps never bleed dark halos around needles or
    leaves.
  - On dense mid-range forests (`40–110 m`), thin redundant interior overlapping
    foliage cards while preserving crown-top silhouettes to cut alpha-test
    overdraw without thinning the skyline.
- **Stylized / low-poly Views**:
  Aim for clean sculptural massing rather than noisy, overly triangulated
  ground, and compose the 16:9 `thumbnail.jpg` so the stylized identity reads
  immediately on the Places card.

## Dynamic midground capabilities

- `skyEntities` (`1.4.6+`): `1..16` disjoint non-terrain unit prefixes anchored
  in the sky-local frame so distant 3D landmarks stay aligned with the panorama
  when a Room adjusts View-ground height.
- `windSway` (`1.2.1+`): rigid tilt per matched non-terrain prefix about each
  unit's own origin (`amplitudeDegrees` `0..15`, `periodSeconds` `0.5..30`,
  `directionDegrees` `-360..360`). Add `wavelengthMeters` (`1..200`, `1.3.4+`)
  for rolling gust waves across grass/plant clumps with root pivots (see
  `destination.moonlit-silvergrass-ridge`).
- `textureFlow` (`1.4.5+`): `1..16` entries (`{"entities": [...], "uvVelocity": [u, v]}`)
  scrolling repeating `UsdPreviewSurface` textures (`uvVelocity` in `-2..2`, not
  both `0`; `[0, -v]` flows downward on upright textures; e.g.
  `destination.jungle-terraces`).
- `flowingWater` (`1.4.9+`): `1..16` entries for static waterfall/stream meshes
  (disjoint from `textureFlow` and `terrainEntities`, total USD vertex count
  bounded cleanly, optional `whiteness` `0..1.5`, `color` `[r, g, b]`,
  `ripple` `0..1`, `speed` `0.25..2`, `brightness` `0..4`, `mist` `0..2`,
  `spray` `0..2`, `shells` `0..2`, and up to `8` `plunges` per entry
  `{"position": [x, y, z], "width": 0.2..20, "height": 0.3..30, "yawDegrees": -360..360}`;
  excluded by `sunPath.daySky`):
  ```json
  {
    "flowingWater": [
      {
        "entities": ["Waterfall_Main"],
        "whiteness": 1.0,
        "speed": 1.0,
        "brightness": 1.0,
        "mist": 1.0,
        "spray": 1.0,
        "shells": 1,
        "plunges": [
          {"position": [0.0, 0.2, -12.0], "width": 2.4, "height": 1.8, "yawDegrees": 0}
        ]
      }
    ]
  }
  ```
  - **Vertex attributes along downstream arc length `s`** (local slope angle `theta`):
    - Integrate flow speed `v` (m/s) downstream with acceleration `0.7 * 9.81 * sin(theta)`
      relaxing toward `1.0 m/s` at `4.0 /s`, keeping `v >= 0.5 m/s`.
    - `primvars:st` (`TexCoord2fArray`): `(acrossMeters, tauSeconds)` where
      `acrossMeters` spans width in meters across the ribbon and
      `tauSeconds = integral(ds / v)` starts at `0` at the head and strictly
      increases downstream.
    - `primvars:displayColor` (`Color3fArray`): `(white, steep, edge)` in `0..1`
      where `steep = smoothstep(0.25, 0.85, sin(theta))`,
      `white = max(smoothstep(1.4, 2.9, v), prev_white - max(dt / 3.0, ds / 5.0))`,
      and `edge` ramps `0` at side banks to `1` ~`1 m` inward.
    - Author outward `normals` and a plain dark-water `UsdPreviewSurface`
      fallback.
  - **Blender `pxr` post-export fix (must remove `:indices`)**: Blender exports
    UVs and color attributes as `faceVarying` with `:indices` arrays. Run this
    with Blender's bundled Python `pxr` after exporting `.usdc`/`.usda`, then
    repackage into `.usdz`:
    ```python
    from pathlib import Path
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdUtils, Vt

    stage = Usd.Stage.Open("midground_raw.usdc")
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh) and prim.GetName().startswith("Waterfall_Main"):
            mesh = UsdGeom.Mesh(prim)
            mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
            api = UsdGeom.PrimvarsAPI(prim)
            for name, vtype, vals in (
                ("st", Sdf.ValueTypeNames.TexCoord2fArray, Vt.Vec2fArray([Gf.Vec2f(*uv) for uv in vertex_uvs])),
                ("displayColor", Sdf.ValueTypeNames.Color3fArray, Vt.Vec3fArray([Gf.Vec3f(*c) for c in vertex_colors])),
            ):
                pv = api.CreatePrimvar(name, vtype, UsdGeom.Tokens.vertex)
                pv.Set(vals)
                prim.RemoveProperty(f"primvars:{name}:indices")
    stage.GetRootLayer().Save()
    UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath("midground_raw.usdc"), "midground.usdz")
    ```
    Validate with `tools/validate_locusplace.py`.

## View midground animations (`ambientAnimations`, Locus 1.6.0+ / protocol `1.5.2+`)

Add an optional non-empty top-level `ambientAnimations` array to
`destination.json` when a View's `midground.path` USDZ carries independently
playable skeletal or transform animation loops (for example swaying chimes,
drifting boats, turning windmills, or gentle wildlife motion). Set
`minimumAppVersion >= "1.5.2"` in `locusplace.json` (Library capability
`locus.view.ambient-animations.v1` alongside `locus.view.midground.v1`).

```json
{
  "midground": {
    "path": "midground.usdz",
    "terrainEntities": ["Terrain_Shore"]
  },
  "ambientAnimations": [
    {
      "id": "windmill-blades",
      "displayName": "Windmill Blades",
      "entityName": "Midground_Windmill_Rotor",
      "animationName": "Rotor_Spin",
      "isEnabledByDefault": true,
      "defaultSpeed": 1.0,
      "speedRange": [0.25, 2.0],
      "defaultIntervalRangeSeconds": [0.0, 0.0],
      "intervalRangeSeconds": [0.0, 60.0]
    }
  ],
  "localizations": {
    "zh-Hans": {
      "animationTitles": {
        "windmill-blades": "风车叶片"
      }
    }
  }
}
```

- **Blender & USDZ export rules:** Author the animation clip cleanly on a
  dedicated named object/subtree inside `midground.usdz`, verify that
  `entityName` resolves to one unique prim and `animationName` resolves on its
  USDZ subtree at load/import preflight, and keep the animated subtree disjoint
  from `midground.terrainEntities` and from any `interactiveStates` pose entity.
  Avoid USD native instances (`instanceable = true`) and time-sampled topology.
- **Intervals:** `defaultIntervalRangeSeconds` defaults to `[0, 0]` (continuous
  looping) and `intervalRangeSeconds` defaults to `[0, 60]`. Use a non-zero
  interval range for occasional accents (for example passing birds or jumping
  koi) so playback rests between cycles.
- **Room composition & keep-out:** Compatible with `midground.skyEntities`.
  Animated midground subtrees bypass static-prop keep-out (`keepsOut`) and Room
  floor-target occlusion, and remain retained even if a legacy Room sets the
  deprecated `viewMidgroundVisibility` to `"terrainOnly"` or `"hidden"`.
- **Visitor controls & motion gate:** Declaring `ambientAnimations` marks the
  View as an **Animated View**. Playback runs only while the View's Animated
  View switch is on, the app is foregrounded, system Reduce Motion is off, and
  the animation's own **Enabled** toggle is on. Visitors adjust **Enabled**,
  **Speed**, and **Interval** in **Current Place**, **Settings**, and **Edit
  View**. Explicit JSON `null` and empty arrays are rejected.

## View interactive items (`interactiveStates`, Locus 1.6.0+ / protocol `1.5.2+`)

Add an optional top-level `interactiveStates` array (`1..16` controls, `2..8`
states each) to `destination.json` when a View's `midground.path` USDZ includes
props visitors can gaze at and pinch or switch from UI—such as garden gates,
bridge lanterns, dock beacons, shutters, or multi-stage mechanisms. Set
`minimumAppVersion >= "1.5.2"` in `locusplace.json` (Library capability
`locus.view.interactive-states.v1` alongside `locus.view.midground.v1`).

Each control follows the same `poses`, `keyframes`, `fromStateIDs`, and
`emissives` schema as Room `interactiveStates`
(`schemas/room-interactive-states-v1.schema.json`), **except
`states[].particleEffects` is unsupported on Views**:

```json
{
  "midground": {
    "path": "midground.usdz",
    "terrainEntities": ["Terrain_Shore"]
  },
  "interactiveStates": [
    {
      "id": "dock-lantern",
      "displayName": "Dock Lantern",
      "kind": "mechanism",
      "targetEntities": ["DockLantern_Frame", "DockLantern_Post"],
      "defaultStateID": "warm",
      "states": [
        {
          "id": "off",
          "displayName": "Off",
          "emissives": [{"entityName": "DockLantern_Core", "scale": 0.0}]
        },
        {
          "id": "warm",
          "displayName": "Warm",
          "emissives": [{"entityName": "DockLantern_Core", "scale": 1.0}]
        },
        {
          "id": "beacon",
          "displayName": "Beacon",
          "poses": [
            {
              "entityName": "DockLantern_Hood",
              "rotation": {"axis": [0, 1, 0], "angleDegrees": 35},
              "durationSeconds": 0.5,
              "timing": "easeInOut"
            }
          ],
          "emissives": [{"entityName": "DockLantern_Core", "scale": 2.2}]
        }
      ]
    }
  ],
  "localizations": {
    "zh-Hans": {
      "interactiveTitles": {
        "dock-lantern": "码头提灯",
        "dock-lantern.off": "关闭",
        "dock-lantern.warm": "柔光",
        "dock-lantern.beacon": "强光"
      }
    }
  }
}
```

- **Coordinate space & pivots:** `poses[].translationMeters` and
  `poses[].rotation.axis` are evaluated in exported USD / RealityKit **+Y up,
  -Z forward** space relative to each entity's rest transform under its parent:
  Blender `(+X, +Y, +Z)` maps to USD `(+X, -Z, +Y)` (rotations around Blender
  `X/Y/Z` map to USD `[1, 0, 0]`, `[0, 0, -1]`, `[0, 1, 0]`). Place each
  rotating or sliding part's Blender origin at its mechanical pivot.
- **Disjointness & hit targets:** Every `targetEntities`, `poses[].entityName`,
  and `emissives[].entityName` must resolve inside `midground.path` and stay
  disjoint from `midground.terrainEntities`. Pose entities must stay disjoint
  (no overlap or shared USD ancestry) from `ambientAnimations`. Target entities
  (`1..16` per control, pairwise disjoint across controls) must bear renderable
  meshes; avoid targeting large clear glass panes that block the vista behind
  them. Every `emissives[].entityName` must carry a positive authored
  `PhysicallyBasedMaterial` emission (`Emission Color > 0` and
  `Emission Strength > 0`) in USDZ, scaled to `0.0` in `"off"` states.
- **Room composition & visitor interaction:** Compatible with
  `midground.skyEntities`, bypasses static-prop keep-out (`keepsOut`) and Room
  floor-target occlusion, and remains visible under legacy Rooms that set
  `viewMidgroundVisibility`. Works in both **Virtual Space** and **Room
  Portal**: gazing at and pinching any `targetEntities` mesh cycles through
  `states[]` (`(index + 1) % count`), and **Current Place** / **Edit View**
  expose direct state pill buttons (persisting non-default choices and snapping
  initial state without transition animation; live changes respect Animated
  View / Reduce Motion). Unlike `ambientAnimations`, `interactiveStates` does
  **not** mark a View as continuously animated.
- **Validate against Locus 1.6.0:**
  ```sh
  python3 tools/pack_locusplace.py --current-app-version 1.6.0 /abs/path/to/MyViewSrc /abs/path/to/MyView.locusplace
  python3 tools/validate_locusplace.py --current-app-version 1.6.0 /abs/path/to/MyView.locusplace
  ```

## Downloadable Blender source examples

Check `data/place-examples.json` for downloadable `midground` Views with
editable Blender 5.2 source bundles (`LicenseRef-EnterLocus-Example`):
`destination.cloud-garden-isles`, `destination.ancient-forest`,
`destination.jungle-terraces`, `destination.moonlit-silvergrass-ridge`, and
`destination.chalk-dune-dawn`.
