# Models, API keys and the cost of a 12K View

Prices checked **2026-11-13**, in USD. These are estimates for provider-direct
APIs, not a quote for a reseller, a subscription allowance or a quality guarantee.
Every submission still needs the creator's approval of its own estimate.

## Choose one of two model routes

| Route | API model | Credential reference | High-resolution work |
| --- | --- | --- | --- |
| Nano Banana Pro | Google Gemini 3 Pro Image (`gemini-3-pro-image`; verify the current model ID supported by the chosen API) | Usually `GEMINI_API_KEY` | Native 4K; previously tested with our skybox method |
| GPT Image 2.6 | OpenAI `gpt-image-2.6-sunburst` | Usually `OPENAI_API_KEY` | Candidate: explicit high quality, 3840×1920 panorama and 2880×2880 square faces; verify returned sizes and quality before continuing |

Ask which API/model the creator wants and which environment variable or secure
credential-file reference holds its key. Do not ask them to paste the key into
chat. Existing compatible configuration is enough; no account-setup walkthrough
is needed. Keys remain outside the repository and all prompt/report output.
A reseller key uses that reseller's model IDs, rates and batch capabilities.

GPT Image 2.6 is an offered route, not yet an accepted quality-equivalent skybox
baseline. Its official calculator explicitly includes 2.6 and uses a maximum
3840-pixel edge and 8,294,400-pixel budget. That permits 3840×1920 and 2880²,
not 4096². The prose size-reference list still names 2/2.5; verify actual results
on the first approved request. API resolution support does not guarantee seam
continuity or useful fine detail. Built-in image generation is not this API.

## What one View costs

First select the base-image route, then count every required stage. Selecting
GPT Image 2.6 or Nano Banana Pro for high-resolution enhancement does **not**
automatically select that paid API for the initial concept/base image.

| Stage | Role | Paid image-API requests |
| --- | --- | --- |
| B: initial full 360° base | Use a supplied image, a built-in generated base, or an explicitly selected paid API base | 0 for a supplied/built-in base; 1 only if paid API base generation was selected and approved |
| G: whole-panorama restoration | Resolve a low-resolution or blurred base globally before splitting | Usually 1 for a low-resolution base; 0 only if the base already passes native-resolution and detail review |
| F: directional detail | Enhance the six perspective faces | Up to 6; skip only truly featureless faces |
| R: targeted repairs | Fix observed wrap/face/nadir defects after review | Plan an initial reserve for 0–2 outputs; larger repairs or failed attempts can require more |

The initial built-in base needs no external API key and adds **$0 to this
image-API bill**. It may consume the host product's generation allowance;
do not call it universally free or unlimited. Its low resolution is acceptable
as an authoring base, never as the final 12K result. If unavailable, ask about
a supplied base or an explicitly quoted paid base instead of silently changing
routes.

For the usual **built-in low-resolution base → G → six F → R** route, expect
**7–9 paid image outputs**, plus any rejected attempts. Starting from an
accepted high-resolution base can reduce that to **6–8**. A paid API base adds
one request, but its accepted high-resolution result may make G unnecessary;
do not automatically charge both paid base generation and restoration.
A sample face used to validate the provider counts as one of the six F outputs,
not a seventh face. If that sample is rejected, its replacement is an extra
paid attempt and must be quoted separately.

These counts assume six detailed faces and a 0–2-output repair allowance, not
a guarantee that two repairs will finish the scene. Quote a four-face seam
refinement as four outputs if that is what the actual repair requires. Local
projection, masks, blending and audits have no image-provider charge. Agent
time, host subscriptions, storage, taxes and third-party fees are excluded.

Before asking approval for the first submission, show the **whole-run plan**
with B/G/F/R counts, native dimensions, quality, estimated input charges and
repair/retry reserve. Then quote the immediate submission separately. A $0.15
base-only quote is not the total View budget. Whole-run planning does not waive
per-submission approval.

### Nano Banana Pro

[Google's official pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3-pro-image)
lists **$0.24 per 4K image output** on the standard route. Input images,
prompt/text and thinking tokens are additional. The [Batch API](https://ai.google.dev/gemini-api/docs/batch-api#image-generation)
processes supported image requests at **50% of standard cost**; **$0.12 per
4K output** below is calculated from that discount, rather than a separate
per-image guarantee for every API route.

| Work | Standard image-output subtotal | Eligible Batch image-output subtotal |
| --- | ---: | ---: |
| Restoration + six faces (7 outputs) | $1.68 | $0.84 |
| Built-in base + restoration + six faces + 0–2 repairs (7–9) | $1.68–2.16 | $0.84–1.08 |
| Optional paid API base, if separately selected | +$0.24 | +$0.12 |
| Each additional 4K reroll | +$0.24 | +$0.12 |

A practical initial planning allowance is **about $3–5 per View** for a modest
standard run with overhead and some rejected attempts. Batch can lower the
output portion substantially, but an allowance is not a promise or automatic
permission to spend it. Quote the selected requests and an explicit reserve.
Do not reuse historical Replicate rates or assume a reseller passes through
Google's Batch discount.

### GPT Image 2.6 Sunburst

[OpenAI pricing](https://developers.openai.com/api/docs/pricing#image-generation)
lists standard image output at **$30 per million tokens**, image input at
**$8/M** and text input at **$5/M**. There is no universal flat price per image.
Dimensions and quality change output token consumption.

The following **output-only estimates** reproduce the official
[image token calculator](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs)
for GPT Image 2.6, without making any billable request:

| Quality | One 3840×1920 panorama | One 2880×2880 face | G + six F | Built-in base + G + six F + 0–2 face repairs |
| --- | ---: | ---: | ---: | ---: |
| high | $0.081 (2,700 tokens) | $0.178 (5,930) | $1.15 | $1.15–1.50 |
| xhigh | $0.144 (4,799 tokens) | $0.316 (10,542) | $2.04 | $2.04–2.67 |
| max | $0.324 (10,798 tokens) | $0.712 (23,719) | $4.59 | $4.59–6.02 |

These are output subtotals, **not full-run quotes**. A quote for G/F/R edits
must include the submitted image-input charge; the text-only base quote has no
image input and cannot be reused for face edits. Estimate from the actual
submitted dimensions and current provider input-token rules, or state a
conservative image-input reserve and the uncertainty. Do not set unknown image
input to zero or treat the displayed planning allowance as a token calculation.
Add input-image/text charges, rejected attempts and a stated reserve to these
subtotals. For planning, allow **roughly $2–4 at high, $3–6 at xhigh, or
$6–10 at max** for that example run, then replace the allowance with the actual
per-submission quote. This is not measured scene cost or a claim that high
matches Nano Banana Pro's quality. More expensive quality settings require a
fresh estimate and approval. Do not default to max merely because it exists.

OpenAI also publishes **Batch rates at half standard** for 2.6: $15/M image
output, $4/M image input and $2.50/M text input. However, the current
[2.6 model page](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst)
still marks Batch unsupported, while the [Batch guide](https://developers.openai.com/api/docs/guides/batch)
explicitly documents image Batch for 2.5. These official sources are not yet
consistent. Treat 2.6 Batch as **availability not verified**: quote standard
pricing until the selected model/account/endpoint is confirmed eligible. If
eligible, halve the output subtotals above; do not silently switch models to
obtain the discount. Do not promise cache savings from reusing the same file.

## How to use bulk processing without wasting money

Bulk means the provider's discounted asynchronous **Batch API**, not six
parallel standard requests or `n=6` in an ordinary request. Those ordinary
requests have no automatic bulk discount. Both providers describe a roughly
24-hour processing window for their Batch products; confirm current endpoint
and model eligibility before quoting that mode.

1. Review and accept the base layout first. Restore it and inspect its native
   output before submitting dependent face edits. For a new provider, inspect
   one approved representative face before committing the remaining faces.
2. After that checkpoint, group independent remaining faces from one or several
   accepted scenes into a batch. List each scene/face and cost in the approval
   request. A batch cannot include a face whose restored input does not exist.
3. Give each request a stable scene/stage/face ID. Save job ID, input hashes and
   outputs after completion. Use JSONL/file inputs for large image batches;
   Gemini inline batch bodies must stay under 20 MB.
4. Reuse successful results; retry only failed or rejected faces after a new
   quote and approval. An interrupted or unknown-status paid request is not
   permission to resubmit. Check its saved job/status first.
5. Run projection, blend, sky masks and audits locally. Skip only truly
   featureless faces, never sand, foliage, clouds or water with visible detail.

For an established provider, one standard Nano Banana restoration plus six
Batch face outputs has an output subtotal of **$0.24 + 6×$0.12 = $0.96**;
with a built-in base and two standard repairs, it is **$1.44**, before
input/text/thinking charges. For a new provider, one representative F face
is first run standard and accepted, then the remaining **five** faces go to
Batch: **$0.24 G + $0.24 F-probe + 5×$0.12 = $1.08**, or **$1.56** with
two standard repairs. The accepted probe is reused, not generated again.
This mixed schedule gives rapid layout/repair feedback and discounts independent
faces. All submissions require their own approved quote.

## Quote before every generation

Present a concrete quote, then wait for an explicit reply before any paid
submission. A useful quote includes:

- API and exact model; stage or face IDs; input identities; requested native
  dimensions, quality, count, and standard/Batch mode;
- itemized output estimate, input/text estimate, expected total, conservative
  reserve and proposed spending ceiling for **this submission**;
- dated pricing source, expected turnaround, and anything still uncertain.

The ceiling is an agent stop/reserve rule, not a provider-enforced billing cap;
token-billed costs can vary. Explain how uncertain input usage is estimated.
If reliable rates or a usable estimate are missing, resolve them before asking
for approval or submitting. Never use an arbitrary historical price as a quote.

An approval covers only the explicitly listed request, or the exact itemized
batch the creator approved. It does not cover later stages, extra candidates,
new seeds, rerolls, changed size/quality/model, or replacement submissions.
A batch quote must show every image's estimate and the batch total so one
explicit approval can cover that declared batch. Re-ask for missing credential
information only when it is actually missing; reuse the chosen model and
credential reference across the session.

A short example (replace these figures with the actual input estimate):

> Nano Banana Pro, six listed 4K face edits in Google Batch. Output estimate:
> 6×$0.12 = $0.72. Estimated input/text/thinking: $0.08. Expected total $0.80;
> proposed reserve/ceiling $1.00. Turnaround up to about 24 hours. This approval
> covers these six faces only; no retries or later repairs. Approve this batch?

After each completed submission, report estimated versus actual/usage-derived
cost, returned native sizes, accepted/rejected outputs and remaining allowance.
Use provider billing for final charges; do not label a calculator estimate as
an actual bill. A visually rejected image may still be billable.
