# Concept image, brief, and metric layout

Start with a concept image and written brief, then derive a metric layout
before opening a 3D tool. This prevents an attractive image from becoming an
unbuildable Room.

## Choose the concept image

One creator-selected image supplies the visual and camera target. It can come
from ChatGPT, any text-to-image model, another image model, a supplied photo
or sketch, a quick Blender blockout render, or the creator's own image. Image
generation is optional: no provider, API key, or paid service is required.

Use one clear design basis rather than contradictory image references. Record
the Room's purpose, mood, main activity, architectural type, important
materials, principal view, day/night state, and any optional animation or
sound. If an image model contributes materially, record that truthfully in
provenance; a prompt alone does not prove authorship or redistribution rights.
Keep a rights inventory for every supplied reference or incorporated asset.

A concept prompt should be specific about the camera as well as the place:
eye height, direction, focal length or field of view, foreground, Room envelope,
opening, and desired view through it. Avoid text, logos, or tiny decorative
features that a model cannot reproduce reliably.

## Derive the metric plan before modeling

The agent turns the selected image into a floor plan and seat layout. These are
build targets—not raw `anchorXZ` values or exported transforms. Record metric
dimensions for the Room envelope, walls, major furnishings, and opening; every
opening's width, height, and position; all floor levels and transitions; usable
paths and clearance; and the View opening plus any wall or roof references.

For every seat, record:

- intended eye position and facing direction;
- purpose and forward focal point;
- headroom, footroom, surrounding circulation, and line of sight; and
- whether it is desk-backed or lounge seating.

For a desk-backed seat, identify the actual tabletop, its usable work area, and
the group that **Hide Desk** must later hide. For lounge seating, define the
relaxed view and access route. Also record the comparison camera's eye height,
direction, framing, and field of view. State the seat count and purpose, which
lamps a visitor can control, and a compact acceptance list: clear paths and
focal points, no floating or intersecting objects, sufficient visible-surface
thickness, and readable usable desks.

## Use both inputs through the build

Set a comparison camera to the concept's eye height, framing, and direction.
Render the first blockout from it. Compare silhouette, major openings, ceiling
height, floor transitions, desk position, and seat-to-focal-point relationships
against the concept and metric plan before adding detail. Repeat after materials
and lights are finished. The thumbnail must show the delivered Room, not the
concept image.

The concept guides visual intent and the layout governs spatial intent. Neither
replaces individual review of the actual seats: one attractive thumbnail cannot
show a backwards chair, obstructed surround, poor route, or insufficient
overhead clearance.
