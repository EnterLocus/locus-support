---
name: build-a-view
description: Create or repair a static full-sphere skybox at native sampling density for Locus using an explicitly configured high-resolution image API, native-size and fidelity checks, and local Python projection and visual audits. Excludes 3D midground, animated or computed water, celestial layers and procedural skies.
---

# Build a View: static skybox

Create a complete 360° × 180° SDR equirectangular panorama. Start with the
creator's brief or a licensed full panorama; preserve the source and save
edits separately. This public skill and `tools/skybox/` are Apache-2.0.
Commands run from a clone of the public `EnterLocus/locus-support` repository;
no private Locus scripts, credentials, source, catalog or asset paths are used.

Use exactly two creator checkpoints. Read [the workflow](references/skybox-workflow.md)
for image processing, [models and costs](references/models-and-cost.md) for
quotes, and [native resolution](references/resolution.md) before promising size.

## Step 1 — make the panorama and obtain visual confirmation

Generate one full 360°×180° base, normally with the host's built-in image tool,
or use the creator's supplied image. The built-in base needs no external API
key; it may consume the host's generation allowance. Do not begin by asking for
an API key or silently select a paid API base. If built-in generation is not
available, explain the alternative supplied/paid-base routes and quote any paid
base before submitting it.

Show the actual panorama to the creator. Where the host offers native 360°
preview, present it there so they can turn around; retain a flat preview and
perspective/seam crops as review evidence. If that host preview cannot be
opened, say so and offer an available interactive/local preview rather than
claiming a flat picture is a 360° inspection. Do not invent a tool/API for it.

Wait for the creator to accept the base's world/layout. Record its exact file,
dimensions, prompt and SHA-256. Freeze those bytes. A supplied or previously
selected base with explicit acceptance skips generation and repeated approval.
Changing that accepted layout/base needs renewed visual confirmation. In a
model comparison, both agents receive the same frozen file, not independent
new base generations or different already-restored versions.

## Step 2 — select API, quote cost and resolution, then enhance

After base acceptance, offer Nano Banana Pro (tested baseline) and GPT Image
2.6 Sunburst (candidate requiring native-size/fidelity validation). Ask for
only missing API/model and credential-reference information: environment
variable name or secure credential-file reference, never a key pasted in chat.
Keep setup brief and reuse known answers. Load keys quietly; do not print,
commit or persist secret values. A generated high-resolution route needs API
credentials even when Step 1 did not.

Present the full stage plan and its formula: N_paid=B+G+F+R+E. For a frozen
low-resolution base, B=0,G=1,F=6,R=0..2,E=0 means 7..9 outputs per model,
14..18 for a two-model comparison. The accepted probe is one of the six F.
Use [the written model-specific cost formulas](references/models-and-cost.md)
and separate known output costs, unknown/actual input or thinking tokens,
actual spent cost and the reserve. Do not guess overhead tokens or multiply
one stage's unit price by all requests. Quote
output **and image-input/text** charges, model, dimensions, quality and expected
final native-sampling ERP size. State which number is calculated and which is
still an unverified model capability/quality assumption. Do not promise 12K.

For Nano Banana Pro, explicitly offer Standard versus discounted Batch,
including estimated savings, up-to-about-24-hour job latency and sequential
stage dependency. Ask which the creator prefers **before production**; reuse
an explicit choice already supplied. For GPT, offer Batch only when its exact
model/account/endpoint eligibility is confirmed. Never assume six parallel
standard requests get a Batch discount.

**Before every paid generation/edit submission, give the concrete itemized
estimate and wait for explicit approval.** A listed Batch job may receive one
approval covering that exact image list and total. Later stages, extra
candidates, repairs, retries, changed size/quality/model and unknown-status
replacement submissions need fresh quotes/approval. An overall planning
budget or supplied key is not ongoing permission to generate. If the creator explicitly authorizes a declared full plan under a combined
cap instead, record that override and execute only its listed scope without
asking again for each image. Keep one shared cost ledger for parallel agents.
Free local preparation and read-only pricing checks can continue while waiting.

After approval, execute the following processing stages, preserving each
checkpoint and returned native dimensions:

1. Restore a low-resolution/blurred base globally at high resolution before
   splitting, preserving its accepted layout. Repair wrap and sky as needed;
   audit the repaired center and newly generated image edges. Reconstruction
   invents detail and must not be described as photographic fidelity.
2. Split into six 102° faces (6° context per side), verify one representative
   preservation edit, then enhance remaining independent faces in an approved
   batch where eligible. Every meaningful detailed direction needs enhancement;
   skip only truly featureless regions. The successful probe counts as one of
   the six, not an additional seventh face.
3. Calculate native output dimensions from actual face sizes/FOV and merge
   with `--native-resolution`, using 0.25° blend half-width. Do not normalize
   small faces to a 3794 grid or force a 12288-wide canvas.
4. Audit forward/back/left/right/up/down, every cube join, wrap, near field and
   poles. Quote targeted repairs only for observed defects. Obtain an
   independent image review when available; reject failed candidates.
5. Deliver the accepted native-size panorama to the requested destination,
   together with prompt, frozen-base identity, raw/restored intermediates,
   face edits, costs, merge receipts and review evidence. For a public demo,
   explain both model paths from the same base and show intermediate and final
   results with actual dimensions/fees; do not replace pending rows with claims.
   Import the exact file in Locus for a separate device check.

A larger canvas made by resizing remains a resized image. Record which faces
received generated detail, their actual returned dimensions and any enlargement.
Metrics diagnose change; neither seam ratios nor sharpness scores prove quality.
Perspective image review is distinct from Locus loading and headset acceptance.

This phase includes painted sea or beach as static panorama pixels. It does
not create water geometry, motion, parallax, sound or procedural lighting.
Build those future View layers on the accepted skybox with their own contracts.

The small-patch tool remains experimental. Its Maldives test failed integration;
it is not an approved substitute for native high-resolution faces. Do not
deliver partial enhancement as a finished high-resolution result. A failed trial remains a
failed trial even when its dimensions are 12288×6144.
