# A full-sphere skybox, from generation to 12K

## Install and choose the image route

Use Python 3.9+ on macOS, Linux or Windows:

```sh
python3 -m venv .venv
# Windows: .venv\Scripts\activate
. .venv/bin/activate
python3 -m pip install numpy Pillow
python3 tools/skybox/skybox.py --help
```

Production authoring requires credentials for an explicitly configured image
API that returns genuinely high-resolution restoration and face edits. Nano
Banana Pro at native 4K is the previously tested baseline. Use the same
whole-panorama restoration → all detailed faces → narrow merge → repair/review
sequence when substituting another model. The Python tools exchange local
files; they do not call a provider or manage API credentials.

Codex built-in images are limited to concept/base creation in this workflow.
The Maldives trial returned 1774×887 whole panoramas and 1254×1254 faces despite
high-resolution wording. The available tool has no explicit output size,
quality or model argument. This establishes that this tested interface is
unsuitable for final high-resolution enhancement, not a universal claim about
the underlying model or every OpenAI image product.

Choose provider, model, exact requested dimensions, quality and budget before
paid work. Save request identity, input/output hashes, actual returned sizes
and response usage after each result. Verify dimensions before resampling;
do not automatically retry interrupted requests with unknown billing status.
Never put credentials in source, manifests, prompts or logs. Do not fall back
to lower resolution to complete a run.

### Model choice, costs and approval

Offer Nano Banana Pro and GPT Image 2.6 Sunburst. Before generating, ask the
creator which API/model to use and the environment-variable name or secure
credential reference for its key; never ask them to paste a secret. Read
[models, per-View costs, bulk discounts and the quote contract](models-and-cost.md).
The article gives dated output subtotals and separates them from billed cost.

Before **each** paid generation/edit submission, quote the specific requests
and wait for explicit approval. A declared batch can be approved as one exact,
itemized list; later stages, retries and repairs require fresh approval.
Choosing a model, supplying a key or discussing an overall budget is not
approval to generate. Keep exact native-size and quality checks for both models.

## 1. Generate the world before the detail

Example creator brief: a deliberately classic Maldives beach. Ask for:

> A photorealistic full 360 by 180 degree equirectangular environment panorama,
> exactly 2:1, from one stationary eye-height viewpoint on a Maldives island
> beach. A level sea horizon, turquoise lagoon, pale sand and palms behind and
> beside the viewpoint. Clear tropical daylight with a consistent sun direction.
> The image center is the initial forward view toward the lagoon. The left and
> right image edges are the same direction and must continue seamlessly.
> Include the entire sky at the top and ground under the camera at the bottom,
> with correct spherical pole distortion. No panorama collage, repeated views,
> text, watermark, border, foreground people or camera equipment.

This is an invented place, not a faithful representation of a named resort.
Review a perspective audit immediately. A wide beach photo, even if cropped to
2:1, is not a full sphere. Do not stretch a non-2:1 output to conceal the failure;
ask for a corrected sphere. The CLI rejects non-2:1 sources.

## 2. Restore ambiguous regions once, with global context

For a low-resolution AI base, first perform a native approximately 4K-wide
whole-panorama API restoration; do not continue if the returned image is still
1774×887 or similarly undersized. Separate deciding
what the objects are from preserving them at higher density. Enhancing six
blurry faces independently tends to preserve blur or invent incompatible objects.

> Restore this full-sphere equirectangular panorama into a sharp photograph.
> Resolve smeared fine structure with plausible detail continuous with its
> surroundings. Preserve the exact layout, object positions, perspective,
> horizon, exposure, colors and light direction. Keep smooth sky smooth.
> Preserve the 2:1 spherical projection and continuous left/right wrap.
> No added objects, grain, text, borders or watermark.

Use this only on AI content or with explicit permission for reconstruction.
For real photographic coverage, keep the original pixels and document any
reconstruction separately; this initial public workflow does not implement
photo-to-invented-world capture fitting.

Put a broken wrap in the center before a targeted edit:

```sh
python3 tools/skybox/skybox.py roll source.png rolled.png --degrees 180
# Edit rolled.png. Repair only the center join, preserving the rest of the sphere.
python3 tools/skybox/skybox.py roll rolled-repaired.png restored.png --degrees -180
```

Inspect both the repaired center and the edit output’s outer edges before accepting
it. A model can repair one seam while creating a new one at its own frame edges;
unrolling moves that new discontinuity to the panorama center. Rolling alone
does not make a generated image seamless.

A smooth exposure mismatch may need gentle local tone correction. A duplicated
palm, shifted shoreline or broken cloud needs a content repair; blurring the
join just turns it into a soft vertical band. Reject large layout drift before
proceeding. Fidelity measurements are diagnostic, especially when a successful
repair is supposed to differ from a defective source.

## 3. Pixel density and splitting

The output target is 12,288 × 6,144: about **34.13 pixels per degree** at the
equator. A 90° ERP span therefore has 3,072 columns. A perspective face's
pixels have nonuniform angular density: a 3,072-pixel core is a convenient
working convention, not a claim of constant 34.13 px/degree in that face.

A 1,774-wide panorama provides only about 443 columns over 90°. Asking a
preservation model for a single 7–8× leap often preserves the original blur.
A coherent restored panorama around 4K wide is required to reduce that leap. Always record
actual model output dimensions: requesting 4K or writing “12K” does not produce
that many independent samples.

```sh
python3 tools/skybox/skybox.py split restored.png faces --core-size 3072 --overlap 6
```

The six files are `px`, `nx`, `py`, `ny`, `pz`, `nz`, plus geometry metadata.
Each face sees 90° + 6° on either side = **102°**. In this grid a 3,072 core
has roughly 3,794 stored pixels per side (`3072*tan(51°)`, rounded by the tool).
Keep that whole stored frame for every model edit. Do not trim margins or
change the field of view. `nz` looks forward; `pz` contains the original ERP
wrap in its center; `py` and `ny` look up and down.

Enhance one detailed face at a time using it as the edit target:

> Enhance the supplied perspective image with resolved photographic fine
> detail. Keep every object, edge, silhouette, shadow, color, exposure and
> perspective in precisely the same place. Preserve the full square frame,
> including all overlap margins. Do not zoom, crop, add or remove objects.
> Keep smooth sky and gradients smooth, without grain or invented stars.

Do not describe scene content again: words can override what is actually in
the face. Inspect palms, shorelines, buildings and horizon against the input.
A featureless sky face can remain the deterministic source projection. This
preserves its smoothness; its file size is not evidence of new detail.

Keep originals in `faces/`; put accepted edited faces and a copy of its metadata
in `enhanced/`. Every face with meaningful detail must be enhanced: vegetation,
sea, clouds and sand are not featureless. Do not copy four detailed faces through
as the Maldives trial did. A truly featureless sky face may remain a source
projection; retain the reason for that exception. Square outputs at different sizes can be
explicitly normalized by the merge command, with recorded enlargement factors.
A nonsquare result or changed framing needs correction, not an automatic resize.
Do not stretch or globally standardize contrast to hide structural disagreement.

### Reject undersized face outputs

A 1024–1254 square output is insufficient for this whole-face route. Stop and
correct the API size/settings or provider. `--normalize-faces` records a
resample; it does not certify or recover detail. Verify each face against its
native input, not against an already enlarged copy. Default to native 4K faces
with the tested provider. A smaller high-resolution API route, such as the
2880-square OpenAI configuration above, requires its own baseline comparison
and explicit dimension record before it can be considered equivalent.

`tools/skybox/tiles.py` remains available as an experimental local split/join
utility. The trial's single detail patch changed foliage silhouettes and made
a sharp rectangle against its neighbors. Its correct deterministic roundtrip
does not establish successful generative integration. The unvalidated 80–96
small-patch route is not a recommended replacement for high-resolution faces.

## 4. Merge with a narrow transition

```sh
python3 tools/skybox/skybox.py merge enhanced panorama.jpg --width 12288 --blend 0.25 --normalize-faces
python3 tools/skybox/skybox.py audit panorama.jpg review
```

Only run this final export after every required face has passed its native
resolution, fidelity and adjacency checks. Use lossless PNG checkpoints. The
current JPEG export uses quality 100 and 4:4:4 sampling; it preserves detail
already present but cannot create detail. On the failed low-resolution trial
it produced a roughly 43 MiB file without corresponding image quality. Do not
export an oversized final as a workaround for missing native detail. Narrow blending uses 0.25° on either side of the geometric boundary:
0.5° total, roughly **17 ERP pixels at the equator**. The 6° input context
and the 0.25° blend solve different problems. A broad cross-fade between
inconsistent faces makes double palm trunks and ghost shorelines. A narrow
join keeps detail, but it cannot align objects that the model moved.

If a join remains broken, repair a face centered on that direction with
sufficient context, then merge and review again. A simple wrap repair belongs
at the center of a rolled panorama or the `pz` face. Preserve neighboring good
pixels. Avoid unlimited rerolls: agree on a small attempt budget, record failed
outputs, and discard a candidate if repeated content drift remains.

For sky dots or noise, prefer retaining the smooth source sky or an explicitly
reviewed sky mask with a soft boundary. Do not apply a blanket blur that wipes
cloud edges, palm fronds and roof silhouettes. Masked sky replacement and
arbitrary rotated repair-face reinsertion are manual image-edit steps in this
initial toolkit; the CLI does not claim to automate them.

## 5. Review and handoff

Inspect the audit contact sheet and full-size perspective images, then inspect
representative native-resolution crops. Check forward, behind, left, right,
zenith, nadir, all side and pole cube joins, and the wrap. Inspect horizon
level, scale, pinched poles, duplicate palms, warped structures, water and sky
tone, edge sharpness and blurry near-ground patches. Metrics help locate
trouble; high-frequency noise can improve a sharpness score without adding
useful detail. A seamless resized source can still look blurry.

Record source and output hashes, prompt for every call, actual returned sizes,
which faces were generated versus copied, normalization factors, rejected
attempts, repairs and remaining findings. Report separately: output dimensions,
resolved detail, spherical continuity, Locus import, physical headset appearance.
An independent reviewer should inspect the files and collect its own crops.

Deliver only a visually accepted `panorama.jpg` as a standalone static View image. In Locus, use Places
→ Import → Import a View, select Files, open the panorama, and inspect the exact
result on Apple Vision Pro. Locus derives its preview and lighting images on
import. The existing [Make a View tutorial](https://enterlocus.com/make-a-view/)
and [complete Package v2 guide](https://enterlocus.com/reference/locusplace-format/)
cover app import and optional reusable packaging with provenance and stable IDs.
Use the actual installed target version when validating a package. Do not
bundle credentials, Python, prompts or tool code as runtime extensions.

A beach skybox contains painted water. This workflow provides no water surface,
wave animation, shore geometry, depth or parallax. Midground, celestial Views,
computed water, beach geometry and procedural sky are future layers with
separate authoring and acceptance requirements.

## Correction after the Maldives trial

The previous public version weakened the established method in material ways:

| Stage | Established high-resolution method | Failed trial / earlier public default |
| --- | --- | --- |
| Whole restoration | Native roughly 4K panorama before face work | 1774×887 in and out |
| Detailed faces | Native high-resolution edits for all detailed directions | Two 1254-square edits, four copied faces |
| Density | Detail reconstructed before final grid normalization | 3.03× face enlargement and much larger base enlargement |
| Repairs | Wrap and smooth-sky correction at restoration and final stages | Public tools provide projection/audit, not automatic wrap/sky repair |
| Fidelity | Layout/detail gates, neighboring faces and accepted baseline comparison | Diagnostic NCC did not prevent visible density and structure discontinuities |
| Delivery | Reject failed assets before final delivery | Oversized failed sample delivered for trial |

The public projection utilities are not a complete port of the internal
restoration, sky-frequency cleanup, row-local wrap correction or provider
runners. This guide requires those repairs as needed, using a reviewed image
edit/mask or suitable equivalent implementation, and never treats a successful
merge command as proof they happened. A rotated broken wrap is still broken
until its repaired center and new image edges both pass visual inspection.

This correction restores the high-resolution API prerequisite and complete
face/repair acceptance requirements. It does not claim a new accepted scene or
validated replacement model. The failed trial and its original findings remain
in the [verification record](../../../../docs/verification/build-a-view-skybox-20261112.md).
