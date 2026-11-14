# Models, request counts and cost formulas

Rates checked **2026-11-13**, USD, provider-direct APIs. Follow the two creator
checkpoints: first show and confirm the panorama; then select API/key, mode,
native resolution and cost. Confirm Nano Banana Pro Standard/Batch preference
before production. Reuse an explicit choice. Never request a secret in chat.

## Models and native image sizes

| Route | API model | Key reference | Native detail work |
| --- | --- | --- | --- |
| Nano Banana Pro | `gemini-3-pro-image` (verify provider model ID) | Usually `GEMINI_API_KEY` | 4K square faces, 4096²; tested method baseline |
| GPT Image 2.6 | `gpt-image-2.6-sunburst` | Usually `OPENAI_API_KEY` | Candidate: 3840×1920 G restoration and 2880² F faces, explicit high quality |

With 6° context per side, six 102° faces cover the whole sphere. Smaller faces
affect density, not coverage. Use the [native sampling calculation](resolution.md):
2880² gives about 7326×3663 ERP, 4096² about 10420×5210, subject to actual
rounded FOV and returned sizes. These are sample-density estimates, not proof
of resolved detail. GPT's 8,294,400-pixel calculator budget is not 4096².
The same-base [trial](../../../../examples/skybox-comparison/README.md) confirmed
these returned native sizes. Its sharpness, repair effort and remaining defects
must be judged separately; size does not establish quality equivalence.

Keys stay in the creator's named environment variable or secure credential
reference. Use the selected provider's own pricing for a reseller; do not
assume Google/OpenAI rates or Batch discounts apply to a different endpoint.

## Measured complete example

The same-base Maldives comparison produced **9 paid outputs per route**:
B=0, G=1, F=6, R=2, E=0. GPT used Standard throughout; Nano Banana used
Standard G/R and actual asynchronous Batch for all six F, including the probe.

| Route | Known image output subtotal | Usage-priced result | Conservative accounting |
| --- | ---: | ---: | ---: |
| GPT Image 2.6 high | $1.504200 | $1.614237 | $1.614237 |
| Nano Banana Pro mixed mode | $1.440000 | $1.471502 if unclassified candidate tokens use text rate | $1.587014 |
| Combined, 18 outputs | $2.944200 | $3.085739 under that Google assumption | **$3.201251** |

These are calculations from saved response usage and dated list prices,
**not reconciled provider invoices**. The Google residual/input discrepancies
are explained below and retained in [every request's counters](../../../../examples/skybox-comparison/usage.json).
The $5 authorization was a combined agent stop boundary, not an expected
charge or provider-enforced billing cap. Rejected paid repairs are included.
Local authoring and reassembly add no image-API fees; agent/subscription time
and storage are separate. This example does not guarantee a finished skybox
for the same cost: observed defects, attempts and acceptance remain explicit.

## Count outputs before quoting money

Write these variables into the plan:

- B: paid base outputs. **0** when reusing a confirmed image or a built-in
  generated panorama. A built-in base needs no external API key and adds $0
  to the image-API bill; host subscription/usage limits still apply.
- G: global restoration outputs. **1** for a low-resolution/blurred base;
  **0** only for an accepted sufficiently detailed high-resolution base.
- F: detailed face outputs. Normally **6**: px, nx, py, ny, pz, nz. A successful
  representative face is included in these six, not a seventh face. Only a
  documented genuinely featureless face may be skipped.
- R: targeted repair outputs. Start with **0**, reserve capacity for **2**.
  One wrap repair usually rerenders one face (1 output); a second independent
  face/nadir defect can require another (2 total). Two repairs are a planning
  allowance, not a promise of completion. A four-face seam-refinement pass
  means **4** outputs and is outside a two-output repair allowance.
- E: additional rejected attempts, replacements or rerolls. Start at **0**.
  A paid rejected result still counts. Never silently rerun a timed-out request.

```text
N_paid = B + G + F + R + E

Same confirmed low-resolution base, per model:
B=0, G=1, F=6, R=0..2, E=0
N_paid = 7..9

Two-model comparison:
N_paid_total = 14..18, excluding extra attempts E
```

If a paid native base already passes G's purpose, do not automatically buy a
second restoration. If a request outputs multiple images, count and price
those outputs individually. Local split/pad/masks/merge/audit have no image-
provider charge. Agent time, subscriptions, storage, tax and reseller fees
are separate. Write the actual stage count and assumptions before the first
submission; a one-image quote is not the whole-project budget.

## Nano Banana Pro: Standard G/R, Batch F

[Official Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3-pro-image)
lists a 4K output as 2,000 image tokens at $120/M = **$0.24 Standard**.
[Batch](https://ai.google.dev/gemini-api/docs/batch-api#image-generation) is
50% of Standard: **$0.12** for that output. Standard input costs $2/M tokens;
text/thinking output $12/M. Batch rates are half. The pricing page describes one image input as 560 tokens; prompt text is
additional. Our first measured requests reported 258 IMAGE input tokens instead.
Retain that discrepancy rather than rewriting reported usage to match the page.

For each request i, let P_i be all prompt-input tokens (including image input),
J_i image-output tokens, L_i returned text-output tokens, H_i thinking tokens,
and d_i=1 for Standard or 0.5 for Batch:

```text
C_NBP(i) = d_i * (2*P_i + 120*J_i + 12*(L_i+H_i)) / 1,000,000
C_NBP = sum_i C_NBP(i)
```

For preflight using the pricing-page example, P_i = 560 + prompt_text_tokens_i.
For measured usage, retain its actual P_i and modality split; a 560-versus-258
billing difference remains a named conservative reserve until reconciled. For the declared
4K-output route, J_i=2000; verify returned metadata and image size. Do not
charge all candidate tokens at the image rate. Read prompt/candidate modality
details and thoughts separately from usageMetadata, avoiding double counting.

For the useful mixed schedule G Standard, **all six F Batch**, R Standard:

```text
C_NBP_image_output(R) = 0.24 + 6*0.12 + R*0.24
                      = 0.96 + 0.24*R
                      = $0.96..$1.44 for R=0..2

C_NBP_doc_example_image_input(R) = 560 * (2 + 6*1 + R*2) / 1,000,000
                         = $0.00448 + $0.00112*R

C_NBP_total(R) = C_NBP_image_output(R)
              + measured_image_input_cost
              + prompt_text_input_cost
              + returned_text_and_thinking_cost
```

The six Batch faces include the accepted F probe. If the probe is submitted
in its own Batch job and the remaining five in another, the paid face count
is still six. If the creator instead selects Standard for the probe, explicitly
change the output formula to 0.24 G + 0.24 probe + 5*0.12 + 0.24R.

**Do not assume 4,096 or any other guessed thinking-token count.** Thinking
and returned text are unknown until measured. Save usageMetadata including
promptTokenCount, candidatesTokenCount, thoughtsTokenCount and modality
details. Use actual G usage as an explicitly empirical planning observation;
it does not guarantee F/R use the same tokens. Bounds/reserves are not expected
usage and must be labeled separately. Never claim a model output-token limit
is a provider-enforced dollar cap.

## GPT Image 2.6: different G and F unit costs

[OpenAI pricing](https://developers.openai.com/api/docs/pricing#image-generation):
image input $8/M, text input $5/M, image output $30/M Standard. For an image-
only raster response with I_i image-input tokens, T_i text-input tokens and
O_i image-output tokens:

```text
C_GPT(i) = (8*I_i + 5*T_i + 30*O_i) / 1,000,000
C_GPT = sum_i C_GPT(i)
```

Read the response's usage input/output modality details; retain the full JSON.
Do not treat nonzero separately reported text output as free or invent its
price: resolve that case against the selected model's actual billing. Assume
no cache discount unless eligible cached-token details actually support it.
Provider billing is the final charge; a usage calculation remains identified
as such until reconciled.

The official [output calculator](https://developers.openai.com/api/docs/guides/image-generation#calculating-costs)
can forecast O_i. For quality q, k is 48 (high), 64 (xhigh), or 96 (max).
Let a=max(W,H)/min(W,H), and round_even mean nearest-integer with ties to even:

```text
k_short = round_even(k/a)
O_q(W,H) = ceil(k * k_short * (2,000,000 + W*H) / 4,000,000)
```

For 2.6 these three quality levels use multiplier 1. Do not reuse this
expression for low/medium (their calculator multipliers differ), another
model, or input-image tokens.

| Quality | O_G at 3840×1920 | O_F/O_R at 2880² | G output fee | F/R output fee |
| --- | ---: | ---: | ---: | ---: |
| high | 2700 | 5930 | $0.08100 | $0.17790 |
| xhigh | 4799 | 10542 | $0.14397 | $0.31626 |
| max | 10798 | 23719 | $0.32394 | $0.71157 |

For the chosen high-quality Standard route:

```text
C_GPT_image_output(R) = 0.081 + (6+R)*0.1779
                      = $1.1484..$1.5042 for R=0..2

C_GPT_total(R) = C_GPT_image_output(R)
              + (8*sum(I_i) + 5*sum(T_i)) / 1,000,000
```

This is why a G estimate such as $0.166 cannot simply be multiplied by seven
or nine: a square F output has a different token count, and editing inputs
are different. Similarly, multiplying the smallest output-only fee hides costs.

The official current [input-cost documentation](https://developers.openai.com/api/docs/guides/images-vision#calculating-costs)
does **not** establish a deterministic GPT Image 2.6 editing-input token formula;
vision-model tile rules and historical GPT Image 1 rules are not a substitute.
Write unknown I_i/T_i as unknown, not zero or a guessed 10k/20k tokens. Make
one explicitly bounded G request, record actual usage, then use an F probe
(one of six) to measure the square-input case. Distinguish empirical remaining-
run projections, known output subtotal, safety reserve and actual spent cost.

OpenAI publishes half-price 2.6 Batch rates, but its model page and Batch guide
still conflict on availability. Until exact eligibility is confirmed, this
comparison uses GPT Standard. Do not silently use 2.5 or assume a Batch discount.

## First measured checkpoints: formulas versus observations

The comparison used the same frozen source; these are observed usage prices,
not an invoice or a universal flat per-image price:

```text
GPT G: (1458*8 + 94*5 + 2700*30)/1e6 = $0.093134
GPT F probe: (1444*8 + 84*5 + 5930*30)/1e6 = $0.189872
```

For the first Nano Banana G, usage reported P=456, J=2000 and H=193, plus
174 candidate tokens not classified by modality. Known classified cost is
(456*2 + 2000*120 + 193*12)/1e6 = $0.243228. Classifying the residual as text
would give $0.245316; it is not established as the exact charge. Reserving that
residual at the highest image rate, plus the documented-versus-measured input
image difference, gives conservative accounting of $0.264712. The Batch F probe
similarly has $0.122217 under a residual-at-text assumption and $0.131051
conservative accounting. Preserve all counters, assumptions and discrepancies;
do not call an unclassified token free or report a reserve as an invoice.

## Whole comparison: counts, known subtotal and cap

For B=0, G=1, F=6 per model, and R_G/R_N=0..2:

```text
N_total = 14 + R_G + R_N                 # 14..18 paid outputs
C_known_image_outputs = 2.1084 + 0.1779*R_G + 0.24*R_N
                      = $2.1084..$2.9442
C_total = C_known_image_outputs
        + GPT image/text input costs
        + NBP image/text input and text/thinking output costs
        + any explicitly allowed extra-attempt costs
```

**$2.1084..$2.9442 is not the all-in bill.** Do not invent a “likely” total by
adding arbitrary overhead tokens. For a creator-approved $5 combined cap,
maintain one shared ledger. Before each request, check actual spent + in-flight
reservations + next reservation <= $5, allowing for unknown token costs. After
the response, replace its reservation with usage-derived cost and update the
remaining empirical forecast. If the planned work no longer fits, stop rather
than silently exceed the cap, reduce resolution or claim unfinished work passed.
An agent reservation is a stop rule, not a provider billing guarantee.

## Batch and approval policy

Confirm Standard versus Batch after base acceptance and before paid work;
reuse the creator's choice. Bulk savings require the actual provider Batch API,
not n=6 or parallel Standard requests. G, a face probe, remaining F outputs and
repairs have dependencies. Batch jobs may each take about 24 hours; separate
probe/remaining-face jobs may mean multiple days. Standard G/R plus Batch F
keeps layout and repair feedback quicker. Never retry an unknown-status job.
For file-based batches, preserve a unique key per image, the uploaded JSONL
identity, job name and completion state; retrieve usage and native output for
each key before settling the reservation. A successful F probe belongs to
F6. Poll/resume the existing job rather than replacing it. Remove uploaded
input files only after completed outputs and receipts have durable copies.

Default: quote each concrete paid submission (or exact itemized Batch list)
and wait for approval. Show the full output-count formula, known costs, unknown
input/thinking components, resolution and proposed reservation first. Reuse
model/key answers; never ask for a key value in chat.

If the creator explicitly overrides this default by approving a defined
whole-run plan under a combined cap, record that authorization and proceed
within its listed counts, model, quality, modes and cap without re-asking for
every image. A bare account balance or key location does not grant that scope.
Report each submission and actual costs. Changed models/quality, extra outputs
beyond the plan or a needed higher cap require renewed approval.
