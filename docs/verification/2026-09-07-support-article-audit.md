# Support article and Room authoring verification

## Scope and reference

Read the 11 HTML pages, format reference, repository and asset READMEs,
authoring skill and its references, and the screenshot/research documents.
Product claims were compared with Locus source at `5a13c076` and immutable
release tags where build compatibility mattered. Historical research and
experimental guidance retain their stated scope; they are not new device
acceptance results.

Confirmed corrections cover multiple real walls in Room Portal (no ceiling),
local image processing on Save as View, Room v5 build compatibility, public
Room inputs and runtime behavior, provenance alternatives, per-Room lighting
controls and saving, Browser defaults, audit commands, and the direct-image
4K gate versus View ZIP validation.

## Public tool regressions

On macOS, run:

```sh
python3 -m unittest -v tests/test_site.py
# In a Python environment with Pixar USD installed:
python3 -m unittest -v tests/test_room_audit.py
```

Results: 28 site/tool tests and 2 USD audit tests passed. The new cases use real
USD compositions, PNG payloads, ModelIO, RealityKit and CLI entry points:

- A valid small model passes; a model with 100,001 actual entities fails even
  without author-supplied quality metadata.
- A 16,384-pixel-wide embedded texture passes; 16,385 fails.
- A 2,048 × 1,024 View ZIP passes: it does not inherit the direct-image gate.
- Legacy downward spots pass the optional audit; v5 requires explicit direction.
- A missing baked-indirect receiver fails the optional audit.

The validator and audit distributed inside the offline skill match the public
tools byte for byte. Existing complete Room examples still pass. The app
source was not changed, so no app regression suite was required for this PR.

## Original Room built from the public walkthrough

Ran `tools/build_minimal_room.py` from an empty Blender 5.2 scene, using only
the public scaffolder, packer and validator. The output contains one desk,
one seat, two walls, a roof and one controlled pendant, with no external assets.
Reviewed the exterior thumbnail and six seated renders. Floor height is
calibrated from the delivered model's minimum Y, including the slab thickness.

The USD audit resolved 11 explicit fade bindings and one directed spotlight.
Two packer runs over the final source produced identical ZIP bytes. A separate
RealityKit load confirmed bounds of approximately `(-2, -0.16, -2)` to
`(2, 2.7, 2)` meters, agreeing with the exported USD composition.

| Artifact | SHA-256 |
| --- | --- |
| Builder script | `91fe5831cdd465db0e167982e803f91c9410f4397f52797a3c724ebd02e19981` |
| Validated Room ZIP | `cea64b7af27937c1851fda53b014389e4f19099a68b1b43ab5361d25e9b00e2c` |
| Delivered USDZ | `2a2bf732edaf29dca31ff49500b0a95af28eaa77b976bccf4357a65da24d8c3b` |

Built Locus Dev from the reference source and installed it on an owned
visionOS 26.5 Simulator. The DEBUG acceptance import calls the real product
importer; it bypasses the Files picker. The Room appeared in Places, entered
Virtual Space with Autumn Hill View, and exposed Primary Pendant in Room Quick
Settings. Repeated with a fresh app container and the final calibrated ZIP.
The installed USDZ and thumbnail matched the final source bytes. This proves
import, model loading and the declared lighting UI, not physical desk alignment,
light appearance, reach, tracking or comfort. The owned Simulator was deleted
after use.

Reviewed the changed web pages locally, including expanded FAQ answers and
the minimal walkthrough at desktop and 390-pixel phone widths. Neither of those
phone layouts overflowed the page. Screenshots and generated binary artifacts
are kept outside Git. No website deployment or merge is part of this audit.

Physical Room Portal behavior, Mac Virtual Display sessions, real passkey
authentication and device comfort were not re-tested during this audit. The
ceiling limitation is a confirmed product boundary; no unsupported SDK-cause
claim was added.
