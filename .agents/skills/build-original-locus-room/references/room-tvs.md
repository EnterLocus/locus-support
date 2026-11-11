# Room TVs

Requires Locus 1.4.9 or later.

A Room can declare up to four TVs. Each TV is a flat screen in `scene.usdz`.
In Virtual Space, a visitor looks at a dark screen and pinches to turn it on;
the screen then shows a web page, such as a video site, with a small remote
under it. A page can move between a TV and a Browser window with **Play on
TV** and **Open in Window**. Every TV is off when the visitor arrives. There is
no author setting for a default page or for starting a TV on.

## When to offer a TV

Offer a TV when the brief has a place people would sit and watch: a living
room or media room sofa, a den, a bedroom, a lounge, a bar, or a small cinema.
An art TV suits a wall that would otherwise carry a painting in front of a
seat: its off state is the artwork. Do not add one by default to a Room
centered on desks, a gallery, a chapel, or an open-air terrace unless the
creator asks.

One or two TVs is usual; four is the limit. Ask which seats watch each TV and
roughly what size it should be, and record the answers in the brief and floor
plan.

## Plan the screen with its seats

Plan each TV with the seats that watch it, before modeling.

- **Face the seat.** Point the screen at its main seat. Keep that seat within
  about 30° of the screen's axis; `check_room.py` warns above 45°.
- **Size it by distance.** A comfortable screen spans about 30–40°
  horizontally from the seat: width ≈ 0.55–0.75 × viewing distance.

  | Diagonal | 16:9 screen (W × H) | Viewing distance |
  | ---: | ---: | ---: |
  | 55" | 1.22 × 0.68 m | 1.7–2.3 m |
  | 65" | 1.44 × 0.81 m | 2.0–2.7 m |
  | 75" | 1.66 × 0.93 m | 2.3–3.1 m |
  | 85" | 1.88 × 1.06 m | 2.6–3.5 m |
  | 98" | 2.17 × 1.22 m | 3.0–4.1 m |

- **Keep it near eye level.** Put the screen's center within about 15° above
  the seated eye. An art TV above a fireplace can sit higher; the main TV for a
  sofa should not.
- **Keep the area under it clear.** Locus places the remote just below the
  screen. Leave room in front of the wall there: no tall plants, vases or
  speakers directly under or in front of the screen. A low console is fine.
- **Use a solid wall.** Do not hang a screen across a window or the View
  opening.

Record each TV in the plan: `id`, display name, diagonal, center, facing
direction, and the seats that watch it.

## Model the screen

The screen mesh is the contract. Locus reads the page rectangle from its
bounds and shows its authored material while the TV is off.

- **One flat quad.** Four vertices, two triangles, exactly 16:9, zero
  thickness. Model the bezel, frame and stand as separate objects.
- **Its own object.** Give it a stable, unique name such as
  `TV_Screen_Living`. Never join it into, or parent it under, another entity
  the Room metadata names: a wall, a Hide Desk group, a lamp, the baked
  lighting receiver, an animation, or a video surface.
- **Its own UVs.** Map 0–1 across the whole quad, with u increasing to the
  watcher's right and v upward, so artwork is upright and unmirrored.
- **A non-emissive off state.** Use dark glass (near-black, low roughness,
  not metallic) or, for an art TV, an artwork texture. A TV that is off must
  not glow.
- **No coplanar faces.** Set the screen 2–5 mm in front of its frame and
  wall. A screen flush with the frame flickers; see
  [Flicker prevention](flicker-prevention.md).
- **Keep it out of joined baked lighting.** When you bake indirect light, do
  not merge the screen into the shared receiver, such as `Locus_BakedIndirect`.
  If an art TV's painting must match the baked light around it, bake the
  screen as its own `bakedIndirect.entities` entry instead.

In headless Blender, build the quad directly and keep it a separate object:

```python
import bpy

def add_screen(name, center, width, height, right, normal):
    """center, right and normal are Blender (Z-up) vectors."""
    up = normal.cross(right).normalized()
    corners = [center + right * (u - 0.5) * width + up * (v - 0.5) * height
               for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, coordinate in zip(mesh.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop.index].uv = coordinate
    screen = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(screen)
    return screen
```

Check that the face normal points toward the seat after export; flip the
corner order if it does not.

## Declare the TVs

`tvs` belongs in the Room's Package v2 `space.json`. The flat compatibility
ZIP cannot carry it.

```json
"tvs": [
  {
    "id": "living-tv",
    "displayName": "Living Room TV",
    "entityName": "TV_Screen_Living"
  }
]
```

- `id`: unique, lowercase letters, digits and hyphens, at most 64 bytes. Keep
  it stable across revisions.
- `displayName`: the name in the **Play on TV** menu, at most 200 bytes.
  Translate it with `localizations.<language>.tvTitles`, keyed by `id`.
- `entityName`: the screen object's exact exported name, unique across TVs.
- One to four entries.
- Set `minimumAppVersion` in `locusplace.json` to `1.4.9` or later.

The [Example Media Room](../../../../examples/media-room/README.md) is a
complete, generated Room with two TVs.

## Check before device review

Pack and check with `--current-app-version 1.4.9` or later:

- `tools/validate_locusplace.py` checks the shape, the version floor, and that
  every `entityName` exists in `scene.usdz`. The Room binding check confirms
  each one resolves to geometry and that no TV screen contains another.
- `tools/check_room.py` also checks each screen: one mesh, one flat quad,
  16:9, not nested in or around another named entity, not emissive, and
  facing a seat. Read every `tvScreen…` warning.
- In the renders, look at each TV from every seat that watches it. The whole
  screen should be visible, unobstructed, and square to the view.

## Review on Apple Vision Pro

Use Locus 1.4.9 or later, in Virtual Space; TVs are not offered in Room
Portal. From each seat that watches a TV:

1. Every TV is off on arrival, and its off state looks right: no glow, no
   flicker at the edges, artwork upright.
2. Look at the screen and pinch. The TV turns on and the page fills the
   screen exactly.
3. The remote under the TV is visible, readable and easy to reach, and no
   furniture hides it.
4. From a Browser window, **Play on TV** lists each TV by its display name and
   moves the page; **Open in Window** brings it back.
5. Watch for a few minutes. Report neck strain, a screen that feels too big or
   too small, or sound that comes from the wrong place.

Record anything you could not check as `not verified`.
