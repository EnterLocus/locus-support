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

The default image producer is Codex's built-in image tool. Ask the agent to
create/edit an image, inspect the returned result and save the actual file
into your working directory. Load each local edit target into the image tool's
context before editing it. An agent tool call and a Python CLI command are
separate steps: there is no public HTTP endpoint for invoking this workflow's
built-in tool from the CLI. Save checkpoints so an interrupted session resumes
without silently generating duplicate images.

Optional API route: submit the same inputs and prompts through your chosen
provider, download its output and continue with the identical local commands.
Nano Banana Pro gave good results in our earlier experiments; it is an option,
not a prerequisite or a promise that another model will behave identically.
Choose the provider, model, credentials and budget explicitly. Do not reuse
historical price or resolution tables: check the provider's current interface.
Square faces make provider-specific aspect-ratio restrictions easier to handle.
No model identifier or SDK is hardcoded in these scripts.

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

If the base is smeared, first ask for a whole-panorama edit. Separate deciding
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
A coherent restored panorama around 4K wide reduces that leap. Always record
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

Keep originals in `faces/`; put edited faces and a copy of its metadata in
`enhanced/`. Copy unedited faces too. Square outputs at different sizes can be
explicitly normalized by the merge command, with recorded enlargement factors.
A nonsquare result or changed framing needs correction, not an automatic resize.
Do not stretch or globally standardize contrast to hide structural disagreement.

### When the model returns small faces

If the image tool returns only about 1K square, enlarging one face to 3,794
pixels cannot deliver the desired density. Use smaller overlapping detail
patches, or choose an API that returns larger faithful face edits. The optional
patch tool works within each perspective face; it does not make additional
spherical camera assumptions:

```sh
python3 tools/skybox/tiles.py split faces/nz.png nz-tiles --grid 4 --context 32
# Edit each patch separately, preserving its full square framing and overlap.
python3 tools/skybox/tiles.py join nz-tiles enhanced/nz.png --normalize-tiles
```

For a 3,794-pixel face, a 4×4 grid with 32-pixel context makes approximately
1,013-pixel square requests. A real 1,024-pixel model output can then supply
the density locally, instead of one 1,024-pixel image being enlarged across
the entire face. The join uses feathered context and records actual returned
sizes; preserving a crop's layout is still essential. A resized input tile
alone adds no information. Keep the whole accepted face as context for the
agent, but identify each patch as the edit target so the model does not replace
it with the whole view.

This can require **16 edits per detailed face**, up to 96 for all six faces.
Skip smooth sky patches; first test one representative ground/vegetation patch
and inspect the seams before committing to the full run. Establish a bounded
call budget with the creator. Local split/join roundtrips are tested; a full
96-edit built-in generation run is not an established quality guarantee.

## 4. Merge with a narrow transition

```sh
python3 tools/skybox/skybox.py merge enhanced panorama.jpg --width 12288 --blend 0.25 --normalize-faces
python3 tools/skybox/skybox.py audit panorama.jpg review
```

Use lossless PNG checkpoints. The JPEG export uses high quality and 4:4:4
sampling. Narrow blending uses 0.25° on either side of the geometric boundary:
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

Deliver `panorama.jpg` as a standalone static View image. In Locus, use Places
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
