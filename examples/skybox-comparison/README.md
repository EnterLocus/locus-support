# One Maldives base, three enhancement routes

Read the [Build a View tutorial on enterlocus.com](https://enterlocus.com/build-a-view/)
for the illustrated creation workflow. This page keeps the downloadable
comparison outputs, detailed evidence and reproducible assembly.

The original two fresh GPT-6.1 Sol agents used the public repository, the same frozen input
and official API documentation. GPT Image 2.6 returned six 2880-square faces;
Nano Banana Pro returned six 4096-square faces. Their conservative native
sampling exports are **7322×3661** and **10418×5209**. Neither is native 12K.

A separate Nano Banana 2.1 trial on 2026-11-14 reused that frozen source and
original prompt. It also returned six 4096-square faces and a **10418×5209**
export. Its nine Standard outputs had $1.1840655 conservative accounting
under a separately authorized $2 plan. It remains a comparison candidate:
owner Locus/headset review is pending, and no model default has changed.

The original trial is also a quality comparison: GPT reconstructed crisper foliage,
water and sand in these particular outputs; Nano Banana returned more pixels
but softer detail. Both needed repairs. Nano Banana still has a visible broad
sky tone difference at the wrap, artificial zenith cirrus convergence and
smoother central sand relief. These are downloadable comparison candidates,
not a claim of defect-free production or headset acceptance.

| Measured route | Paid outputs | Delivery JPEG | Usage-priced API cost |
| --- | ---: | ---: | ---: |
| GPT Image 2.6 Sunburst, high, Standard | G1 + F6 + R2 = 9 | 7322×3661; 12.82 MB | $1.614237 |
| Nano Banana Pro, Standard G/R, Batch F6 | G1 + F6 + R2 = 9 | 10418×5209; 15.45 MB | $1.471502 under the residual-at-text assumption; $1.587014 conservative accounting |

Original two-model cohort: **18 paid outputs, $3.201251 conservative accounting** against the
creator's $5 combined authorization. These are response-usage calculations,
not reconciled provider invoices. The failed Nano Banana R1 is included.
See the [full formulas and token ambiguity](../../.agents/skills/build-a-view/references/models-and-cost.md)
and [request counters grouped by authorization cohort](usage.json). Agent/subscription time and storage
are separate.

## 1. The shared prompt and original panorama

The exact [original prompt](prompt.txt) describes a classic photorealistic
Maldives island beach with lagoon, pale sand, palms, a level horizon and one
fixed eye-height viewpoint. The original built-in image output is 1774×887.
It requires no external API key for that base step; host usage limits apply.

![The unchanged 1774 by 887 source panorama](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/source.png)

All three routes received these same bytes, not a regenerated or pre-restored
substitute. The source itself has a wrap defect and puts palms in the center
despite the prompt's lagoon-facing request. The creator froze this base for
the comparison, so those baseline choices remain visible.
[comparison.json](comparison.json) binds source/prompt hashes. The images here
are flat and perspective evidence; they do not claim a host's interactive
360° preview or an inspection in Locus.

## 2. Global restoration before face detail

GPT edited the complete source at 3840×1920/high/Standard. Nano Banana used
cyclic 21:9 context, Standard 4K, returned 6336×2688, then was explicitly
unpadded/downsampled to 5376×2688. The original source remains unchanged.

![Global restoration: GPT on the left, Nano Banana on the right](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/global-restoration.jpg)

These are invented reconstructions of an AI scene. They are not recovered
photographic truth. The archives include prepared inputs, raw outputs,
prompts, the Nano Banana aspect correction and usage.

## 3. Six contextual faces and native sampling

Each route covers all six directions with approximately 102° faces: a 90°
core plus 6° context per side. Source-sized projections were 1186-square
GPT inputs and 1660-square Nano Banana inputs; the models returned 2880² and
4096². Inputs were not enlarged to those output sizes.

The first successful face probe belongs to F6. Nano Banana's probe and
remaining five faces used actual asynchronous Batch jobs, not six parallel
Standard calls. A later repair needs the completed merge and therefore used
Standard. Batch discounts and possible job latency are explained in the
[cost article](../../.agents/skills/build-a-view/references/models-and-cost.md#batch-and-approval-policy).

For actual input projection ratio T=stored/core and returned face side N:

```text
f_center = N / (2*T) pixels per radian
W = 2 * floor(pi*N / (2*T))
H = W/2

GPT:  T=1186/960,  N=2880 => 7322×3661
Nano: T=1660/1344, N=4096 => 10418×5209
```

This is a conservative sampling convention, not measured resolved detail.
The [resolution reference](../../.agents/skills/build-a-view/references/resolution.md)
explains the common wider ERP convention and its face-center oversampling.
Merge directly sampled the returned native faces with a 0.25° blend half-width.

The following crops are **512 source pixels displayed at 1:1**, from the raw
forward face. They cover different angular areas because native pixel
densities differ; use the common-angle figure below for a matched comparison.

![Native pixel crops: GPT on the left, Nano Banana on the right](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/native-face-crops.jpg)

## 4. Repairs and remaining limits

The raw GPT merge had sky facets and vertical exposure bands. Free quadratic
sky-tone matching reduced the facets. A guarded source-sky mask retained
coherent 3840×1920 G sky on about one third of the canvas, with a wrap guard
and erosion around palm tips. That retained sky is interpolated G material,
not newly generated 7.3K sky detail. Two paid 2880-square,60° FOV perspective
edits at yaw ±135° repaired the remaining sky/water join bands; local
reinsertion preserved the original ERP grid and all zero-alpha PNG pixels.

Nano Banana's raw nadir had a strong radial sand star. Its first paid repair
did not solve it. Free native donor-grain healing removed the radial geometry
but left smooth microrelief; R2 restored grain, then was localized into the
original F face while protecting reviewed stones, shadows and overlap.
A free row-local sky-wrap correction reduced the narrow line, while the
broader tone difference and zenith cloud convergence remain. The nadir is
improved but still smoother than its surrounding original sand.

![Repair evidence: GPT seam and Nano Banana nadir before and after](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/repair-before-after.jpg)

The [local recipes and reviewed mask coordinates](recipes/README.md) are
included. They require image-specific inspection. Failed attempts, donor
regions, native outputs, masks and costs are retained; a clean-looking
thumbnail or seam statistic is not acceptance evidence.

## 5. Final comparison candidates

![Native-density final panoramas, GPT left and Nano Banana right](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/final-panorama.jpg)

The same camera directions, field of view and 768-pixel review grid are used
below for palms, shore, nadir and wrap. These are perspective resamplings for
comparison, not extra generated detail or native face crops.

![Matched angular comparisons, GPT left and Nano Banana right](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/same-angle.jpg)

Delivery derivatives use JPEG quality95,4:4:4 and optimized coding, with no
dimension change. Raw/lossless authoring inputs remain in the archives.
The smaller files do not establish quality; representative native crops
were checked against the PNG checkpoints.

Independent image review covered six cube directions, all 12 edge views,
poles, wrap and local feather boundaries. Locus import, physical Vision Pro
appearance, comfort and remote iCloud synchronization remain **NOT VERIFIED**.
The static skybox contains painted water; it adds no motion, depth or parallax.

## 6. Nano Banana 2.1 extension — 2026-11-14

API model `gemini-nano-banana-2.1` used **G1 + F6 + R2 = 9 Standard outputs**.
G returned 6336×2688 through the same cyclic 21:9 context, recovered as
5376×2688. Each 1660-square contextual face input (1344-square 90° core,
6° context per side) returned 4096². Native merge with 0.25° blend produced
10418×5209, without forcing a 12K canvas. The final q95, 4:4:4 sRGB JPEG is
15,620,534 bytes with unchanged dimensions; its identity is in
[comparison.json](comparison.json).

| Separate 2.1 accounting component | USD |
| --- | ---: |
| Nine 4K image outputs | $1.0206000 |
| Classified input/image/thinking usage | $1.0643055 |
| Total if unclassified candidate tokens use text rate | $1.0942455 |
| Conservative accounting, residual at image rate | $1.1840655 |

The creator explicitly authorized the full G1/F6/R0..2 trial under **$2**;
that covered its stages without repeated per-image confirmation. This was
separate from the original 18-output/$5 cohort. The two cohorts contain
**27 paid outputs**, with distinct approvals and costs; provider invoices
remain unverified. Batch support was checked through read-only model metadata
and current official pricing, but no 2.1 Batch generation was performed. The
cheaper mixed-mode formula is a modeled alternative, not this trial's cost.
See the [model-specific formulas](../../.agents/skills/build-a-view/references/models-and-cost.md)
and [all sanitized counters](usage.json).

The raw nadir had a dark crater and radial sand distortion. Paid R1 was
insufficient. Free native donor healing flattened the geometry; paid R2
restored grain, then local reinsertion protected reviewed stones and shadows.
A tiny pre-R2 pixel patch removed an added leaf edge and grey ghost. Free
row-local sky-wrap tone correction reduced a narrow wedge. These local edits
are scene-specific; the lossless checkpoints, masks, prompts and receipts
belong with the downloadable intermediates, not only the final JPEG.

Independent static review covered all six cube directions and 12 join views,
then rechecked affected nadir edges, wrap, zenith, matched directions and
native repair crops. It accepted this candidate for static comparison with
disclosed limits: waxy/outlined leaves, partly soft sky, zenith cirrus
convergence, lower-relief speckled nadir sand and a locally smoother shell
protection patch. The crater and new leaf/ghost were removed without a new
hard reinsertion ring at reviewed scales.

In this scene, 2.1 was close to Pro in foliage/water detail, with better wrap
continuity and repaired nadir grain, at a lower calculated fee. GPT's candidate
remained crisper in foliage, water patterns and sand relief. One AI scene,
one candidate per route and different local repairs do not establish a
universal ranking. Static image acceptance does not establish Locus import,
physical Vision Pro appearance or comfort. **Owner headset review is pending;
2.1 has not become the default.**

![Nano Banana 2.1 native-density final panorama](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-panorama-b97fb63bb25e.jpg)

![Nano Banana 2.1 nadir: raw face, R1, local geometry heal and localized R2](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-repairs-2359ac4202dc.jpg)

![Matched GPT Image 2.6, Nano Banana Pro and Nano Banana 2.1 views](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-comparison-17d8f14e3cca.jpg)

## Downloads and reproduction

- [GPT7322×3661 JPEG](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/gpt-image26-7322x3661.jpg)
- [Nano Banana10418×5209 JPEG](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-pro-10418x5209.jpg)
- [GPT native G/F/R outputs and prompts](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/gpt-image26-intermediates.zip)
- [Nano Banana native G/F/R outputs, failed R1 and repair inputs](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-pro-intermediates.zip)
- [Perspective review images and masks](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/review-evidence.zip)
- [Nano Banana 2.1 10418×5209 JPEG](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-10418x5209-3f7b009726cc.jpg)
- [Nano Banana 2.1 inputs, nine native outputs and selected nadir](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-intermediates-74e0d4babde4.zip)
- [Nano Banana 2.1 and three-route visual evidence](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-21-review-evidence-b1799ceb39be.zip)
- [Every released asset's identity](comparison.json)

To reassemble saved API outputs without keys or new API fees:

```sh
python3 -m pip install numpy Pillow
python3 examples/skybox-comparison/reproduce.py \
  --gpt-archive gpt-image26-intermediates.zip \
  --nano-archive nano-banana-pro-intermediates.zip \
  --outdir maldives-reproduced
```

Python 3.9+ is required. The script produces native PNG checkpoints and JPEG
derivatives, checks original framing metadata, and preserves local receipts.
A real no-API run reproduced both final PNG files byte-for-byte; see the
[reproduction check](reproduction-check.json).
Dependency versions can affect byte encoding; the published trial records
its actual hashes. This reproduces local assembly, not stochastic API draws.

The separate 2.1 intermediates archive is identified as
`nano-banana-21-intermediates.zip` in [the asset manifest](comparison.json),
with the delivery JPEG and `nano-banana-21-review-evidence.zip`. It retains
source/prompt, G, six face inputs and native outputs, R1/R2, selected final
nadir face, masks, local-method scripts and sanitized receipts. To reassemble
that route without a key or another paid call:

```sh
python3 examples/skybox-comparison/reproduce_nano21.py \
  --archive nano-banana-21-intermediates.zip \
  --outdir nano21-reproduced
```

This assembles saved stochastic outputs; it does not regenerate their AI
content. The selected nadir face includes the reviewed local repairs. The
script applies the recorded native merge and public sky-wrap tone helper.

The public skill, scripts and recipes are Apache-2.0. Demo images are separate
from that tooling license grant; the repository's [license map](../../LICENSE.md)
applies. Start a new scene with the [build-a-view skill](../../.agents/skills/build-a-view/SKILL.md):
confirm its panorama first, then choose API/key, native size, processing mode
and an explicit formula-based budget.
