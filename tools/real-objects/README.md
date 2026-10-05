# Real Objects tools

Mac command-line tools for the [Real Objects tutorial](https://enterlocus.com/experimental-real-objects/):
turn a scan of something you own into an ARKit `.referenceobject` that Locus can import. They sit
between the iPhone capture and Locus Settings › Workspace › Experimental › Real Objects. Nothing
here ships inside the app.

| Tool | Language | What it does |
| --- | --- | --- |
| `inspect_usdz` | Swift (ModelIO + `usdcat`) | Metric size, mesh/texture stats, rigid check, tracking-readiness warnings |
| `rescale_usdz` | Python 3.9 | Uniform rescale to a measured size, then re-inspect |
| `reconstruct` | Swift (RealityKit `PhotogrammetrySession`) | Rebuild a USDZ on the Mac from the kept Object Capture images |
| `train` | Python 3.9 | `xcrun createml objecttracker` with checks, logs, checkpoint and a run manifest |

Each name is a launcher in this folder — run it directly, e.g. `./inspect_usdz model.usdz`.

## Requirements

- A Mac with Apple silicon and Xcode 27's command-line tools installed.
- The Python tools (`rescale_usdz`, `train`) run on Xcode's own `/usr/bin/python3` (3.9) and need
  nothing installed. There are no Python USD bindings on this Mac, so USD facts come from Xcode's
  `/usr/bin/usdcat`.
- The Swift tools (`inspect_usdz`, `reconstruct`) compile on first use with `xcrun swiftc -O` into
  `.build/` (git-ignored; no binaries are committed). To build ahead of time:

  ```bash
  cd tools/real-objects
  ./build.sh                 # inspect_usdz + reconstruct -> .build/   (ROS_BIN_DIR overrides)
  ```

## A short end-to-end example

1. Scan the object with an iPhone (see the tutorial) and move the exported USDZ to the Mac.
2. Check its real size against a measured dimension:

   ```bash
   ./inspect_usdz --expect height=95 model.usdz
   ```

   `--expect AXIS=MM` (axis `x|y|z|height`) prints the deviation and the scale factor that would
   fix it.
3. If it's off by more than about 1%, rescale it uniformly:

   ```bash
   ./rescale_usdz model.usdz --height-mm 95 -o model-fixed.usdz
   ```

4. Train a reference object:

   ```bash
   ./train --source model-fixed.usdz --output model.referenceobject \
            --mode standard --angles upright --caffeinate
   ```

   Drop to a dry run first with `--dry-run` to see the exact command without starting it.

5. Optional: if the on-phone model is too coarse, rebuild it on the Mac from the kept Object
   Capture images at full detail:

   ```bash
   ./reconstruct --input images/ --output model-full.usdz --detail full
   ```

   Then continue at step 2 with the new USDZ.

## What `train` writes

Next to the `.referenceobject` output:

- `<output>.progress.csv` — the training progress stream, appended to across resumes.
- `<output>.summary.txt` — the training summary.
- `<output>.run.json` — a run manifest: Xcode/macOS versions, machine, start/end time of every
  attempt, SHA-256 of the source and every `--avoid` model, the inspect result, the exact command,
  exit status and the output's SHA-256.
- `<output>.checkpoint/` — the checkpoint directory. If a run is interrupted (Ctrl-C, reboot), run
  the same command again to resume from it.

`train` also refuses to start on an implausible model (unless `--force`) and refuses to replace an
existing output (unless `--overwrite`).

## Timing

Standard training took about 5.5 hours on an M4 Pro Mac mini. Create ML's extended mode tracks
best but takes several times longer, and needs at least 43 GB free on the Mac's **startup disk** —
Create ML checks the system temporary volume for this, and setting `TMPDIR` does not move it.

A reference object trained with Xcode 27 needs visionOS 27 or later; Locus itself keeps supporting
earlier visionOS releases for everything else.

## Tests

No network, training or photogrammetry run. Fixtures are tiny USDZ files generated in Python;
`train` is tested against a fake `createml` executable; `reconstruct` only up to input validation
and `--dry-run`.

```bash
cd tools/real-objects
/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py'
```

The first run compiles the two Swift tools (a few seconds).

## Notes and limits

- ModelIO reports bounds with prim transforms applied but ignores `metersPerUnit`; `inspect_usdz`
  multiplies it back in, using the layer's authored value (USD's 0.01 fallback is flagged).
- Texture variance is computed on a downscaled copy and only for textures that feed diffuse / base
  colour (normal, roughness and similar data maps are listed with role `data` and not judged).
- `train` was exercised against a fake `createml`; the `--csv-fd` / `--summary-fd` redirections
  follow the example in `xcrun createml objecttracker --help`, but the CSV and summary contents of
  a real run can vary by Xcode version.
