# Room Interactive States (`interactiveStates`, Locus 1.5.1+)

Use this guide when a Room brief calls for operable doors, windows, motorized
pergola louvers, fireplaces, fire tables, or other multi-stage mechanisms. Every
contract below belongs to **Complete Package v2** (`.locusplace` / `.zip` with
`minimumAppVersion >= "1.5.1"`); the flat compatibility ZIP cannot carry
`interactiveStates`.

Normative references:
- [Complete Package v2 authoring — Room interactive states](https://enterlocus.com/reference/locusplace-format/#room-interactive-states)
- [Field reference — Room interactive states](https://enterlocus.com/reference/locus-asset-format/#room-interactive-states-locus-151-or-later)
- [JSON Schema (`room-interactive-states-v1.schema.json`)](https://enterlocus.com/schemas/room-interactive-states-v1.schema.json)

---

## 1. Visitor Interaction & Authoring `states[]` Order

- **3D gaze + pinch cycles in array order:** Looking at and pinching any entity
  listed in `targetEntities` (in Virtual Space) steps sequentially through
  `states[]` as `(currentIndex + 1) % states.count`. Order `states[]` cleanly
  for one-handed 3D stepping (for example `closed -> breeze -> open`, or
  `off -> embers -> low -> full`).
- **Room Features UI selects directly:** **Current Place › Room Features**
  shows a button grid in the same `states[]` order so the visitor can jump
  straight to any state, preview author defaults (**Try Original Settings**), or
  persist custom choices (**Save for This Room…** / **Revert**). Interactive
  controls are not offered in Room Portal.
- **No magic naming prefixes:** Names like `Slider_Living_A` or
  `Pergola_Louver_00` in examples are clear naming conventions, never required
  prefixes. Runtime binds strictly to the exact USD prim names declared in
  `space.json`.

---

## 2. Blender Z-Up to RealityKit/USD Y-Up Conversion

`poses[].translationMeters` and `poses[].rotation.axis` are evaluated in the
exported USDZ / RealityKit **+Y up, -Z forward** coordinate space, relative to
each entity's rest transform under its parent. When modeling in Blender (**+Z up**),
convert pose vectors as follows before USD export applies its root transform:

| Blender World Axis (Z-up) | Exported USD / RealityKit Axis (Y-up) | Example Pose Value |
|---|---|---|
| `+X` (East / right) | `+X` | Moving `+1.50 m` along `+X` -> `[1.5, 0, 0]` |
| `+Y` (North / forward) | `-Z` | Moving `+1.50 m` along Blender `+Y` -> `[0, 0, -1.5]` |
| `+Z` (Up) | `+Y` | Lifting `+0.008 m` along Blender `+Z` -> `[0, 0.008, 0]` |
| Rotation around Blender X | `axis: [1, 0, 0]` | Right-handed `angleDegrees` around USD `+X` |
| Rotation around Blender Y | `axis: [0, 0, -1]` | Right-handed `angleDegrees` around USD `-Z` |
| Rotation around Blender Z | `axis: [0, 1, 0]` | Right-handed `angleDegrees` around USD `+Y` |

Keep each pivoting or sliding part's origin at its mechanical pivot:
- **Door lever / pull handles:** place the mesh/object origin at the spindle
  center so rotation swings cleanly in place.
- **Motorized louver blades:** place each blade's origin on its longitudinal
  axle so rotation around its local axle axis opens/closes the slat without
  translation drift.
- **Sliding door leaves:** put a parent empty/Xform root at the closed leaf
  resting position containing the frame, pull, and glass child meshes so one
  `translationMeters` vector slides the whole leaf assembly together.

---

## 3. Hierarchy, Lighting Separation, and Hollow Hit Targets

- **Keep interactive parts out of `Locus_BakedIndirect`:** Parent moving leaves,
  handles, louvers, switch plates, grates, and interactive ember/glow meshes
  under the Room root, never inside `lighting.bakedIndirect.entities`.
- **Keep `interactiveStates[].emissives` disjoint from `lighting`:** Interactive
  `emissives[].entityName` entries are strictly forbidden from overlapping or
  sharing USD ancestry with `lighting.luminaireGroups[].entities`,
  `lighting.luminaireGroups[].illuminatedEntities`, or
  `lighting.bakedIndirect.entities`. Give each emissive mesh its own positive
  authored `PhysicallyBasedMaterial` emission in USDZ (`Emission Color > 0` and
  `Emission Strength > 0`), and set `"scale": 0.0` in `"off"` states inside
  `space.json`.
- **Keep clear glass OUT of `targetEntities`:** Never add transparent glass panes
  to `targetEntities`, or looking at the outdoor View through a closed door/window
  will highlight the whole pane and intercept pinches meant for Views/UI. Instead:
  - Keep clear glass as a sibling child mesh under the moving leaf root (so it
    slides with the door).
  - Target the hollow perimeter frame subtree (`Slider_*_Frame` split into
    separate rail/stile child meshes) plus the handle (`Slider_*_Pull`), or a
    dedicated hollow rim/grate/wall switch mesh (`1...16` unique mesh-bearing
    entities per control, pairwise disjoint across controls and disjoint from
    `tvs` and `lighting.luminaireGroups[].entities`).

---

## 4. Fire Emitters (`particleEffects` + `rotateX(+90°)` Rule)

When driving a fireplace or fire table with `particleEffects`:

- Author the emitter anchor in `space.json["particleEffects"]` (`id`,
  `preset: "fire"`, `anchorEntity`, `sizeMeters`) and place its Blender Empty
  **2–4 cm above** the glowing coal/burner mesh so flames never clip under
  opaque fuel geometry.
- **Upward `+Y` in USDZ:** `ParticleEffect` fire rises along the USD entity's
  local `+Y` axis. Because Blender exports Z-up objects with a Y-up conversion,
  set the Blender emitter Empty's Euler rotation to **`(math.pi / 2, 0, 0)`**
  (`+90°` X) and verify on the exported `scene.usdz` that `UsdGeom.XformCache`
  maps local `(0, 1, 0)` to world `(0, +1, 0)`.
- **Zero-GPU off / embers states:** Set `"intensity": 0.0` on `"off"` and
  `"embers"` states. Starting in a zero-intensity default state avoids initial
  GPU flame warmup altogether.

---

## 5. Multi-Stage Choreography (`keyframes`, `fromStateIDs`, `delaySeconds`)

- **Lift-and-slide or latch-then-glide doors:**
  - Opening (`closed -> breeze` or `open`): rotate the handle (`delaySeconds: 0`,
    `durationSeconds: 0.2`) while holding the leaf (`Slider_*`) at
    `translationMeters: [0, 0, 0]` until `{"at": 0.2, "fromStateIDs": ["closed"], "translationMeters": [0, 0, 0]}`.
    Adding `"fromStateIDs": ["closed"]` lets direct transitions between
    `breeze <-> open` glide immediately without re-latching.
  - Closing (`breeze` / `open -> closed`): bring the leaf home by `at: 0.78`
    with `"fromStateIDs": ["breeze", "open"]`, then rotate the handle back with
    `delaySeconds: 0.68`.
- **Staggered louvers (`kind: "louvers"`):** Give consecutive blades increasing
  `delaySeconds` (`0.00, 0.045, ..., 0.405`), and list both the wall switch and
  louvers (up to 16 total `targetEntities`) so visitors can pinch overhead slats
  from lounge seats as well as at the wall switch.

---

## 6. Localization, Validation, and Device Checks

1. Add `localizations.<lang>.interactiveTitles` with keys `"<controlID>"` and
   `"<controlID>.<stateID>"` for every language your Room ships.
2. Set `"minimumAppVersion": "1.5.1"` (or higher) in `locusplace.json`.
3. Pack and validate against `1.5.1`:

```sh
python3 tools/pack_locusplace.py --current-app-version 1.5.1 /abs/path/to/MyRoomSrc /abs/path/to/MyRoom.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.5.1 /abs/path/to/MyRoom.locusplace
python3 tools/check_room.py --current-app-version 1.5.1 --renders /abs/path/to/renders /abs/path/to/MyRoom.locusplace
```

4. On physical Apple Vision Pro (`1.5.1`+), verify gaze highlights trace only
   frames/handles/switches (not clear glass), pinch-cycling visits every state
   in intuitive order, and **Current Place › Room Features** switches, previews,
   and saves defaults cleanly.
