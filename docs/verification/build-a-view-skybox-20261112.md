# Public skybox authoring tools — 2026-11-12

Scope: public static-skybox workflow, provider-neutral local Python tools and
Apache-2.0 skill. No private app source or generation credentials are published.
No App runtime, catalog, website HTML or package format changes.

## Focused tooling validation

- `python3 -m unittest tests/test_skybox.py`: 5 passed after final projection
  and audit changes. Real CLI boundaries, analytic compass/direction probes,
  split/merge, wrap/poles, invalid inputs, explicit size normalization and
  diagnostic reports. Parent reviewed geometry and returned diff.
- `python3 -m unittest discover -s tests -p test_skybox_tiles.py`: 1 passed.
  An uneven 83-pixel input survives a 4×4 overlap split/join pixel-exactly;
  changed model dimensions require explicit normalization and missing tiles fail.
- `python3 -m py_compile tools/skybox/skybox.py tests/test_skybox.py` and
  `python3 -m py_compile tools/skybox/tiles.py`: passed.
- `git diff --check` and skill relative Markdown links: passed.
- No private filesystem paths or provider credentials in the public skill,
  tools or tests. Tests use portable temporary directories and remove them.

Geometry: half-pixel centers, horizontal wrap, vertical clamp; u=.5 is -Z,
u=.75 is +X. A 90-degree core spans tangent coordinates [-1,1]. Each face
carries 6 degrees of context per side; merge defaults to a 0.25-degree
half-width. All six face files are required. Normalization logs actual input
sizes and enlargement factors. Audits emit six face and twelve edge-centered
views; scalar seam diagnostics are never a visual verdict.

## Built-in image generation trial

An independent authoring agent generated a Maldives beach with the built-in
image tool; the parent independently inspected its image outputs. It exercised
public scripts and instructions once available. This was not a clean-room
public-only trial: the tester initially read internal method notes. All actual
projection, split, merge and patch commands use the public Python tools.

The whole ERP generation and restoration both returned 1774×887. A square
face edit returned 1254×1254, requiring approximately 3.03× enlargement to the
3794-pixel stored face. A local detail patch returned 1254×1254 from a roughly
1013-pixel input, demonstrating a feasible local sample density but also
reconstructed foliage/silhouette drift. Those findings motivated the optional
small-patch route and its explicit call-count and continuity cautions.

This is evidence of workflow execution and a limitation of this tested route,
not certification of uniform 12K resolved detail. A full 16-patch-per-face
built-in run has not been validated. The sample is an experiment, not a
published Library View. No paid-key API route was executed. API-specific
models, pricing and interfaces are deliberately not pinned by the public CLI.

The panorama/image audits are offline evidence. Locus import, physical Apple
Vision Pro rendering, comfort and owner acceptance are NOT VERIFIED. This
methodology publication does not require an app build or Simulator.

## Final sparse trial review

Five built-in image calls total: base, whole-panorama restoration, one detail
face (`px`), one local patch, and one targeted `pz` repair. The final JPEG is
12288×6144; only px/pz received generated face detail and four faces retain
resampled base pixels. The patch experiment is separate from that panorama.

Independent parent captures used the public audit tool on that exact final JPEG:
contact sheet, cube-pz, cube-ny, edge-px-pz, edge-py-pz and edge-px-ny.

- Output dimensions: PASS.
- Uniform 12K resolved detail: FAIL, sparse enhancement and approximately
  3.03× face normalization leave uneven density.
- Seam quality: FAIL, a visible sharpness/texture boundary crosses the surf
  in edge-px-ny; a center continuity concern remains in the repaired back face.
- Nadir: FAIL, radial pinching/starburst in cube-ny.
- Local patch integration: FAIL, reconstructed palm geometry and a sharp
  rectangular patch boundary against softer neighboring pixels.
- Uninspected native views, app import and physical device: NOT VERIFIED.

The test candidate is rejected as a finished high-quality View. Publishing the
method and tested deterministic tools does not promote this sample. The public
workflow explains these rejection conditions; full-density multi-patch editing
requires a separate bounded validation run before claiming equivalent quality.

Source, prompts, trial output, full audit, metrics and parent review evidence are
retained in the project Dropbox Workspace/build-a-view-maldives-20261112.
The Dropbox path is project evidence storage, not a public download link.
