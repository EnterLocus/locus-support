---
name: build-a-view
description: Create or repair a static full-sphere 12K skybox for Locus using built-in image generation or images from any provider, with local Python projection, overlap blending and visual audits. Excludes 3D midground, animated or computed water, celestial layers and procedural skies.
---

# Build a View: static skybox

Create a complete 360° × 180° SDR equirectangular panorama. Start with the
creator's brief or a licensed full panorama; preserve the source and save
edits separately. This public skill and `tools/skybox/` are Apache-2.0.
Commands run from a clone of the public `EnterLocus/locus-support` repository;
no private Locus scripts, credentials, source, catalog or asset paths are used.

Read [the workflow](references/skybox-workflow.md) for commands, prompts,
pixel-density arithmetic and repair decisions. Default to Codex's built-in
image generation/editing tool, then exchange actual image files with the
local Python tools. The Python CLI does not invoke the built-in tool or ask
for an API key. Inspect its actual output dimensions; prompt wording cannot
guarantee a model's size or projection.

If built-in generation is unavailable, report that limitation. A creator can
choose another image editor or API, including their own Nano Banana Pro key
route. Models are interchangeable file producers; do not silently switch to
a billable API, choose a paid budget, or assume built-in availability is free
or unlimited. Never include keys in files, prompts, logs or reports.

1. Generate a coherent full sphere. Review level horizon, world layout,
   wrap and poles before spending effort on resolution.
2. Restore ambiguous AI regions across the complete panorama once, if needed.
   Roll the wrap into the image center for repair, then reverse the roll.
   Restoration may invent detail; do not use it to claim photographic fidelity.
3. Split the accepted layout into six perspective faces with 6° context on
   each side. Enhance detailed faces one at a time with a preservation prompt.
   Resample featureless sky instead of inventing texture. Inspect each result
   for geometry and tone drift; preserve overlap and framing.
4. Merge to 12,288 × 6,144 using a narrow 0.25° half-width transition. Broad
   overlap supplies generation context; it is not a broad blending instruction.
5. Audit perspective views, every cube join, ±180° wrap, zenith and nadir.
   Repair the smallest defective region and repeat the affected audit.
   Obtain an independent image review when another agent is available.
6. Deliver the panorama, source, face metadata, prompts, generation dimensions,
   checksums and honest review findings. Import the exact panorama through
   Locus Places → Import → Import a View, then check on Apple Vision Pro.

A 12K canvas made by resizing remains a resized image. Record which faces
received generated detail, their actual returned dimensions and any enlargement.
Metrics diagnose change; neither seam ratios nor sharpness scores prove quality.
Perspective image review is distinct from Locus loading and headset acceptance.

This phase includes painted sea or beach as static panorama pixels. It does
not create water geometry, motion, parallax, sound or procedural lighting.
Build those future View layers on the accepted skybox with their own contracts.
