# Materials, export, and RealityKit pitfalls

Use the exported USDZ as the delivery artifact. A material that looks right in
a DCC can still lose transparency, normals, or texture interpretation after
export. Reopen or inspect the USDZ and use the Room checker renders before
calling an export complete.

## Export contract

- Export one self-contained USDZ in meters with +Y up and world -Z forward.
- Store USDZ members uncompressed so the archive remains accepted by the
  public tooling.
- Give every metadata-referenced object a stable, unique exported name.
- Keep authoring cameras, helper lights, unused test geometry, and source-only
  collections out of the delivered model.
- Use file-backed base color, roughness, metallic, and normal maps. Bake
  procedural textures to images before export when the target material cannot
  express them.

Run `xcrun usdchecker --arkit scene.usdz` and inspect the delivered hierarchy,
texture paths, axes, scale, material bindings, transparency values, and every
controlled fixture body's emission. A structural checker cannot judge whether
a material looks plausible from a visitor's eye point.

## Known RealityKit failures

**Do not rely on a double-sided material flag.** It can be back-face culled.
Give open shells—lamp shades, cups, leaves, curtains, and open boxes—real
thickness or closed geometry. For intentionally thin cards such as leaves,
point normals toward the side visible from the seats.

**Do not ship one packed ORM image.** An occlusion/roughness/metallic texture
can render black in the target path. Split it into separate grayscale roughness
and metallic image files, then wire each to its own input.

**Do not use a zero-thickness desktop.** Desk measurement needs a real tabletop
volume. Model a slab with a physical thickness and map the desk seat to that
actual tabletop entity.

**Do not place a terrain base under the Room.** A large ground plane hides the
paired View's water and makes the USDZ visual bounds much larger than the Room.
That shifts every normalized `anchorXZ` seat. The Room floor and architecture
should be only what the visitor needs to see and occupy.

**Do not center a seat eye point inside the chair.** Put it in front of the
backrest and above the cushion. Exported bounds and the eye-point helper make
this easy to review before packaging.

## Material review

Check glass and translucent surfaces against a bright and a dark view. Check
metal, roughness, normal scale, texture repetition, leaf normals, and emissive
fixture bodies from every declared seat. Repair the editable source and repeat
the export; do not compensate with a name-based runtime override or by editing
the ZIP directly.
