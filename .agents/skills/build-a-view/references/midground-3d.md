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
- **Lighting**: Room `directSun` shadow frustums fit the Room only, not
  midground geometry. Bake gentle shading into texture/vertex color for static
  Views, or pair with `environment.sunPath.light` (`"midground": true`,
  `1.4.9+`) for 24-hour sunlight response.

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
- **`ambientAnimations` on Views** (Locus 1.6.0+ / protocol `minimumAppVersion
  >= "1.5.2"`, capability `locus.view.ambient-animations.v1`): optional
  non-empty top-level `destination.json` array driving named skeletal or
  transform clips inside `midground.path` with the same entry schema as Room
  `ambientAnimations` (`id`, `displayName`, `entityName`, `animationName`,
  `isEnabledByDefault`, `defaultSpeed`, `speedRange`, optional
  `defaultIntervalRangeSeconds` and `intervalRangeSeconds`; localized via
  `localizations.<lang>.animationTitles.<id>`). Entities must resolve in
  `midground.path` and stay disjoint from `midground.terrainEntities`; they are
  retained even if a legacy Room sets `viewMidgroundVisibility` to
  `terrainOnly`/`hidden` and bypass static-prop keep-out. Counts as an Animated
  View.
- **`interactiveStates` on Views** (Locus 1.6.0+ / protocol `minimumAppVersion
  >= "1.5.2"`, capability `locus.view.interactive-states.v1`): optional
  top-level `destination.json` array of `1..16` multi-state controls acting on
  `midground.path` props using the same `poses`, `keyframes`, and `emissives`
  schema as Room `interactiveStates` (`schemas/room-interactive-states-v1.schema.json`,
  localized via `localizations.<lang>.interactiveTitles`), **except
  `states[].particleEffects` is unsupported on Views**. All referenced entities
  must resolve in `midground.path` and stay disjoint from `terrainEntities`;
  pose entities must stay disjoint from `ambientAnimations`. Works in both
  Virtual Space and Room Portal via 3D gaze + pinch cycling and **Current Place**
  / **Edit View** state pills; does not mark the View as continuously animated.

## Downloadable Blender source examples

Check `data/place-examples.json` for downloadable `midground` Views with
editable Blender 5.2 source bundles (`LicenseRef-EnterLocus-Example`):
`destination.cloud-garden-isles`, `destination.ancient-forest`,
`destination.jungle-terraces`, `destination.moonlit-silvergrass-ridge`, and
`destination.chalk-dune-dawn`.
