# Native sampling and output resolution

Six square cube faces cover a full sphere. Smaller faces reduce sample density,
not coverage. More views or smaller patches are needed only to add density or
repair defects; they are not needed simply to see all directions.

Record actual returned face sizes before choosing the final panorama size.
Never infer them from a model name, a “4K” setting or an enlarged stored PNG.

## Derivation

For one N×N perspective face with half field of view A = 45° + overlap:

- T = tan(A).
- Face-center focal length f = N/(2T), in pixels per radian.
- Equivalent 90° core C = N/T = 2f.
- Common cube-grid panorama width is 4C. This convention oversamples the
  face-center angular density by 4/pi ≈ 1.273; it is not uniform native detail.
- A conservative ERP width matching the lowest, face-center angular density
  is W = 2*pi*f = pi*N/T. Round W down to an even integer and set H = W/2.

At 6° per-side overlap (102° total FOV):

| Native stored square | Equivalent 90° core | Common 4C width | Conservative W×H |
| --- | ---: | ---: | ---: |
| GPT candidate 2880² | 2332.18 | 9328.71 | 7326×3663 |
| Nano Banana Pro 4096² | 3316.88 | 13267.50 | 10420×5210 |

These are sampling conventions, **not measured resolved detail**. Rectilinear
pixels have nonuniform angular spacing; ERP also stretches pixels near poles.
No projection produces one globally uniform “true K” number. The conservative
rule avoids an arbitrary 12288-wide output and excessive interpolation at
face centers; it cannot recover blur, prove an AI model's native detail or
certify spherical continuity.

Actual split metadata rounds the stored face size. The merge uses that exact
ratio, so its dimensions can differ by a few pixels from this idealized table.
For mixed native face sizes, use the smallest by default. Do not treat a
copied, low-resolution detailed face as a high-density face merely because
its PNG was enlarged. Such a set fails detail acceptance. A genuinely
featureless face may retain smooth source pixels with that exception recorded.

## Public commands

```sh
python3 tools/skybox/skybox.py resolution --face-size 2880 --overlap 6
python3 tools/skybox/skybox.py merge enhanced panorama.jpg --native-resolution --blend 0.25
```

Native merge samples each original face directly; it does not enlarge the face
files first and does not accept a forced width or normalization flag. Its
receipt records actual input sizes, FOV, sampling calculation and output size.
Final filenames and demo captions use those decoded dimensions, not “12K”.
Use lossless intermediates and compare common angular crops plus original
native pixels; a smaller export is not automatically worse-looking.

For a higher target, estimate the additional overlapping views/patches and
cost, then obtain approval before generating them. The experimental small-
patch route has not established equivalent seam/fidelity quality; do not
silently buy many more images or claim upscaling adds detail.
