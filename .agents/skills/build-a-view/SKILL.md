---
name: build-a-view
description: Plan, author, repair, and package any Locus View — routing across static 360° skyboxes, 3D midground and large-scale 4-layer parallax worlds (`skyRadiusMeters` up to 1600 m, 3D-baked standees, `ambientAnimations`, `interactiveStates`, `flowingWater`), realtime water and computed surf (`shore`), procedural night skies, painted clouds, 24-hour `sunPath` day/night blends, looping panorama video, fireflies, point lights, spatial sound, and `celestial`, `nearOrbit`, and `blackHole` profiles. Excludes Room-only authoring (`build-original-locus-room`).
---

# Build a View

Plan, author, refine, and package any Locus View into a validated Package v2
(`.locusplace`) archive — from a standalone 360° × 180° SDR equirectangular
skybox to a full multi-layer world with 3D midground, water or breaking surf,
24-hour daylight, animation, interactivity, spatial sound, or orbital/black-hole
profiles.

Resume at the stage the creator needs: adding spatial sound, tuning `shore`
parameters, converting an existing View to day/night, or optimizing midground
textures does not require regenerating a base panorama. Preserve source assets
and save edits separately. This public skill, `tools/skybox/`, and the public
authoring tools are Apache-2.0. Commands run from a clone of the public
`EnterLocus/locus-support` repository; no private app source, internal tools,
or private catalog paths are used.

## Choose your View route

Most modern Views combine a 2:1 SDR panorama with one or more orthogonal
capability layers. Load only the references needed for the tracks the creator
asks for:

| Track / View capability | Read next |
|---|---|
| **1. Static 360° skybox** — concept base, restoration, 6-face enhancement, frequency-split merge, seam/wrap repair, native resolution & cost quotes | [Skybox workflow](references/skybox-workflow.md), [models and costs](references/models-and-cost.md), and [native resolution](references/resolution.md) |
| **2. 3D midground & large-scale parallax** — `midground.usdz`, `skyRadiusMeters` (`80..1600`), 4-layer parallax (`< 150 m` real 3D + `>= 150 m` 3D-baked standees), terrain/foliage/rock/VRAM craft, `skyEntities`, `windSway`, `textureFlow`, `flowingWater`, View `ambientAnimations` & `interactiveStates` | [3D midground](references/midground-3d.md) |
| **3. Realtime water & breaking surf** — painted waterline rules, `water` (`ocean`/`still`, `bed.deepening` & `macro`, `reflectionRegistration`, `contactCalibration`, `glow`), and computed `shore` (`1.4.9–1.4.11`, 4-edge bed taper, night horizon calibration) | [Water and shore](references/water-and-shore.md) |
| **4. Sky, clouds & 24-hour daylight** — procedural night `sky` (`stars`, `milkyWay`, `moon`, `aurora`), painted `clouds`, and `environment.sunPath` (`daySky`, `panoramaGrade`, `light`, `panoramaBlend`, cloud-preserving dual masks) | [Sky, clouds, and daylight](references/sky-clouds-and-daylight.md) |
| **5. Video, atmosphere & spatial sound** — looping `.mp4` panorama regions (`media` + `media.dayNight`), `fireflies`, `pointLights`, and View `sound` v1/v2 | [Video, atmosphere, and sound](references/video-atmosphere-and-sound.md) |
| **6. Space & orbital profiles** — `blackHole`, `celestial` v1/v2 (`rings`, `advection`), and `nearOrbit` v1/v2 (`tiles`, `surface`, fallback proof) | [Space and black hole Views](references/space-and-black-hole.md) |
| **Packaging & delivery** — Package v2 `.locusplace`, `thumbnail.jpg` vs `lighting-ibl.jpg`, `environment.condition`, ASTC KTX1 `gpuTextures`, `localizations`, validation & Apple Vision Pro check | [Package v2 delivery](references/package-v2-delivery.md) |

A clone of `EnterLocus/locus-support` also carries complete offline format specs
(`reference/locusplace-format.md` and `reference/locus-asset-format.md`), JSON
Schemas (`schemas/locusplace-v1.schema.json`, `schemas/provenance-v1.schema.json`,
`schemas/room-interactive-states-v1.schema.json`,
`schemas/view-celestial-v1.schema.json`, `schemas/view-celestial-v2.schema.json`,
`schemas/view-near-orbit-v1.schema.json`, `schemas/view-near-orbit-v2.schema.json`,
`schemas/view-black-hole-v1.schema.json`), and a stdlib package-builder
reference (`examples/locusplace/build_examples.py`). See
[Package v2 delivery](references/package-v2-delivery.md) for which scripts
under `tools/` are CLIs versus importable Python helpers.

## Core View authoring principles

- **Separate far skybox from real 3D geometry**: static panorama pixels provide
  no depth, motion, or parallax. When a View is meant to hold up under elevated
  Rooms or `Glide` / `Move` locomotion, keep the 2:1 panorama strictly far-only
  (distant peaks, open horizon, sky) and build everything inside the playable
  envelope (`< 150 m` on `skyRadiusMeters: 1600` worlds) in real 3D. Never put
  2D cutout billboards inside the reachable/near zone.
- **Design every View to coexist with arbitrary Rooms**: Room
  `viewMidgroundVisibility` (`terrainOnly`/`hidden`) is deprecated for new Rooms
  because large-scale Views keep their land in `midground.path`. Always isolate
  walkable/gradable ground in `terrainEntities`, keep the central ground gentle
  enough for Room placement, and split near props into tight-bounded individual
  units so Room keep-out hides only colliding items.
- **Respect capability coexistence and version floors**:
  - `blackHole` (`1.3.4+`) and `nearOrbit` (`1.3.0+`) exclude `celestial`,
    `sky`, `media`, `midground`, `water`, `shore`, `fireflies`, `clouds`,
    `pointLights`, `environment.sunPath`, and `skyRadiusMeters`.
  - `shore` (`1.4.9+`) excludes root `water`, `midground.water`, space
    profiles, and any Room `ocean` region in the same package.
  - `environment.sunPath` (`1.3.0+`) requires `sunFreeSky: true` and a
    `sun-free-sky` provenance entry, and excludes `environment.directSun` and
    static `sunVisibility` bakes; `daySky` / `panoramaGrade` / `light` (`1.4.9+`)
    exclude `clouds`, `midground.water`, `midground.flowingWater`, `sky.aurora`,
    and `media` (unless paired with `media.dayNight`, `1.4.11+`).
  - Always pass `--current-app-version <target-version>` explicitly to
    `tools/pack_locusplace.py` and `tools/validate_locusplace.py` (default is
    conservatively `1.0.0`).
- **Keep verification boundaries honest**: metrics (seam ratios, sharpness
  scores, NCC) locate defects but never certify visual quality; flat renders and
  perspective audits are distinct from Locus import and physical Apple Vision
  Pro stereo depth, glare, frame pacing, and comfort review.

## Paid-API and static-skybox checkpoints

Whenever a View requires paid image/3D/audio generation — especially Track 1
(static 360° skybox restoration and 6-face enhancement) — enforce two strict
creator checkpoints (full step-by-step workflow in
[Skybox workflow](references/skybox-workflow.md), pricing formulas in
[models and costs](references/models-and-cost.md), and native sizing in
[native resolution](references/resolution.md)):

1. **Checkpoint 1 — Freeze the base layout first**: start from a supplied
   panorama or a host built-in 360° base (do not begin by asking for a paid API
   key). Present the actual panorama (with native 360° preview where supported,
   plus perspective/seam crops), wait for layout acceptance, and freeze its
   exact file, dimensions, prompt, and SHA-256.
2. **Checkpoint 2 — Quote before every paid submission**: offer tested API
   routes (Nano Banana Pro baseline, Nano Banana 2.1 lower-cost candidate, GPT
   Image 2.6 Sunburst), ask only for missing model and environment-variable /
   credential-file references (never paste secrets in chat), offer Standard vs
   Batch where eligible, and quote the full stage plan `N_paid = B + G + F + R + E`
   with output + input/thinking charges and calculated native ERP size (never
   promise 12K or force-enlarge undersized faces). Wait for explicit creator
   approval before submitting paid calls unless the creator explicitly
   authorizes a declared full plan under a combined cap.

## Worked examples

Finished Locus Views are published as worked examples. The manifest is
<https://enterlocus.com/data/place-examples.json> (in a clone,
`data/place-examples.json`); people can browse the same files at
<https://enterlocus.com/gallery/?examples>. Records with `kind: "view"` give
`packageID`, `title`, `license`, `features`, a `package` (`contentVersion`,
`minimumAppVersion`, `url`, `byteCount`, `sha256`), and usually `source: null`.
View feature ids are `video` (looping video regions), `water`, `flowing-water`,
`shore`, `midground` (3D midground USDZ), `day-night`, `procedural-sky`,
`celestial`, `clouds` (animated cloud sea), `particles`, `interactive-states`
(pinch-operable midground props, Locus 1.6.0+), and `sound`. Those
features correspond directly to the capability references in this skill; use
these packages to study how a finished View structures its assets, `destination.json`,
thumbnail, appearance, and `provenance.json`. Room-only ids such as `room-tv`
(Room TVs) and `baked-irradiance` (v14 baked irradiance lightmaps) are explained
in the build-original-locus-room skill.

A record may also have `upcoming`: a newer revision for a Locus `appVersion`
that is not public yet, with its own `package`, `source`, `features` and
optional `notes`. The current public App cannot install it; use the main
`package` unless the creator targets that version, and check an upcoming
revision with that release's public tools: the current validator may not know
its newest fields yet. At release closeout the upcoming revision becomes the
main entry.

Check `byteCount`, download into scratch space, compare `shasum -a 256` with
`sha256`, validate with `python3 tools/validate_locusplace.py
--current-app-version <target-version> <file>`, then unzip and read
`locusplace.json` and `catalog/destinations/<destination-id>/destination.json`.

Examples marked `LicenseRef-EnterLocus-Example` (version 1.1) may be studied,
changed and used freely as templates for the creator's own Views, and what the
creator makes may be used anywhere, including commercially. When the result
will be part of a commercial product or service, or sold, replace the example's
panoramas, video and sound with the creator's own: renamed, recoloured,
rearranged or partly swapped example assets still count as the example. Never
re-upload the original files (link to the Gallery page instead), and do not use
Locus names, logos or app icons or imply endorsement by EnterLocus.com.
Third-party components keep the terms in each `provenance.json`. Full terms:
<https://enterlocus.com/asset-rights/#example-license>.
