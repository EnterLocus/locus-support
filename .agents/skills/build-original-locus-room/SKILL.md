---
name: build-original-locus-room
description: Build, package, validate, and runtime-check an original 3D Room for Locus using the public Room ZIP, seat, entity, desk, lighting, optional experimental animation, provenance, and verification contracts. Use when creating a new Room from a brief or adapting an original professional 3D scene for Locus.
---

# Build an Original Locus Room

This is a sample skill for taking an original Room from concept to an exact,
importable Locus ZIP. Use the creator's preferred professional 3D workflow.
Concentrate on the Locus interface, deterministic packaging, and honest
verification; preserve the creator's modeling judgment.

If the request starts from a blank brief, use an available professional 3D
authoring tool to create the geometry, materials, lighting geometry, and camera
views. Do not stop after producing metadata or a package skeleton. If no such
tool is available, state that limitation before promising a finished Room.

Read these local references before authoring:

- `references/room-interface.md` for the current Room v1-v3 contract, optional
  experimental Room v4 animations, and exact delivery gates.
- `references/design-language.md` when designing a new Room or judging whether
  it belongs beside the public Locus examples.

The online [Room ZIP reference](https://enterlocus.com/reference/locus-asset-format.md)
is canonical when network access is available. The bundled reference is enough
to work offline and prevents an unavailable website from blocking the task.

## Establish the deliverable and rights

Write down the intended Room, important views, entry seats, optional desks,
Room Portal surfaces, and visitor-controlled lights. State any assumption that
changes the Room interface or delivered files.

Before authoring, inventory every model, texture, image, font, and generated
input. For each non-original component, retain its creator, exact source URL,
license identifier and URL, and any required credit. Do not describe a
composite Room as wholly original when third-party components remain embedded.
Use only material that permits redistribution inside the delivered USDZ.

Record creators, sources, rights, requested credit, modifications, and AI use
truthfully in `provenance.json`. Set `aiGenerated` to `true` and name every
generative AI provider that materially contributed in `aiProvider`. A
permissive component does not become proprietary merely because it is packed
inside the Room; say which parts are third-party in `modificationNotes` and
point `sourcePageURL` to a durable notices page when several sources must be
listed.

`aiProvider` names the generative AI service or model, not the DCC, renderer,
exporter, scripting language, or ordinary build tools. Make sure a custom
`rights.url` actually publishes that exact statement; otherwise use the
matching standard or project license object.

## Design and author the Room

- Create an original, coherent environment rather than copying a public demo.
- Export one self-contained, meter-scale, +Y-up USDZ with world -Z forward.
- Give every metadata-referenced entity a stable, unique exported name.
- Declare exactly one View opening and at least one usable entry seat.
- Derive each seat's normalized `anchorXZ` from the final delivered USDZ bounds,
  after any exporter axis or root-transform conversion; do not copy DCC world
  coordinates into the normalized field.
- Keep teleport IDs stable across revisions.
- Map an optional desk seat to the tabletop entity itself, not a hierarchy
  containing legs, chairs, lamps, computers, or props.
- Name optional wall and roof entities explicitly for spatial adaptation.
- Create a current `thumbnail.jpg` that represents the delivered Room.

Inspect the authored Room from every declared seated eye point before export.
Check sightlines, scale, glass, normals, materials, clipping, and whether a
visitor can read the Room's intended focal point without standing up.

After export, inspect the delivered USDZ rather than trusting the DCC viewport
or render. Confirm up axis and scale, metadata-referenced entity names,
embedded texture paths, positive emission on every controlled fixture body,
and transparent-material parameters. Some exporters render alpha correctly in
the authoring tool but write an opaque USD PreviewSurface. `usdchecker` can
accept that file because it checks USD validity, not appearance. Correct the
source or repeatable export pipeline and rebuild the USDZ when fidelity drifts.

## Declare optional lighting

Treat each `luminaireGroups` entry as one logical visitor control. `entities`
names emissive fixture bodies; `proxy` or Room-v3 `proxies` declares bounded
direct sources. An enabled fixture body must remain visibly emissive from every
seat. `nearTeleportIDs` scopes only the direct source; it must not make the
fixture body appear switched off elsewhere.

The emissive body, direct proxy, and indirect response are separate layers:

1. The exported emissive material makes the physical fixture look on.
2. A bounded point or spot proxy creates local direct illumination.
3. Optional Room-v3 `bakedIndirect.entities` supplies broad, low-frequency
   diffuse response on opaque receivers.

Keep glass, water, transmissive materials, luminaire glow meshes, and
fixture-specific halos out of the baked-indirect subtree. Locus scales that
layer with the Room Lights master and Overall Room EV; individual light
switches and color controls do not recolor the shared bounce.

Respect the Room-v3 safety contract: no more than 12 authored proxies, 4 active
proxies at a seat, 1 shadow-casting proxy, 10,000 lumens per proxy, and a
brightness range within -4...+1 EV. These limits are not modeling or lighting
recommendations.

## Declare optional experimental animations

Treat all Room animation metadata and playback behavior as experimental. Use
Room v4 only when the creator knowingly accepts that the field names, controls,
speed behavior, and replay interval behavior may change.

Each `ambientAnimations` entry connects one stable ID and visitor-facing name
to one exact entity and animation name in the delivered USDZ. Set bounded speed
and interval ranges. `[0, 0]` means immediate replay; any other range selects a
fresh random pause after every completed play. The default interval must fit
inside the adjustable range.

The bundled scaffolder intentionally remains a stable Room v1-v3 starting
point. To experiment with Room v4, add `ambientAnimations` only after the USDZ
contains the named clips, then run the bundled validator against the exact ZIP.
Try every animation switch, speed, and interval in Locus before delivery. Do
not describe validator success as proof that the named clip produces the
intended visible motion.

## Scaffold, package, and validate

Resolve the directory that contains this `SKILL.md`; do not assume the current
working directory is the skill directory. The bundled scaffolder creates the
metadata and copies a finished USDZ and thumbnail into a new flat source
directory. Run its `--help` first, then provide explicit provenance and Room
arguments. For example:

```sh
python3 /absolute/path/to/skill/scripts/scaffold_locus_room.py --help
```

For a one-seat Room with one pendant, pass `--light-body` and `--light-anchor`
using the exact exported entity names. Add `--baked-indirect-entity` only when
that exported subtree actually exists. Review every generated JSON value; the
scaffolder cannot infer geometry, bounds, seat pose, authorship, or rights.

The finished source directory contains exactly:

```text
room/
|-- space.json
|-- provenance.json
|-- teleport-points.json
|-- scene.usdz
`-- thumbnail.jpg
```

Do not add an ID, parent folder, editable source, GLB, loose texture, cache, or
any other file. Put the user-visible name in `space.json` as `displayName`;
Locus assigns a UUID at import and allows duplicate display names.

Pack and validate by absolute path so the commands work from any directory:

```sh
python3 /absolute/path/to/skill/scripts/pack_locus_asset.py /absolute/path/to/room /absolute/path/to/room.zip
python3 /absolute/path/to/skill/scripts/validate_locus_asset.py /absolute/path/to/room.zip
```

The packer refuses to overwrite an existing ZIP. Validate the exact archive
that will be delivered. Passing validation confirms structure and
machine-checkable requirements; it does not prove entity semantics, comfort,
scale, glass transparency, fixture emission, appearance, or runtime behavior.

## Exercise the shipping path

Import the exact validated ZIP through Locus's normal public import flow, pair
it with a View, enter the Room, and try every declared seat and visitor control.
On a simulator, verify archive import, catalog presentation, Room loading,
entry, and controls that do not require world sensing. Capture a screenshot and
inspect it for a loaded Room rather than treating a successful launch command
as visual proof.

Before calling physical behavior complete, try every declared seat on Apple
Vision Pro. Exercise desk mappings, adaptive surfaces, Room Portal behavior,
tracking, scale, reach, comfort, and lighting from different viewpoints there.
Simulator evidence must not be reported as physical-device evidence.

For experimental Room v4 content, also check every animation from every seat,
including off, continuous `0–0`, fixed nonzero, and random interval behavior.
Check motion scale, comfort, and sustained performance on Apple Vision Pro.

Report the archive path and SHA-256, validator result, import and entry result,
tested seats and interfaces, screenshot or device evidence, and every check
that remains pending. Correct the authored source and rebuild instead of
patching the ZIP by hand.

## License

This skill, its references, and its bundled scripts are licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). The
repository's `LICENSE.md` and `LICENSES/Apache-2.0.txt` contain the exact scope
and terms.
