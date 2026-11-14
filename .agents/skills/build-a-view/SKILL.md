---
name: build-a-view
description: Create or repair a static full-sphere 12K skybox for Locus using an explicitly configured high-resolution image API, native-size and fidelity checks, and local Python projection and visual audits. Excludes 3D midground, animated or computed water, celestial layers and procedural skies.
---

# Build a View: static skybox

Create a complete 360° × 180° SDR equirectangular panorama. Start with the
creator's brief or a licensed full panorama; preserve the source and save
edits separately. This public skill and `tools/skybox/` are Apache-2.0.
Commands run from a clone of the public `EnterLocus/locus-support` repository;
no private Locus scripts, credentials, source, catalog or asset paths are used.

Read [the workflow](references/skybox-workflow.md) for commands, prompts,
pixel-density arithmetic and repair decisions. **A configured high-resolution
image API and its credentials are required for the generated 12K route.**
Offer **Nano Banana Pro** (previously tested native 4K baseline) and
**GPT Image 2.6 Sunburst** (new candidate requiring native-size and quality
validation). Read [models, costs and Batch](references/models-and-cost.md)
before discussing a budget or making a paid request. Other models still need
actual-size, fidelity and seam validation against an accepted baseline.
An already accepted high-resolution panorama can skip generation.

Codex built-in image generation may supply concepts or a low-resolution base.
It is not the final restoration/enhancement route: the tested tool returned
1774×887 panoramas and 1254×1254 faces and exposed no explicit size/model/
quality controls. Do not enlarge these into a purported finished 12K View.
The default has been corrected after the failed Maldives trial.

## Model, credential and approval conversation

Before generation, ask which API/model the creator wants and where its key is
configured: an environment variable name (for example `GEMINI_API_KEY` or
`OPENAI_API_KEY`) or a secure credential-file reference. Never request the
secret value in chat. Reuse answers already given; ask only missing details.
Keep setup brief. Load credentials quietly and never print or commit them.

**Before every image-generation/edit submission, give an itemized cost estimate
and wait for explicit user approval.** State exact model, input/stage/face IDs,
native dimensions, quality, image count, standard/Batch mode, output and input
estimates, reserve/ceiling and expected turnaround. Read-only pricing and local
image preparation can proceed while approval is pending; paid submission cannot.
Follow the quote contract in [models and costs](references/models-and-cost.md#quote-before-every-generation).

Approval applies only to that declared submission. For a Batch job, show every
image estimate and the total; one explicit approval may cover that exact list.
Later stages, retries, extra candidates, model/quality/size changes and repairs
need fresh quotes and approvals. An overall budget is not standing permission
to generate. Do not automatically retry an unknown-status paid request.
Never silently switch providers or reduce native resolution to finish a run.
The local Python tools do not submit generation requests.

## Make and review the skybox

1. Generate a coherent full sphere. Review level horizon, world layout,
   wrap and poles before spending effort on resolution.
2. Restore a low-resolution AI base across the complete panorama at a verified
   approximately 4K-wide native output before face enhancement.
   Roll the wrap into the image center for repair, then reverse the roll.
   Restoration may invent detail; do not use it to claim photographic fidelity.
3. Split the accepted layout into six perspective faces with 6° context on
   each side. Validate a representative face with a preservation prompt, then enhance
   independent remaining faces through an approved batch when eligible.
   Enhance every face with meaningful detail, including ground and clouds.
   Only truly featureless faces may use resampling. Inspect each result
   for geometry and tone drift; preserve overlap and framing.
4. Reject undersized, incomplete or visibly inconsistent face sets before
   final export. Merge accepted faces to 12,288 × 6,144 using a narrow
   0.25° half-width transition. Broad
   overlap supplies generation context; it is not a broad blending instruction.
5. Audit perspective views, every cube join, ±180° wrap, zenith and nadir.
   Repair the smallest defective region and repeat the affected audit.
   Obtain an independent image review when another agent is available.
6. Deliver only an accepted panorama, with source, face metadata, prompts,
   generation dimensions,
   checksums and honest review findings. Import the exact panorama through
   Locus Places → Import → Import a View, then check on Apple Vision Pro.

A 12K canvas made by resizing remains a resized image. Record which faces
received generated detail, their actual returned dimensions and any enlargement.
Metrics diagnose change; neither seam ratios nor sharpness scores prove quality.
Perspective image review is distinct from Locus loading and headset acceptance.

This phase includes painted sea or beach as static panorama pixels. It does
not create water geometry, motion, parallax, sound or procedural lighting.
Build those future View layers on the accepted skybox with their own contracts.

The small-patch tool remains experimental. Its Maldives test failed integration;
it is not an approved substitute for native high-resolution faces. Do not
deliver partial enhancement as a finished 12K result. A failed trial remains a
failed trial even when its dimensions are 12288×6144.
