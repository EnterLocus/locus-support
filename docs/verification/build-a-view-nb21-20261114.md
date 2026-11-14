# Nano Banana 2.1 comparison extension — 2026-11-14

Scope: public static-skybox skill, same-base comparison data and experimental
trial evidence. No new generation, App runtime, Library package or catalog
publication is implied by this documentation update. Generated images stay
outside Git; downloadable identities are recorded in
[comparison.json](../../examples/skybox-comparison/comparison.json).

## Source and sampling identity

- Frozen source: 1774×887, SHA-256
  `839693327e5ce645ec0c5be03be22e4123db47543168a823b26946eab8f27c9d`.
- Original prompt unchanged, SHA-256
  `699b2e1c8794398d88d22c3aded0579bd8748b1e0ddb8f56025c3580c515e8d6`.
- API model `gemini-nano-banana-2.1`; nine Standard outputs:
  B=0, G=1, F=6, R=2, E=0.
- G: 6336×2688 returned, deterministic cyclic-context unpadding to 5376×2688.
- F: six 1660² contextual inputs, 1344² core, returned 4096²;
  actual FOV 102.010069060699°, 0.25° merge half-width.
- Native-density final: 10418×5209; no forced 12K enlargement.
- Lossless final PNG SHA-256:
  `7232c1e8f7b3beb25c5af39a95c5078a82d300083ac91cbfcaa1f5124636a0df`.
- JPEG: 15,620,534 bytes, q95/4:4:4/sRGB, no dimension change; SHA-256
  `3f7b009726ccfe39c25af6794cce51520c9a5519cdf3b1dc46046ea0c21d2e71`.

Dimensions describe sampling, not resolved photographic detail. The original
scene is AI generated; reconstructed detail is invented.

## Authorization and accounting

The creator explicitly approved G1/F6/R0..2 under a separate $2 cap, permitting
those stages without renewed per-image approval. No extra outputs are covered.
The earlier two-model cohort remains 18 outputs under its original $5 combined
authorization. All 27 counters are public with explicit cohort identities;
the new trial's costs are never charged against that earlier approval.

Current [official 2.1 pricing](https://aistudio.google.com/docs/pricing#gemini-nano-banana-2.1)
was checked on 2026-11-14: input $1.50/M, image output $30/M, text/thinking
output $7.50/M; Batch rates are half. 3780 image tokens give $0.1134 per
Standard 4K output and $0.0567 Batch. Read-only model metadata advertised Batch
support, but this trial used Standard throughout; no 2.1 Batch generation is
verified. The [cost reference](../../.agents/skills/build-a-view/references/models-and-cost.md)
keeps executed and modeled schedules separate.

Nine image outputs subtotal $1.0206000; known classified usage $1.0643055;
residual-as-text calculation $1.0942455; conservative accounting $1.1840655.
3992 candidate tokens lack returned modality classification. Conservative
accounting reserves them at image rate; the text-rate total is an assumption.
These are response-usage calculations, **not reconciled provider invoices**.
Failed/insufficient R1 is retained and charged. Free local processing adds no
image-API fee. See [sanitized counters](../../examples/skybox-comparison/usage.json).

## Independent static review and boundaries

The independent reviewer inspected six raw cube views and all 12 joins, reused
unaffected evidence, then rechecked affected nadir edges, wrap/zenith, six
matched angular directions and native repair crops. The final bounded recheck
confirmed removal of the R2-added leaf and grey ghost without a new hard
reinsertion ring at the reviewed scales. Status:
`accepted_for_static_comparison_with_disclosed_limits`.

The raw nadir crater survived insufficient R1. Native donor healing flattened
it; R2 restored grain. Local reinsertion protected landmarks; a tiny pre-R2
patch removed generated leaf/ghost pixels. Row-local sky-wrap tone correction
reduced the narrow wedge. Remaining limits: waxy/outlined foliage, soft sky,
zenith cirrus convergence, speckled/lower-relief nadir sand and a locally
smoother shell-protection patch. 2.1 is close to Pro in this scene, with better
wrap and repaired nadir; GPT's candidate retains crisper foliage, water and
sand relief. Different local repairs and one scene limit this comparison.

Locus import, physical Vision Pro appearance and comfort: **NOT VERIFIED**.
Owner headset review: **PENDING**. No model default has changed. A later default
decision must follow that review; this publication is a comparison result.

## Documentation/data validation

`tests/test_skybox_costs.py` recomputes per-request prices from public counters,
checks the two authorization cohorts and verifies the output schedule/formulas.
Skill frontmatter and local reference links are checked separately. This does
not repeat the earlier visual review or establish device acceptance.

Validation performed for this update:

- `python3 -m unittest discover -s tests -p test_skybox_costs.py`: 4 passed
  with system Python 3.9.
- Skill Creator `quick_validate.py`: passed with the installed Python that
  provides PyYAML; system Python lacks that optional validator dependency.
- Local Markdown targets in the skill, references, comparison README and this
  record: passed. `git diff --check`: passed.

Publication validation added after authoring:

- Fifteen focused checks passed: article4, accounting4, external-assets4,
  metadata/local links/localization3. All seven translated catalogs gained
  27 article keys plus one updated tutorial-card description each, with existing values unchanged; the eight-language build and
  1,104-page search index completed.
- The new offline reproduction command made zero API calls and reproduced the
  selected native PNG byte-for-byte, SHA-256
  `7232c1e8f7b3beb25c5af39a95c5078a82d300083ac91cbfcaa1f5124636a0df`.
- All nine new figure/download objects passed public HTTPS status, byte-count
  and SHA-256 readback against the asset manifest. R2 cached authentication
  could not be renewed and browser access was unavailable; the new objects
  use attachments on the existing comparison release. Existing R2 assets are
  unchanged. No generated image or ZIP entered Git.
- Independent browser review passed for all eight locales at390px, with
  English/Chinese desktop1440px checks. All ten article images loaded, the
  new figures select672w in fresh phoneDPR1 contexts, and no document overflow
  or page JavaScript errors occurred. Cost tables, scrolling formulas,
  expanded archives and download targets were checked. The exact original
  prompt and advanced tutorial placement are preserved.
- New default status is unchanged: static comparison only; owner headset
  review remains pending. Screenshot evidence is retained outside Git in
  the publication handoff, not as website binaries.

Live deployment readback is recorded in the final publication handoff after
Pages completes; a merge alone is not live proof.
