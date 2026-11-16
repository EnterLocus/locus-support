# Example Media Room: a Room with TVs

Requires Locus 1.4.9 or later.

A small Package v2 Room with two
[Room TVs](../../reference/locus-asset-format.md#room-tvs-locus-149-or-later):
a 75-inch TV on the left wall facing the sofa, and a 55-inch art TV on the
back wall facing a reading chair. The art TV's off state is a painting; the
living TV's off state is dark glass.

| File | Role |
| --- | --- |
| [`locusplace.json`](locusplace.json) | Package envelope, with `minimumAppVersion: "1.4.9"`. |
| [`space.json`](catalog/spaces/space.example-media-room/space.json) | Room manifest, including `tvs` and translated `tvTitles`. |
| [`provenance.json`](catalog/spaces/space.example-media-room/provenance.json) | Rights and credit. |
| [`build_media_room.py`](build_media_room.py) | Generates the scene, the painting and the seats, then packs and validates. |

The script generates `scene.usdz` from source: simple boxes for the room and
furniture, each TV screen as one flat 16:9 quad of its own, and a procedural
painting texture. It also writes `teleport-points.json` from the final model
bounds. No network, image model or paid service is involved, and no binary is
committed.

```sh
python3 examples/media-room/build_media_room.py /tmp/media-room
python3 tools/check_room.py --current-app-version 1.4.9 \
  --renders /tmp/media-room-renders /tmp/media-room/media-room.locusplace
```

The output directory must be absent or empty. It receives the editable source
(`media-room/`) and the checked archive (`media-room.locusplace`, about 50 KB).
To change the Room, edit the script or the checked-in JSON and build again;
never edit the archive by hand.

The screens show the contract from the
[Room TVs reference](../../.agents/skills/build-original-locus-room/references/room-tvs.md):

- `TV_Screen_Living` and `TV_Screen_Art` are separate objects, each holding one
  four-vertex quad with 0–1 UVs, u to the watcher's right.
- Each screen sits 4 mm in front of its own frame, and faces its seat.
- Neither screen material is emissive.

It is a format example, not a finished design: there are no lamps, no
thumbnail and plain materials. It has not been checked on Apple Vision Pro.

The script, metadata and generated Room are licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
