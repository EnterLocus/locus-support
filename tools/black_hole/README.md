# Black-hole View tools

Command-line tools for the tutorial
[How to make your own black hole View](https://enterlocus.com/make-a-black-hole-view/).
They compose a starry sky, compute how a non-spinning black hole bends it, bake the
accretion disc, and pack the result as a complete Package v2 View that Locus 1.3.4 or
later can import and animate. Nothing here ships inside the app.

| Tool | What it does |
| --- | --- |
| `compose_sky.py` | Procedural starfield plus your nebula photos, as the unlensed 2:1 sky |
| `bake_view.py` | Lens table, disc map, turbulence, glow, panorama, cover and `destination.json`; previews stills and frames |
| `pack_view.py` | Writes `locusplace.json` (`files`, `contentHash`) and the archive, then validates it |
| `validate_view.py` | Checks a packed black-hole View the way Locus does at import |
| `outpaint_fal.py` | Optional, paid: extends a nebula photo with a dark margin using Bria Expand on fal.ai |
| `black_hole_lens.py` | Schwarzschild ray tracing (NumPy only), used by the baker |
| `black_hole_profile.py` | Field names, ranges and image formats of the `blackHole` profile |
| `view-black-hole-v1.schema.json` | JSON Schema of the `blackHole` profile |
| `recipes/ring.view.json` | Example recipe: the ring composition of Locus's Event Horizon: Ring |

## Requirements

- Python 3.9 or later with NumPy and Pillow: `python3 -m pip install numpy pillow`.
  Xcode's `/usr/bin/python3` works once both are installed.
- About 5 GB of free memory and roughly a minute per bake at the default resolution
  (measured on a 12-core M-series Mac; slower machines take a few minutes).
- Optional: `ffmpeg` to turn preview frames into `reference.mp4`.
- Locus 1.3.4 or later on Apple Vision Pro to import the result.

## A short end-to-end example

```bash
cd tools/black_hole

# 1. Download nebula photos yourself, e.g. from https://esawebb.org/images/
#    (CC BY 4.0, credit "NASA, ESA, CSA, and STScI"). Compose the sky:
python3 compose_sky.py ~/bh/sky.png \
  --photo ~/bh/weic2212a.jpg,0,12,110,0.55,0.1,fade \
  --photo ~/bh/weic2207b.jpg,180,-12,50,0.5,0.2,add

# 2. Copy the recipe, put your name in its provenance, then bake (about a minute):
cp recipes/ring.view.json ~/bh/my-ring.view.json
python3 bake_view.py ~/bh/my-ring.view.json --sky ~/bh/sky.png --out ~/bh/my-ring --stills 0,5,10

# 3. Pack and validate:
python3 pack_view.py ~/bh/my-ring ~/bh/my-ring.locusplace
```

Then move `my-ring.locusplace` to Files or iCloud Drive and import it in Locus with
Places › Import › Import a View › Files.

## Recipe fields

A recipe has the Package v2 identity (`destinationID`, `contentVersion`, `title`,
`caption`), the `blackHole` values that Locus reads at runtime, `bake` settings that only
the baker reads, and the `provenance.json` to ship. `bake_view.py` fills in the image
paths, `version`, `discMapMaxAngleDegrees` and, when `disc.exposure` is absent, an
automatic exposure.

Lengths are in units of the hole's mass (the horizon is at 2, the photon sphere at 3, the
innermost stable orbit at 6).

| Field | Meaning |
| --- | --- |
| `blackHole.yawDegrees`, `elevationDegrees` | Where the hole sits around you (yaw 0 is straight ahead; elevation −60…60) |
| `blackHole.observerRadius` | Your distance from the hole, 8–200. Closer makes the shadow and ring larger |
| `blackHole.disc.inner`, `outer` | Disc radii (`inner` normally 6; `outer` at least `inner` + 1, up to 200) |
| `blackHole.disc.spin` | 1 or −1: which way the gas orbits |
| `blackHole.disc.iscoPeriodSeconds` | Seconds for one orbit at the inner edge (time is compressed; outer gas is slower) |
| `blackHole.disc.regenerationSeconds` | How often each of the two turbulence layers is renewed, so it never winds into stripes |
| `blackHole.disc.profileExponent` | Radial fall-off of brightness (3 is the thin-disc value; lower is softer) |
| `blackHole.disc.peakTemperatureKelvin` | Colour of the hottest gas |
| `blackHole.disc.textureLogSpan`, `contrast` | Size and strength of the turbulence |
| `blackHole.doppler` | 0–1. 0 removes Doppler beaming and colour shift, as in many films; 1 is physical (one side brighter and bluer) |
| `blackHole.glow` | 0–2. Soft bloom around the disc; an art layer, not physics |
| `blackHole.drift.degreesPerSecond`, `axis` | Slow turning of the distant sky (0–2 °/s) about `up`, `right` or `view` |
| `blackHole.flares` | Optional short-lived hot spots on circular orbits |
| `bake.inclinationDegrees`, `rollDegrees` | Disc tilt: 90 is edge-on, 0 face-on; roll turns it about your line of sight |
| `bake.thumbnailHfovDegrees` | Horizontal field of view of the Library cover, centred on the hole |
| `bake.lensWidth`, `discMapWidth`, `supersample`, `glowWidth`, `texture` | Bake resolution and turbulence pattern |

The full contract, with the formulas Locus evaluates, is in
`black_hole_profile.py`, the schema, and `bake_view.py`'s `Reference` class, which
renders exactly what a conforming reader shows.

## What is computed and what is art

The lens table, the disc map and the panorama are exact Schwarzschild ray tracing at bake
time: the shadow, the photon ring, the lensed image of the far side of the disc and the
bent starfield. The disc's emission profile, turbulence, temperatures, exposure, flares,
glow, the time compression and the sky are artistic choices. Not modelled: spin (Kerr),
disc thickness and transparency, light-travel delay between images, and jets.

## AI outpainting and provenance

`outpaint_fal.py` is optional and uses your own fal.ai key from the `FAL_KEY` environment
variable. It costs money per run and sends a downscaled copy of the photo to fal.ai. If
any generated pixels end up in your View, set `"aiGenerated": true` and `"aiProvider"` in
the recipe's provenance and say what was generated in `modificationNotes`. Never commit
API keys.

## Tests

```bash
python3 -m unittest discover -s tools/black_hole/tests
```

From the repository root, `python3 -m unittest discover -s tests` runs them too (they are
skipped when NumPy or Pillow is missing). They check the lens against independent
reference values (shadow size, deflection angles, the capture threshold), the lens table
against direct integration, which side of the disc is blueshifted, the 16-bit PNG
round trip, that the first animated frame equals the panorama, and that the packer writes
`files` and `contentHash` exactly like the Locus reference packer.

## License

Apache License 2.0, as for everything under `tools/`; see `LICENSE.md` at the
repository root. The nebula photos you download keep their own licences.
