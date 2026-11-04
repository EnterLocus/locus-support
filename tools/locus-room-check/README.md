# macOS Room checker

Run from the public repository on **macOS 15 or later**, with Xcode or Command
Line Tools and Python 3.9 or later. `usdchecker` and `usdcat` must be on PATH.
No Locus source checkout, account, API key or paid service is required.

```sh
python3 tools/check_room.py --current-app-version 1.4.4 --json \
  --renders ./renders ./my-room.locusplace
```

Use the version actually installed on Vision Pro. The version is mandatory;
validation against a development branch does not establish compatibility.
Package v2 and legacy flat Room ZIPs are recognized automatically. The SwiftPM
executable builds through `xcrun --sdk macosx` in a private temporary directory,
removed on completion. Non-macOS hosts fail explicitly rather than offering a
reduced check that could be mistaken for success.

## Layers and exit status

* **S, structure:** archive safety, integrity, public schema, resource budgets,
  complete image decode, USD validation (`usdchecker --arkit`) and model counts.
  It also applies the App's ModelIO triangle, material-object and entity budget
  rules to each Room scene plus separate collision model, and each View
  midground model. A ModelIO budget failure makes the check invalid.
* **B, binding:** the shared public RealityKit entity resolver used by both
  archive validators. Exact, unique names; geometry and subtree overlap checks.
* **E, entry:** always load the model, even if no entities are referenced; check
  finite, nondegenerate bounds; nonempty seat list; nonzero upright seated
  quaternion (normalized up vector x/z < 0.0001 and y > 0.9999); desk basis,
  bounds and Hide Desk ancestry; authored positive emission and opacity of
  illuminated/indirect surfaces; animation names in the loaded animation library.
* **W, risk:** seat eyes, 0.15 m eye-to-geometry-bounds clearance, horizontal
  span below 1.5 m, model spans above 80 m, double-sided USD declarations,
  connected roughness/metallic texture risk, triangle/material/entity/texture budget usage, and isolated mesh centers more
  than max(10 m, 8 times the median center distance) from the median geometry center. These are heuristics, not proof of rendering failure.
* **R, render (when requested):** seat forward (`yaw-0`), seven other yaw
  directions, up/down and authored exterior preview, PNGs plus a contact sheet.

Only errors affect exit status (0 valid, 1 invalid; argument errors use 2).
JSON lists completed layers, errors, warnings, the macOS runtime, elapsed wall
clock time, each seat's coordinates and produced image paths. `modelIO.groups`
reports counts and limits for each Room or midground; Room totals combine the
scene and separate collision. Existing `rooms[].budgets` counts come from
flattened USD and use a different counting method, so the numbers can differ.
ModelIO results reflect this Mac's OS and ModelIO implementation, not the
installed visionOS build or a guarantee that device import will succeed. Per-Room
`room-N/seat-N/` output directories use indices so author-controlled names never
become filesystem paths; the report maps each seat index to its authored ID.

The eye scaffold uses the **delivered model's** visual bounds: interpolate
`anchorXZ` over min/max XZ, floor = minY + `sourceFloorOffset`, eyeY = floor +
`eyeHeight`. Yaw is the authored model rotation about +Y; camera forward in
model space is `[sin(yaw), 0, -cos(yaw)]`.

## Render scaffold

Resolution is 640 by 360, vertical field of view 75 degrees for seats and
45 degrees for exterior preview. Lighting is fixed: a constant RGB 0.5 gray
128 by 64 environment generated from source, IBL exponent +2, and a white
1500-lux directional light aimed from (3,5,2) toward the origin. Contact-sheet
labels explicitly say **scaffolded**. This is diagnostic lighting, not the
Room's appearance with a selected View. Files in an existing output directory
are overwritten; choose a fresh directory for each candidate.

The renderer does not implement head-pose seating, Move Seat offsets, desk
alignment, personal seat safety, Summon, water/waves, texture flow, surfing,
procedural sky/celestials, light controls/proxy rigs, baked-light-layer mixing,
View IBL or View sun. Declarations still receive structural checks; these
runtime effects are not simulated in diagnostic pictures.

## Limits

macOS RealityKit and visionOS RealityKit differ in renderer, tone mapping,
lighting, shadows and platform versions. B/E are structural checks; W/R are
approximations. Emission detection checks authored texture/color and intensity,
not whether the texture's pixels actually emit visibly. Clearance checks use
bounding boxes and can warn around empty space inside a concave object.
Connected roughness and metallic textures are reported conservatively, including
separate images; inspect the source before changing it. Double-sided geometry
is a risk warning, not an unconditional error.

The checker is intentionally conservative: all three desktop extents must exceed
0.0001 m; zero-thickness desks may not fail every installed reader. The public
structural validators also reject procedural USD primitives (Sphere, Capsule,
Cylinder, Cone, PointInstancer), instancing, and archives failing `usdchecker`;
they limit flat captions to 1000 UTF-8 bytes. These are authoring restrictions,
not claims that every reader rejects the same data.

Comfort, scale perception, tracking, Room Portal, real desk detection/alignment,
frame rate, lighting appearance and sound require Vision Pro. Offline validation
cannot determine import allowance or conflicts with content already installed.
No successful check guarantees device acceptance. E rules are maintained semantic
checks, not private runtime code; cross-repository fixture parity is tracked
separately. Detailed mesh attribution of USD warnings remains a future improvement.

## Measured diagnostic examples

On an Apple M4 Pro running macOS 27, after shader caches were warm, the
one-seat source fixture took about 0.26 seconds for R (11 views plus its sheet),
and the 9.9 MB Atrium model took about 0.56 seconds (21 views plus its sheet).
The Atrium command took 12.6 seconds including validation and a fresh Swift
build. `renderDurationSeconds` measures only R; model loading, archive checks
and Swift compilation are outside that number. These timings describe these
small examples, not device frame rate or a performance budget.

The source fixtures in `tests/render_risk_fixtures.py` provide a reproducible
platform spike. On this Mac, a wall declaring `doubleSided = 1` disappeared
from the rear, while explicitly authored reverse-facing geometry restored it.
A packed ORM texture and equivalent separate grayscale maps both loaded with
roughness/metallic texture bindings and showed no blackening in this synthetic
case. The ORM symptom was therefore not reproduced here; it remains a warning,
not an entry error. Inspect the exact model on Vision Pro.

Entry errors still allow requested diagnostic images when finite model bounds
and seat eyes are available. Structural/binding failures prevent unsafe render
attempts. Missing Metal GPUs are reported as errors by the CLI; CI tests may
explicitly skip the GPU-only assertion while retaining S/B/E coverage.
