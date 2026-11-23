# Larger Rooms

Plan a multi-level Room before detailed modeling. Draw circulation, entries,
the View opening, seats, desks, controlled fixtures, and maintenance access at
the same scale. Divide the model into bounded authored areas, but do not add
invisible terrain or oversized base slabs merely to organize it: they distort
the delivered bounds and can hide View water.

For each seat, retain a short review card: intended activity, forward focal
point, eye position, facing, desk/HIDE Desk association, nearest lamps, and
the render files that cover it. A long seat list without individual renders is
not reviewable evidence.

Respect the published Room resource budgets and lighting limits. Reuse
materials, texture resolution, and geometry intentionally; do not assume a
large source file is safe simply because it imports. At villa or multi-level
scale:

- **Use `mode: "irradiance"` (`Locus 1.6.0+`, protocol `1.5.2+`) for baked
  lighting.** Across 100+ receivers, a house-wide atlas sits around 35–55
  lightmap texels/m; `mode: "irradiance"` keeps full `UV0` stone, wood, and
  fabric sharpness while keeping layer sizes modest (`2048×1024` or
  `4096×2048`).
- **Budget resident Float16 light-layer memory.** Each baked layer allocates
  `width × height × 8` bytes at runtime (for example ~16 MiB at `2048×1024` or
  ~64 MiB at `4096×2048`). Group lamps semantically (5–6 layers maximum) and
  leave tiny low-bounce accents (such as underwater pool glows) emissive-only
  rather than adding an extra full-house layer.
- **Pack `LocusIndirectUV` per object with skyline packing and deduplicate
  indirect materials.** Unwrap each receiver individually, preserve source UV
  charts on sculpted/generated furniture with higher weight, pack rectangular
  blocks with a 16 px gutter, and share one `__LocusIndirect__shared` material
  per base material (`../scripts/bake_irradiance.py` handles this automatically).
- **Consolidate static meshes and avoid extra glass layers** on upper terraces
  or backdrops where they add overdraw without architectural benefit.

Check the final USDZ and the exact Package v2 archive, then use the contact
sheet to make sure no floor, balcony, or seating area was skipped.
