# Physical-device preview and iteration report

Mac validation and renders establish useful evidence, but they do not duplicate
Apple Vision Pro tracking, comfort, scale, selective occlusion, or actual
RealityKit appearance. Preview the exact archive that passed the public Room
checker on a physical Apple Vision Pro. This public workflow does not use a
Simulator.

## Preview on device

1. Import the Package v2 archive from Files or a direct HTTPS URL.
2. Open the Room card's **Preview in 3D** and inspect the full model, its
   materials, bounds, and thumbnail relationship.
3. Pair it with a View and enter Virtual Space.
4. Try every seat. Check the forward view, full surround, headroom, footroom,
   focal point, clipping, seat facing direction, and usable path.
5. For every desk-backed seat, check tabletop alignment and **Hide Desk** if
   declared. Confirm that the hidden group contains all table-top objects.
6. Try every light control and, if present, every experimental animation
   switch, speed, and replay interval.
7. Check actual appearance, scale, reach, readability, material appearance,
   comfort, and lighting in the conditions the Room is designed for.

Capture screenshots that make concrete findings reviewable. Send the archive
hash, screenshots, and specific observations to the agent—for example the
affected seat, direction, material, lamp, or missing hidden object. The agent
uses that feedback to repair the editable source rather than patching the ZIP,
then rebuilds and reruns the affected render and archive checks. A creator may
also ask another reviewer to look for coverage gaps, but that is not a required
approval step.

## Reimport a revision

Starting with Locus 1.4.5, importing a changed Package v2 payload with the same
imported `packageID` asks before replacing it, including equal or lower content
versions. Keep the package, space, and teleport IDs stable. Increment
`contentVersion` whenever archive bytes change. Replacement preserves saved
settings and organization and uses no additional import allowance; an identical
content hash remains a no-op.

Import the exact revised archive that passed `check_room.py`; do not treat a
prior checker result, render, or screenshot as evidence for changed bytes.
Repeat the physical checks affected by the revision and record which exact
archive each screenshot covers.

## Write the iteration report

Include:

- archive filename and SHA-256;
- `packageID`, space ID, `contentVersion`, and target app version;
- exact `check_room.py` result and retained render contact sheet;
- evidence for import, Preview in 3D, each seat, each lamp, and Hide Desk;
- device model and conditions for physical checks; and
- every warning, unavailable test, or `not verified` item with the next action.

Do not promote a package because it was accepted by the importer, because a
command returned zero, or because its concept image looks good. Those signals
are narrower than the device experience.
