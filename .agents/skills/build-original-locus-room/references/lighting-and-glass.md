# Indirect lighting and clear architectural glass

Use this reference to author broad artificial-light bounce and export clear
glazing that behaves correctly in Locus. It is self-contained and uses ordinary
Blender/USD concepts plus the public Room interface. Use your chosen authoring
tool; the Blender-specific details below describe the default headless route.

## Identify the affected layer

An emissive fixture, a point/spot direct source, and an indirect atlas do
different jobs. A brighter direct source does not replace broad diffuse bounce.
The Room Lights master changes both direct and indirect contributions, so
toggling it alone cannot isolate which one causes an artifact.

For an investigation, hold the Room, View, camera/seat, sun, brightness, and app
version fixed. Change one contribution or material parameter in a recoverable
source variant, restore the original, and repeat. Re-export and import each
exact variant through the normal Locus flow. Record which Room variant is
selected; successful import alone does not prove the right variant is visible.

Two distinct problems informed these checks:

- Colored surface blotches at high Room brightness came from damaged indirect
  texture data. Higher-precision storage removed the color damage, but residual
  cloud-like mottling also required correct material UVs and sufficient sampling.
- A small colored center or dark ring in a reflected sun responded to the
  glass's clearcoat roughness, even when clearcoat strength was zero. This is
  a separate material compatibility issue, not evidence of a noisy bounce atlas.

Do not conceal either problem by lowering the brightness ceiling, dimming all
lamps, blurring every reflection, or removing the sun instead of isolating it.

## Bake indirect light without losing its color or precision

For Room-v3 `bakedIndirect.entities`, select intentional opaque receivers such
as floors, walls, ceiling undersides, and furniture. Keep transparent glass,
water, other transmissive surfaces, visible fixture bodies, and local halos
outside this subtree. Preserve base materials and the editable original.

1. **Keep the bake in linear float.** In Blender, create the target image with
   `float_buffer=True` and scene-linear `Linear Rec.709` color space. Filter
   and calibrate those linear values before encoding. Dim channels quantized
   into an 8-bit buffer cannot be recovered by saving that buffer as PNG16 later;
   Room-wide gain can expose the lost precision as colored patches.
2. **Include receiver material color.** For the emission-atlas approach, bake
   diffuse indirect with `use_pass_indirect=True`, `use_pass_direct=False`,
   and `use_pass_color=True`. The atlas is emitted light from the surface,
   not irradiance that Locus will multiply by the base color again. Exclude
   preview world/sun lighting from an artificial-only bake.
3. **Keep two UV roles distinct.** Preserve the original material UV as
   `active_render` so implicit material texture coordinates still sample the
   original maps. Pass the atlas UV explicitly to the bake, for example
   `uv_layer="LocusIndirectUV"`. That name is an authoring convention, not a
   required Room JSON field. Check that base UV coordinates remain unchanged.
4. **Use an explicit sampling budget.** In the tested Blender 5.2 workflow,
   inherited preview adaptive thresholds stopped a dim bake too early. Later
   normalization and brightness gain exposed the remaining noise. A verified
   starting point was a 1024-square atlas, 2048 fixed samples, seed 0, animated
   seed off, and adaptive sampling off, followed by two radius-4 box-filter
   passes in linear float. Tune resolution, samples, and filtering for the
   actual Room; this is not a convergence proof or a universal minimum.
   Inspect the raw atlas and final surface instead of using blur to hide a
   wrong UV binding or incomplete sampling.
5. **Encode once, independently of the scene's look.** Save RGB 16-bit PNG
   through a separate Standard/sRGB save scene with no look, exposure 0,
   gamma 1, and no dither. In the tested Blender path, `Image.save()` did not
   honor the scene's PNG depth setting; `image.save_render(path, scene=...)`
   with explicit `file_format="PNG"`, `color_mode="RGB"`, and
   `color_depth="16"` did. Reload the file as sRGB. Verify the actual PNG
   depth/type, rather than inferring it from the filename or settings.
6. **Verify UV and color bindings in the delivered USDZ.** Blender 5.2 could
   export the additional UV primvar but still bind its named reader to `st`.
   Inspect the indirect `UsdPrimvarReader_float2` input `varname` and the
   connected texture's `st`; make the reader address the actual atlas primvar,
   leaving base-material UVs alone. Put any required correction in a repeatable
   export step, then rebuild and validate the package. Confirm the emission
   texture is declared sRGB and its packaged PNG is byte-identical to the
   saved source; do not label encoded sRGB values as linear.
7. **Make baseline gain survive export.** The tested Blender USD
   textured-emission path dropped a separate non-unity Emission Strength.
   Calibrate the desired baseline into the atlas and keep material emission
   gain at 1 for that path. Locus applies `2^overallEV` to the authored indirect
   baseline. If another exporter represents gain differently, inspect the
   exported material rather than assuming the DCC render proves equivalence.

Retain source maps, scripts, and bake settings outside the five-file Room ZIP.
Bake each differing Room/light layout intentionally; a similar-looking house
does not justify reusing its atlas. Repeated builds must replace only their
own generated nodes/lights and preserve geometry, base UVs, material settings,
and any authored animation.

This layer is static aggregate lamp bounce, not full dynamic global
illumination. The Room master and Overall Room EV affect it, but per-light
switch/color/temperature/EV changes do not recompute that light's baked
contribution, and moving occluders do not rebake it. Point/spot proxies are not
large area emitters. A clean bright-state result is not proof of physically
calibrated equivalence to diffuse lighting in a real home.

## Check transmissive materials in the exact USDZ

In the tested Blender 5.2 USD PreviewSurface export, Principled Alpha alone
could produce opaque glass: the Transmission Weight mapping also writes USD
opacity. For scalar transmissive glazing in this path, use Alpha 1 and author
the intended Transmission Weight, then check the exported `inputs:opacity`.
Transmission 0.9 exported opacity about 0.1 in the supplied Material Study.
This describes an export mapping, not a required glass appearance or a promise
of refraction in Locus. Blender's
[USD material writer](https://raw.githubusercontent.com/blender/blender/main/source/blender/io/usd/intern/usd_writer_material.cc)
is the upstream implementation reference; recheck with another exporter version.

Preserve linked maps, animation and intentional coatings. Inspect opacity,
roughness, coat and normal inputs in the delivered file, then import it and
look through the panes against a View. Correct the editable material or a
repeatable export step and rebuild; a runtime preset or a manually patched ZIP
would leave the next source export wrong. USD validity alone does not prove
that the material is transparent.

## Distinguish base roughness from clearcoat roughness

In Locus testing with visionOS 26.5, transparent architectural glass with
clearcoat strength 0 and clearcoat roughness 0.03 produced a colored center
in a sun reflection on the Simulator. Changing only clearcoat roughness to
0.2 removed that center; restoring 0.03 restored it, and a repeated 0.2 trial
removed it again without changing the surrounding highlight extent. A thin
gray/dark ring on physical Vision Pro was separately confirmed corrected.
These observations establish a useful compatibility workaround, not the
renderer’s internal shader mechanism or a universal law for all glass.

For transparent architectural glass with an unused, unlinked clearcoat scalar
and exactly zero coat strength, author `clearcoatRoughness` at least 0.2
(Blender Principled `Coat Roughness`), preserving a higher valid value.
**Do not change base roughness to 0.2.** Keep the intended base roughness,
opacity/transmission, color, normals, and other material properties. Base
roughness 0.02 and opacity 0.1 were the tested clear-glass settings, not
mandatory settings for every creator's material.

Do not apply this correction to water, opaque surfaces, or intentionally
coated glass. Do not flatten connected textures or animated inputs into a
constant. Reject nonfinite/out-of-range scalar values instead of silently
clamping malformed authoring data.

Update the editable source and verify the matching exported
`UsdPreviewSurface.inputs:clearcoatRoughness`; otherwise the next export may
restore the old value. Preserve unrelated material properties, geometry, UVs,
texture bytes, and animation. Inspect other formats separately: a GLB exporter
may omit a disabled clearcoat extension, while USD still writes its scalar.
An unchanged Blender render with zero coat strength does not prove the
RealityKit highlight is unchanged.

## Verify through the public Locus workflow

- Validate the exact rebuilt USDZ and Room ZIP, then import, pair with a View,
  and enter it using the normal app controls. Inspect the loaded Room, not only
  the thumbnail or a settings panel over the surrounding environment.
- For an indirect-layer change, review affected seats in a dark View and a
  daylight View at 0/+2 EV and at +4 EV stress when the installed app exposes
  that Room-wide setting. If it does not, test its available ceiling and report
  that boundary. Do not modify per-light `brightnessEVRange` beyond `[-4, 1]`;
  it is a different contract. Inspect walls, floors, ceiling undersides,
  transitions, color patches, mottling, and clipping.
- For a glass-only correction, reproduce the reflected-sun case at the same
  camera and compare its center, extent, surrounding pixels, and transparency.
  Check relevant View changes; preserve the intended appearance rather than
  merely hiding the light. A scalar-only correction does not require unrelated
  lighting rebakes or establish a new all-seat comfort acceptance.
- Record the exact source/export, app version, Room variant, View, seat,
  brightness and sun settings with the screenshots. Simulator captures are
  useful for deterministic comparisons but do not replace physical Vision Pro
  checks for subtle glare, scale, tracking, reach, and comfort.

Return to [the Room interface](room-interface.md) for metadata and exact
delivery gates, and [the main skill](../SKILL.md) for packaging and handoff.
