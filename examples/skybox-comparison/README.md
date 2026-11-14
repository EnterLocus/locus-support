# One Maldives base, two enhancement routes

Two fresh GPT-6.1 Sol agents used the public repository, the same frozen input
and official API documentation. GPT Image 2.6 returned six 2880-square faces;
Nano Banana Pro returned six 4096-square faces. Their conservative native
sampling exports are **7322×3661** and **10418×5209**. Neither is native 12K.

This trial is also a quality comparison: GPT reconstructed crisper foliage,
water and sand in these particular outputs; Nano Banana returned more pixels
but softer detail. Both needed repairs. Nano Banana still has a visible broad
sky tone difference at the wrap, artificial zenith cirrus convergence and
smoother central sand relief. These are downloadable comparison candidates,
not a claim of defect-free production or headset acceptance.

| Measured route | Paid outputs | Delivery JPEG | Usage-priced API cost |
| --- | ---: | ---: | ---: |
| GPT Image 2.6 Sunburst, high, Standard | G1 + F6 + R2 = 9 | 7322×3661; 12.82 MB | $1.614237 |
| Nano Banana Pro, Standard G/R, Batch F6 | G1 + F6 + R2 = 9 | 10418×5209; 15.45 MB | $1.471502 under the residual-at-text assumption; $1.587014 conservative accounting |

Combined: **18 paid outputs, $3.201251 conservative accounting** against the
creator's $5 combined authorization. These are response-usage calculations,
not reconciled provider invoices. The failed Nano Banana R1 is included.
See the [full formulas and token ambiguity](../../.agents/skills/build-a-view/references/models-and-cost.md)
and [all 18 request counters](usage.json). Agent/subscription time and storage
are separate.

## 1. The shared prompt and original panorama

The exact [original prompt](prompt.txt) describes a classic photorealistic
Maldives island beach with lagoon, pale sand, palms, a level horizon and one
fixed eye-height viewpoint. The original built-in image output is 1774×887.
It requires no external API key for that base step; host usage limits apply.

![The unchanged 1774 by 887 source panorama](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/source.png)

Both routes received these same bytes, not a regenerated or pre-restored
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

## Downloads and reproduction

- [GPT7322×3661 JPEG](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/gpt-image26-7322x3661.jpg)
- [Nano Banana10418×5209 JPEG](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-pro-10418x5209.jpg)
- [GPT native G/F/R outputs and prompts](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/gpt-image26-intermediates.zip)
- [Nano Banana native G/F/R outputs, failed R1 and repair inputs](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/nano-banana-pro-intermediates.zip)
- [Perspective review images and masks](https://github.com/EnterLocus/locus-support/releases/download/skybox-comparison-2026-11-13/review-evidence.zip)
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

The public skill, scripts and recipes are Apache-2.0. Demo images are separate
from that tooling license grant; the repository's [license map](../../LICENSE.md)
applies. Start a new scene with the [build-a-view skill](../../.agents/skills/build-a-view/SKILL.md):
confirm its panorama first, then choose API/key, native size, processing mode
and an explicit formula-based budget.
