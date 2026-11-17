# Optional paid generation

This appendix is optional. The Room workflow is complete with creator-supplied
references, original modeling, local tools, and the public checker. Never make
an account, API key, paid provider, or credit balance a delivery prerequisite.

If a creator elects to buy generation, stay within their authorization and
retain the provider job ID, price, input rights, and output license in the
project record. Do not begin a paid generation job merely because this skill
mentions it.

## Image-to-3D furniture

Treat creator-authorized image-to-3D (e.g., Tripo, Rodin, Meshy, or local
open-weight models; never required) strictly as a **bounded single-prop
generator orchestrated by the Python build**, never as a whole-Room or
architectural-shell generator.

Use one isolated, unobstructed product shot per prop at a time rather than
mixing separately generated views whose proportions disagree. Inspect the
output topology and materials, and **never decimate an imported glTF directly**:
raw exports arrive split along UV and normal seams, so direct decimation opens
dark cracks. Either request a target polygon budget from the generator or weld
coincident vertices, decimate, and rebake color, roughness, metallic, and
tangent-normal maps onto clean UVs.

Split packed ORM data into separate grayscale roughness and metallic image
files, prefix texture filenames per prop so USDZ export does not collide
`color.jpg` across models, give thin surfaces real thickness where needed,
inspect all visible sides (especially chair backs visible from seats), normalize
axes and scale in Blender, and export a self-contained USDZ. Record material AI
contributions truthfully in `provenance.json` (`aiGenerated`, `aiProvider`).

Tripo is one optional image-to-3D route for furniture or local props. It is not
required, is not called by this skill, and needs no special runtime integration.
If the creator elects to use it, apply the same authorization, rights, and
provenance rules above; then bring only the selected output into Blender for
axis and scale normalization, UV/PBR preparation, dependency resolution, and
export review. Do not assume a generated model is already compatible with the
Locus mesh-USDZ delivery contract.

## Material relief and audio

Generated relief still needs a plausible scale, clean UVs, and an exported
normal/roughness response that survives the target renderer. Generated
environment sound or music must have rights that permit redistribution and
must be optional to the Room's core visual delivery. Record material AI use in
provenance whenever it materially contributed to the delivered asset.
