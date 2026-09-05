# Public Locus Room examples

These are complete flat Room ZIPs for direct import into Locus and for studying
the public Room metadata contract.

| File | Display name | Format | Seats | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `atrium-loft-room.zip` | Atrium Loft | 5 | 2 | `9e448784ffe8814729b3eab5407173ed352b6dc1ca8d7451ee725c4fd6b74bf4` |
| `courtyard-gallery-room.zip` | Courtyard Gallery | 5 | 3 | `6981d3e796d7844383aead0d842f3eb6cda6b88014cd4e87f9856875c3854fa3` |
| `horizon-atelier-room.zip` | Horizon Atelier | 5 | 3 | `cda45e58f29762a2e3a9eb44a2a3a1a824c33ec9e70531ef9fa33a7ecfa1bde9` |

`demo-room.zip` is a byte-for-byte compatibility alias of
`atrium-loft-room.zip` so existing public links continue to work.

The examples were packed with the public deterministic packer and pass the
public validator, including `usdchecker --arkit`. They carry the same USDZ
and thumbnail bytes as the source-authored Room publication
`authored-room-rendering-v38-2026-09-05` (Atrium Loft 1.0.14, Courtyard Gallery
1.0.16, Horizon Atelier 1.0.18; refreshed September 5, 2026). The v5 metadata
carries explicit reflection/fade roles and spotlight directions. Horizon keeps
the softer wood-floor finish; the other Rooms retain their floor designs.

These ZIPs require a Locus build with Room v5 support. Locus 1.1.0 does not
support v5. The download pages link the previous compatible ZIPs at the frozen
[September 3 example revision](https://github.com/EnterLocus/locus-support/tree/4017745d9f3b6001f00d325ad2610da0a4e171cb/examples).
Public provenance retains the existing CC BY 4.0 and embedded-texture CC0
terms; scene, thumbnail, seat and rendering metadata bytes match the accepted
source export. This publication changes no rendering code and includes no
Room + View reflection capture experiment.

The Locus-authored geometry, arrangement, lighting artwork, and thumbnail in
each demo are licensed under CC BY 4.0. Credit the relevant work as
`<Room name> by EnterLocus.com`, link the license, and say if you changed it.
Embedded Poly Haven texture maps retain CC0 1.0. Exact authors, sources, and
scope are listed at <https://enterlocus.com/asset-rights/#demo-room-notices>.

## Experimental animation demo

| File | Display name | Format | Seats | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `coffee-atrium-experimental-room.zip` | Coffee Atrium POC | 4 | 2 | `c83b3be2f5d29737e418f898fb442b8ded61488b4f32b613195dc0ecab27d42d` |

This Room demonstrates experimental USDZ animation playback: a seated coffee
gesture with an 8–20 second random replay interval and a continuously turning
ceiling fan. All animation metadata, playback controls, speed, and interval
behavior in this demo are experimental and may change.

The ZIP carries a reserved-rights statement for its Locus-authored parts. It
may be used with the official Locus app for this demonstration but is not
licensed for redistribution or reuse elsewhere. Embedded Poly Haven textures
remain CC0 1.0. See the
[complete rights and component notices](https://enterlocus.com/asset-rights/#experimental-animation-demo-notices).
