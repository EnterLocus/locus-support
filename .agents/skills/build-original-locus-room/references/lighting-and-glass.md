# Baked lighting, luminaire groups, and architectural glass

Use this reference as part of building any lit Room—from planning luminaire
groups in the brief through baking per-lamp irradiance layers in headless
Blender, auditing photometry, and exporting clear architectural glazing. It is
self-contained and uses ordinary Blender/USD concepts plus the public Room
interface and bundled scripts (`../scripts/bake_irradiance.py` and
`../scripts/audit_lighting_photometry.py`).

## 1. Design semantic luminaire groups before modeling fixtures

Plan how a visitor will switch the lights before placing emitters. In Locus,
each entry in `lighting.luminaireGroups` is one logical switch with its own EV,
temperature, and optional color controls—and pinching any member toggles its
group.

- **Group by mood layer, not room quadrant.** Separate primary overheads
  (`overheads`, `chandelier`) from small mood layers (`accent`, `task`, `cove`)
  and outdoor circuits (`outdoor`). Turning off overheads should drop room-wide
  median luminance cleanly (at least ~65% / ~1.5 EV) so desk lamps, floor
  lamps, sconces, and cove strips create a warm evening atmosphere.
- **Keep colored lights in their own group.** Runtime tints untextured glows
  to the group's color, so never merge a cyan pool light or colored accent into
  a warm-white interior circuit. Keep color temperatures within ~600 K inside
  any single warm group.
- **Prefer baked layers over real-time proxies.** Real-time proxies are
  budgeted per seat and scoped by `nearTeleportIDs`, so a proxy's pool vanishes
  from other seats, and shadow-casting proxies are expensive on Apple Vision
  Pro. Bake each independently controlled group into its own
  `lighting.bakedIndirect.layers` image instead: a baked layer follows its
  group's switch, EV, temperature, and color from every seat at zero per-frame
  shadow cost. Do not double-count the same direct pool with both a baked layer
  and a real-time proxy.
- **Keep each layer role distinct.** An emissive fixture body
  (`luminaireGroups[].entities`) makes the lamp itself visible; a baked
  receiver layer (`lighting.bakedIndirect.layers`) lights walls, floors,
  ceilings, and furniture; `illuminatedEntities` is only a secondary option for
  authored emissive washes, never a substitute for a baked receiver atlas.
- **Model physically believable fixtures with open light paths.** Connect
  shades, arms, mounts, and cords cleanly. Delete end caps on cylindrical/cone
  lamp shades (a capped shade traps its bulb), leave clearance below bulbs, and
  offset inner shade linings by at least 2 cm so coplanar faces do not flicker.
  For shaded floor, table, or reading lamps, bake with directional spots (a
  downward cone plus a weak upward bounce spot), never a bare omnidirectional
  point light that washes out the whole room. For linear cove/shelf strips,
  bake with rectangular `AREA` lights or emissive strip meshes rather than
  spotlights. Keep close-range task lamps moderate (typically `<= 300 lm`) so
  tabletops do not blow out.

## 2. Bake per-lamp irradiance layers (`mode: "irradiance"`, Locus 1.6.0+ / protocol `1.5.2+`)

**Default to `mode: "irradiance"`** (`minimumAppVersion: "1.5.2"` in
`locusplace.json`, keeping Package v2 `space.json` at `formatVersion: 2`; flat
compatibility ZIPs use `formatVersion: 14`, never copy `14` into Package v2).

With legacy `mode: "radiance"`, surface albedo is baked into `LocusIndirectUV`
(`UV1`), which limits texture sharpness under Room Lights to the lightmap's
texels per meter (~35–60 texels/m on multi-room interiors) and blurs stone,
wood grain, rugs, and woven upholstery. With **`mode: "irradiance"`**, Cycles
bakes pure incoming diffuse irradiance (`include_color=False`) normalized by
one shared HDR `irradianceScale` (`(0, 64]`, 16-bit sRGB PNG required when
`> 1`), and Locus multiplies `irradiance(UV1) * baseColor(UV0) * (1 - metallic)
* ao` at runtime in an `rgba16Float` GPU texture—preserving 100% of `UV0`
(`st`) texture sharpness, normal maps, and roughness.

```json
"lighting": {
  "luminaireGroups": [
    {"id": "overheads", "displayName": "Ceiling Lights", "entities": ["Can_Glow_01", "Can_Glow_02"]},
    {"id": "desk-lamp", "displayName": "Desk Lamp", "entities": ["Desk_Lamp_Glow"]}
  ],
  "bakedIndirect": {
    "entities": ["Locus_BakedIndirect", "Work_Desk_Top"],
    "mode": "irradiance",
    "irradianceScale": 4.5,
    "layers": [
      {"luminaireGroupID": "overheads", "image": "light-overheads.png"},
      {"luminaireGroupID": "desk-lamp", "image": "light-desk-lamp.png"}
    ]
  }
}
```

Single-atlas Rooms without per-lamp controls can also use `mode: "irradiance"`
with `"image": "baked-irradiance.png"` instead of `layers` so master/overall EV
still preserves `UV0` sharpness.

### Step-by-step irradiance baking workflow

1. **Choose opaque receivers deliberately.** Include lit interior and terrace
   surfaces that should visibly respond to lamps: floors, walls, ceilings,
   stairs, hearths, rugs, artwork, non-metallic furniture, desk props, and
   indoor plants. Exclude glass, water, visible luminaire glow bodies, pure
   metals (`metallic == 1` has zero diffuse response), exterior roof/site
   shells, and moving `interactiveStates` parts. Receivers inside a Hide Desk
   group (or a bound TV screen) stay under their own parent and are named
   directly in `bakedIndirect.entities` alongside `Locus_BakedIndirect`.
2. **Prepare `st` (`UV0`), `LocusIndirectUV` (`UV1`), tangents, and deduplicated materials.**
   - Name every receiver's base PBR UV layer **`st`** and keep it as
     `active_render` so implicit material texture coordinates never sample the
     lightmap UV. Every `bakedIndirect` receiver mesh must export both `st`
     (`UV0`), non-overlapping `LocusIndirectUV` (`UV1` in `[0, 1]`), and mesh
     tangents.
   - Because `mode: "irradiance"` only resolves smooth lighting gradients and
     soft shadows, `1024×1024` or `2048×1024` / `2048×2048` (~35–90 texels/m)
     is sufficient for most Rooms and keeps resident Float16 RAM low (each
     layer uses `width × height × 8` bytes, e.g. `16 MiB` at `2048×1024`,
     `64 MiB` at `4096×2048`).
   - Pack one rectangular block per receiver with a skyline packer and a 16 px
     block gutter so mipmaps never bleed between neighbors. For sculpted or
     generated furniture props, preserve their clean source UV charts instead
     of re-shattering them with Smart UV Project, and give them higher area
     weight so small curved faces do not facet at night.
   - **Deduplicate indirect materials per base material** (for example
     `<BaseMat>__LocusIndirect__shared`) instead of cloning one material per
     object slot, preventing shader and memory bloat in multi-room scenes.
3. **Never divide old `radiance` PNGs by `baseColor` offline.** Existing baked
   radiance pixels already convolved tiled `UV0` texels, filtering, and sRGB
   clamping; dividing dark stone or wood veins amplifies noise and cannot
   recover clipped highlights. Always rebake from the editable `.blend` source.
4. **Bake each group in isolation with sharp direct + low-passed bounce.**
   - Keep the bake target in scene-linear float (`float_buffer=True`,
     `Linear Rec.709`), fixed deterministic sampling (`use_adaptive_sampling =
     False`, `seed = 0`, `use_animated_seed = False`), and preview World/sun
     lighting off (`Strength = 0`). Unlink any existing
     `Locus_BakedIndirect_Texture -> Emission Color` wire while baking so
     Cycles never reads a circular dependency.
   - Disable shadow casting on architectural glass during artificial bakes and
     hide non-active luminaire meshes so glass frames and inactive shades do
     not corrupt the bounce.
   - For each group, enable only that group's baking lights (at authored power,
     never floored to a proxy minimum) and mesh emitters. Bake
     **`use_pass_direct = True, use_pass_indirect = False`** (sharp direct
     pools and contact shadows) and **`use_pass_direct = False,
     use_pass_indirect = True`** (smooth bounce, low-passed in linear float
     with two radius-4 separable box passes inside an 8 px bake margin) with
     `use_pass_color = False`, then sum both linear-float arrays.
   - **Watch secondary-bounce albedo inflation.** When using a temporary
     unit-white diffuse proxy to bake albedo-free irradiance, multi-bounce rays
     reflecting off `1.0` white walls carry more energy than a real ~0.3–0.5
     albedo interior. Either keep real surface albedo on secondary bounces
     (via a Cycles `Light Path` ray-depth switch) or calibrate a shared
     `layerScale` against the Room's accepted `0 EV` night exposure.
5. **Compute one shared `irradianceScale` and encode 16-bit sRGB PNGs once.**
   - Sum all baked groups in linear float and pick one shared
     `irradianceScale` across every layer covering the composite peak
     (`ceil(peak * 1.02)` up to `64.0`) so **`0%` of texels clip**—never
     normalize each layer independently, which destroys lamp brightness ratios.
   - Encode each layer as `sRGB(clamp(linearIrradiance / irradianceScale, 0,
     1))` through an isolated Standard/sRGB save scene (no look, exposure 0,
     gamma 1, dither 0) using `image.save_render(path, scene=...)` with
     `file_format="PNG"`, `color_mode="RGB"`, `color_depth="16"`. `Image.save()`
     does not honor PNG bit-depth settings in Blender 5.2; verify the actual
     saved PNG bit depth.
   - Bake one fast 24-sample material-colored (`use_pass_color = True`)
     radiance composite for `scene.usdz`'s `emissiveColor` (`UV1`) at
     `Emission Strength = 1.0` so standalone Quick Look and fallback previews
     still look balanced. Always snapshot and restore `scene.cycles` (such as
     `transmission_bounces`) before saving `.blend` or rendering review frames.
6. **Verify exported USDZ bindings and run the bundled baker + photometry audit.**
   - Use the bundled standalone script for new Rooms or rebakes:

   ```sh
   # 1. Lint semantic groups, emitter types, and Float16 RAM budget before baking
   python3 .agents/skills/build-original-locus-room/scripts/bake_irradiance.py \
     --output-root /abs/path/to/work --config /abs/path/to/bake-config.json \
     --validate-config-only

   # 2. Run headless Cycles v14 irradiance baking (outputs LightLayers/*.png + bake-audit.json)
   blender --background --factory-startup --python-exit-code 1 \
     --python .agents/skills/build-original-locus-room/scripts/bake_irradiance.py -- \
     --output-root /abs/path/to/work --config /abs/path/to/bake-config.json \
     --width 2048 --height 1024 --direct-samples 96 --indirect-samples 128
   ```

   - After exporting `scene.usdz`, verify that base PBR textures bind to `st`,
     the indirect `UsdPrimvarReader_float2` binds to `LocusIndirectUV` (Blender
     5.2 can export the second primvar yet leave its reader pointing at `st`),
     and the packaged emission PNG is declared sRGB with `Emission Strength = 1`.
   - When rendering Cycles night review frames from the baked `.blend`, set
     receiver material `emission_sampling = "NONE"` with zero bounces—otherwise
     Cycles lets emissive receivers illuminate neighboring walls, which
     RealityKit never does.
   - Place every layer PNG at the Room package root (matching `bakedIndirect.layers[].image`
     1-to-1, identical dimensions `<= 4096×4096`, 16-bit RGB/RGBA PNG when
     `irradianceScale > 1`) and run the photometry audit alongside the standard
     package gates:

   ```sh
   python3 .agents/skills/build-original-locus-room/scripts/audit_lighting_photometry.py \
     /abs/path/to/MyRoom.locusplace
   python3 tools/validate_locusplace.py --current-app-version 1.6.0 \
     /abs/path/to/MyRoom.locusplace
   python3 tools/check_room.py --current-app-version 1.6.0 \
     --renders /abs/path/to/empty-room-renders \
     /abs/path/to/MyRoom.locusplace
   ```

### Declarative `bake-config.json` shape

```json
{
  "rootName": "ExampleRoom_ROOT",
  "blendName": "room.blend",
  "manifestName": "space.json",
  "scale": "standard",
  "layerScale": 1.0,
  "excludedEntities": ["Window_Glass_North"],
  "deskGroups": ["Work_Desk_Group"],
  "lightGroups": [
    {
      "id": "overheads",
      "role": "overheads",
      "bakedLayer": true,
      "fixtures": [
        {
          "id": "can-01",
          "kind": "downlight",
          "emitterType": "spot",
          "position": [0.0, 2.75, -1.2],
          "rotationEuler": [0.0, 0.0, 0.0],
          "lumens": 450,
          "kelvin": 2900,
          "spotDegrees": 95,
          "blend": 0.65
        }
      ]
    },
    {
      "id": "desk-lamp",
      "role": "task",
      "bakedLayer": true,
      "fixtures": [
        {
          "id": "desk-01",
          "kind": "desk_lamp",
          "emitterType": "spot",
          "position": [-0.4, 1.15, -1.8],
          "rotationEuler": [0.15, 0.0, 0.0],
          "lumens": 220,
          "kelvin": 2700,
          "spotDegrees": 80,
          "blend": 0.55
        }
      ]
    }
  ]
}
```

Valid `role` values are `overheads`, `chandelier`, `accent`, `task`, `cove`,
`outdoor`, and `decorative`. Pass `--reuse-existing-uv --keep-blend-atlas` when
rebaking light layers onto an unchanged `scene.usdz` whose `LocusIndirectUV`
and Quick Look fallback atlas are already verified.

## 3. Check transmissive glass and clearcoat roughness in the exact USDZ

### Exported transmission

In Blender 5.2 USD PreviewSurface export, lowering Principled Alpha alone can
still export opaque glass because the Transmission Weight mapping also writes
USD opacity. For scalar transmissive glazing in this path, keep Alpha at `1`,
author the intended Transmission Weight, and inspect exported `inputs:opacity`
(Transmission `0.9` exports opacity about `0.1`). Preserve linked maps,
animation, and intentional coatings. Import the exact USDZ and look through the
panes against a View; USD validity alone does not prove transparency.

### Distinguish base roughness from clearcoat roughness

In visionOS testing, transparent architectural glass with clearcoat strength `0`
and clearcoat roughness `0.03` produced a sun-reflection center artifact (a
colored center in Simulator, a thin gray/dark ring on physical Apple Vision
Pro). Raising only `clearcoatRoughness` (Blender Principled `Coat Roughness`)
to at least **`0.2`** removed the artifact while keeping the surrounding
highlight unchanged.

- Apply `clearcoatRoughness >= 0.2` only to transparent architectural glass
  whose unlinked clearcoat strength is exactly `0` (preserving any higher valid
  value). **Do not change base roughness to `0.2`**; keep the intended base
  roughness (for example `0.02`), opacity, color, and normals.
- Do not apply this workaround to water, opaque surfaces, or intentionally
  coated glass, and do not flatten connected textures or animated inputs into
  constants.
- Update the editable source and verify exported
  `UsdPreviewSurface.inputs:clearcoatRoughness` so future exports never revert.

## 4. Isolate defects and verify on Apple Vision Pro

- **Causal A/B for lighting or glass artifacts:** hold Room, View, seat, sun,
  EV, and app version fixed. Change one parameter in a recoverable copy, verify
  which Room variant is actually loaded, and compare all-off, all-on, and each
  group solo. Never hide blotches, clipping, or glass artifacts by lowering the
  EV ceiling, dimming every lamp, or disabling sunlight.
- **Check both night and day Views:** inspect every affected seat in a dim/night
  View and a daylight View at `0 EV`, `+2 EV`, and `+4 EV` stress (or the app's
  available ceiling). Confirm crisp `UV0` surface textures under Room Lights,
  clean transitions when toggling overheads off into small mood lights, zero
  color patches or mottling, no permanent painted pools when a lamp is off, and
  no double-counted proxy pools. Keep per-light `brightnessEVRange` within
  `[-4, 1]`.
- **Remember what offline checks cannot prove:** `check_room.py` and
  `audit_lighting_photometry.py` validate structure, UV bindings, bit depth,
  clipping, speckle, and mood contrast, but `check_room.py`'s scaffold renderer
  does not composite baked light layers or paired Views. Physical Apple Vision
  Pro review remains required for glare, presence, comfort, and real daylight
  to night transitions.

## 5. Legacy `mode: "radiance"` fallback (untextured Rooms or `< 1.6.0` targets)

Use legacy `mode: "radiance"` (omitting `mode` and `irradianceScale`,
`minimumAppVersion >= "1.2.1"` for per-group `layers` or flat `formatVersion:
10`, or plain v3 single shared atlas for master-only EV) only when targeting
older Locus versions or flat-colored untextured geometry without tiled `UV0`
maps:

- Bake with `use_pass_color = True` in scene-linear float (`float_buffer=True`,
  `Linear Rec.709`) so receiver albedo is included in the emitted layer.
- Keep one shared absolute radiance-to-emission scale across all layers,
  encode 16-bit sRGB PNGs through the isolated Standard/sRGB save scene, keep
  material `Emission Strength = 1.0`, and compose the all-groups-on linear sum
  into `scene.usdz`'s `emissiveColor` (`LocusIndirectUV`).
- Never bake an independently switchable lamp's pool into a single shared v3
  atlas that only responds to Room master/overall EV.

Return to [the Room interface](room-interface.md) for metadata limits and
[the main skill](../SKILL.md) for packaging and handoff.
