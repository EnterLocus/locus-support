# 3D midground and flowing water

Covers `midground` USDZ scenery (`1.2.1+`) and dynamic midground capabilities
(`windSway`, `wavelengthMeters`, `textureFlow`, `skyEntities`, `flowingWater`).
See the public
[field reference](https://enterlocus.com/reference/locus-asset-format/).

## Coordinate contract and budgets

- Export one self-contained `midground.usdz` in meters, `+Y` up, `-Z` forward,
  with origin `(0, 0, 0)` at the View ground level under a Room's first seat.
- Keep all geometry inside the `80 m` sky sphere with margin (`<= 76 m`), and
  target near land within `~25 m` and props within `~27 m` unless paired with
  known Rooms.
- Declare ground unit names in `terrainEntities` and separate prop units
  outside `terrainEntities`.

## Room compatibility and lighting

Rooms grade `terrainEntities` and hide overlapping non-terrain units using
`viewGroundFloorOffsetMeters`, `viewGroundKeepOut`, or `viewGroundFootprint`
(`tools/view_ground_footprint.py`), and may hide midground completely via
`viewMidgroundVisibility`:

- **Flat keep-out pad** (e.g. `destination.cloud-garden-isles`): reserve a flat
  empty pad around the origin large enough for expected Rooms.
- **Hideable prop units** (e.g. `destination.ancient-forest`): split props into
  many small independent units with tight bounding boxes so Rooms hide only
  overlapping units.
- **Self-sufficient panorama**: ensure the `2:1` panorama reads well on its own
  if a Room hides the midground.
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
  (disjoint from `textureFlow` and `terrainEntities`, `<= 400,000` vertices,
  optional up to 8 `plunges` per entry, excluded by `sunPath.daySky`):
  - Author **vertex-interpolated** `primvars:st` (`texCoord2f[]`:
    `(acrossMeters, tauSeconds)` where `tauSeconds` increases downstream) and
    `primvars:displayColor` (`color3f[]`: `(white, steep, edge)` in `0..1`),
    plus outward `normals` and a plain dark-water `UsdPreviewSurface` fallback.
  - Because Blender writes UVs and color attributes as `faceVarying` by
    default, convert `primvars:st` and `primvars:displayColor` to `vertex`
    interpolation in USD (`pxr`) after exporting and validate with
    `tools/validate_locusplace.py`.

## Downloadable Blender source examples

Check `data/place-examples.json` for downloadable `midground` Views with
editable Blender 5.2 source bundles (`LicenseRef-EnterLocus-Example`):
`destination.cloud-garden-isles`, `destination.ancient-forest`,
`destination.jungle-terraces`, `destination.moonlit-silvergrass-ridge`, and
`destination.chalk-dune-dawn`.
