# Public Locus Room examples

These are complete flat Room ZIPs for direct import into Locus and for studying
the public Room metadata contract.

| File | Display name | Format | Seats | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `atrium-loft-room.zip` | Atrium Loft | 3 | 2 | `588c14c5b1226ec677fada112df1346bb105f0cbdb0344db9d1e1be03b3b9ff1` |
| `courtyard-gallery-room.zip` | Courtyard Gallery | 3 | 3 | `1d4be79f0c69c6d34e285729c02bd1870bf11133497277a1f1d94d7b0dd9f21f` |
| `horizon-atelier-room.zip` | Horizon Atelier | 3 | 3 | `dd3551316cae67c01a114a6130db37823f03dcebcec703f15a8fedf7dc291fe7` |

`demo-room.zip` is a byte-for-byte compatibility alias of
`atrium-loft-room.zip` so existing public links continue to work.

The examples were packed with the public deterministic packer and pass the
public validator, including `usdchecker --arkit`. They carry the same USDZ
and thumbnail bytes as the Locus 1.1 runtime publication of each Room
(Atrium Loft 1.0.10, Courtyard Gallery 1.0.12, Horizon Atelier 1.0.14,
refreshed September 3, 2026); the public metadata is unchanged.

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
