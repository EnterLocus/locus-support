# Device preview and report

Mac validation and renders establish useful evidence, but they do not duplicate
Apple Vision Pro tracking, comfort, scale, selective occlusion, or the actual
RealityKit appearance. Preview the exact archive that passed the Room checker.

## Preview on device

1. Import the Package v2 archive from Files or a direct HTTPS URL.
2. Open the Room card's **Preview in 3D** and inspect the full model, its
   materials, bounds, and thumbnail relationship.
3. Pair it with a View and enter Virtual Space.
4. Try every seat. Check the forward view, full surround, headroom, footroom,
   focal point, clipping, and the seat's facing direction.
5. For every desk-backed seat, check tabletop alignment and **Hide Desk** if
   declared. Confirm that the hidden group contains all table-top objects.
6. Try every light control and, if present, every experimental animation
   switch, speed, and replay interval.
7. Check scale, reach, readability, material appearance, comfort, and lighting
   in the actual view conditions the Room is designed for.

Use a simulator only for import, loading, and non-world-sensing controls. Do
not label simulator screenshots or offline renders as device acceptance.

## Independent review

Ask someone other than the author to inspect the archive hash, checker output,
render contact sheet, and device evidence. Their job is to find omissions,
misleading claims, backwards seats, material failures, and coverage gaps, not
to repeat the authoring decisions. Repair the editable source, repack, recheck,
and repeat the affected device checks when they find a problem.

## Write the report

Include:

- archive filename and SHA-256;
- `packageID`, space ID, `contentVersion`, and target app version;
- exact `check_room.py` result and retained render contact sheet;
- evidence for import, Preview in 3D, each seat, each lamp, and Hide Desk;
- device model and conditions for physical checks; and
- any warning, unavailable test, or `not verified` item with the next action.

Do not promote a package because it was accepted by the importer, because a
command returned zero, or because its concept image looks good. Those signals
are narrower than the device experience.
