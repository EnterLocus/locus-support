# Local corrections used in the Maldives trial

These NumPy/Pillow recipes make no API calls. Their masks and coordinates were
reviewed for this one image. Inspect and select new masks for another scene;
blue pixels alone do not universally identify sky or water.

The [intermediate archives](../README.md#downloads-and-reproduction) contain
the exact model outputs and inputs. The [reproducer](../reproduce.py) runs the
accepted local operations and encodes delivery JPEGs. Model generation is
stochastic; reassembling saved outputs is distinct from buying the same draws.

For GPT, first fit a bounded quadratic RGB residual from each native F face to
its coherent G projection in clean blue sky:

```sh
python3 examples/skybox-comparison/recipes/correct_sky_tone.py \
  --source-faces gpt/F/input --enhanced-faces gpt/F/raw \
  --output-dir gpt/F/tone --audit-dir gpt/review/tone --spatial
python3 tools/skybox/skybox.py merge gpt/F/tone gpt/tone.png --native-resolution --blend 0.25
python3 examples/skybox-comparison/recipes/retain_g_sky.py \
  --skybox-tool tools/skybox/skybox.py --reference gpt/G/raw-3840x1920.png \
  --candidate gpt/tone.png --output gpt/sky.png --audit-dir gpt/review/sky --wrap-guard
```

The sky mask is eroded eight native pixels before a narrow sky-side feather,
protecting palm tips. Retention is disabled within 2° of the original wrap
and fades in through 8°, because G itself retains a wrap defect. Approximately
one third of the canvas retains/interpolates G sky samples from 3840×1920;
those pixels are not newly generated 7.3K sky detail. Two paid, seam-centered
2880-square perspective edits at yaw ±135° then remove residual sky/water
exposure bands. The public patch helper binds the camera/source hash and
keeps all zero-alpha pixels unchanged in PNG.

For Nano Banana, the first paid nadir repair did not remove radial sand
distortion. A deterministic local heal screened two native donor regions,
rearranged their fine residual grain using a fixed seed, and fitted broad
sand shading while protecting reviewed stones and shadows:

```sh
python3 examples/skybox-comparison/recipes/heal_ny_sand.py \
  --source nano/R/R1-localized.png --donor nano/F/raw/ny.jpg \
  --output-dir nano/R/free-heal-review \
  --config examples/skybox-comparison/recipes/sand-heal.json --seed 20261113
```

This removed the radial star but left smoother microrelief. The second paid
repair restored grain using that geometry-healed input. Its raw output was
localized into the original F face with the reviewed
[sand mask](sand-localize.json), retaining the original overlap and major
landmarks:

```sh
python3 examples/skybox-comparison/recipes/localize_sand_repair.py \
  --source nano/F/raw/ny.jpg --repair nano/R/R2-raw.jpg \
  --config examples/skybox-comparison/recipes/sand-localize.json \
  --output-dir nano/R/localized
```

The 4096-square requirement is specific to this demo's coordinates. Automatic
shadow protection is limited to the actual palm-shadow regions; a blanket
cool-pixel mask had preserved fragments of the original radial artifact.
The separate free sky-wrap helper cancels a small row-local RGB step and
touches up residual lines only in smooth sky neighborhoods. It does not
remove the remaining broad sky tone difference or artificial zenith cirrus.

Keep all raw inputs, rejected repairs and masks. Pixel preservation,
deterministic reproduction and a native canvas do not certify natural
appearance or headset quality.
