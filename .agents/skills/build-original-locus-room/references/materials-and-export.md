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

## Asset and texture inputs

When modeling demands detail that suitable external assets could provide,
search available libraries rather than assuming primitive placeholders are the
only option. Use only the models and textures needed for the selected Room;
downloading a large library does not make it a Room input. The creator may supply their own
properly licensed model, select a free licensed model, or ask ChatGPT to
generate a needed texture. Treat all of these as authoring inputs, not as
runtime-ready Room content: use Blender to normalize axes, scale, and
materials; resolve every external dependency; UV-map the model where needed;
prepare file-backed PBR maps; and review the final exported USDZ.

Useful public sources include:

- [Poly Haven models](https://polyhaven.com/models) and
  [textures](https://polyhaven.com/textures), both offered under
  [CC0](https://polyhaven.com/license);
- NVIDIA's official
  [SimReady assets dataset](https://huggingface.co/datasets/nvidia/simready-assets),
  licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); and
- Scenario's official
  [3D collection](https://huggingface.co/datasets/scenario-labs/3d-collection),
  licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The NVIDIA license statement applies to that official dataset, not generally to
all SimReady Central datasets. For NVIDIA or Scenario inputs, retain the source
URL, required attribution, license, and a record of the changes made in
`provenance.json`. Prefer mesh assets such as GLB or USD. Do not use Scenario
SPZ or splat assets: a Locus Room is delivered as a mesh USDZ.

For a ChatGPT-generated texture, keep the generated source and record material
AI use in provenance. Build or derive the required base-color, roughness,
metallic, and normal maps, then confirm the UV mapping and PBR response in the
exported USDZ. A free or generated input is not a promise of RealityKit-ready
materials, scale, topology, or licensing beyond its recorded terms.

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
