# Capturing product screenshots

The home page uses four 16:9 web exports from the approved Locus 1.0 launch
media. Each image answers a different first-time visitor question:

1. `virtual-space-desk-wide.jpg` — what working inside a Room feels like;
2. `place-picker.jpg` — how a visitor combines a Room and a View;
3. `virtual-space-room-turn.jpg` — that Virtual Space continues beyond the
   desk; and
4. `imports-virtual-space.jpg` — where a visitor brings in a View or Room.

The 3840 x 2160 PNG masters remain in the private release media root. This
public repository contains only 1920 x 1080 JPEG exports. Their master hashes
and simulator-evidence boundary are recorded in `assets/README.md`.

## Prepare the simulator scene

The reusable scene-preparation workflow lives in the private Locus source at
`scripts/app-store-capture/`. It builds and installs only the development app,
starts a clean Virtual Space with no visited website content, and uses a fixed
simulator head pose. Keep that workflow as the authority rather than copying
launch commands into this public repository.

Camera framing remains a calibrated manual step: the workflow prepares the
scene, while the operator pulls back to show the full desk or turns to show the
rest of the Room. Save accepted frames with `simctl io` at the simulator's
native 3840 x 2160 resolution.

## Publish web exports

Downsample an approved master without cropping and use a new public filename
when the image changes so the live site cannot reuse a stale cached image:

```sh
sips --resampleWidth 1920 \
  --setProperty format jpeg \
  --setProperty formatOptions 88 \
  approved-master.png \
  --out assets/screenshots/new-public-name.jpg
```

Update the home page, `assets/README.md`, and the exact asset hashes in
`tests/test_site.py` together. Run the site tests and inspect both desktop and
mobile layouts before publishing.

Simulator captures explain composition and UI. They do not prove physical
Apple Vision Pro tracking, passthrough, occlusion, presence, performance, or
comfort.
