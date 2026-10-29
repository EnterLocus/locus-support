# Reproducible `.locusplace` examples

[`build_examples.py`](build_examples.py) creates three small, self-contained
Package v2 archives for public authoring and validation. They include decoded
16×8 PNGs, strict provenance, a stored USDZ with a root USDA layer, per-file
SHA-256 records, and the canonical package `contentHash`. No network,
provider, paid generation, or private asset is involved.

| Archive | Declared content |
| --- | --- |
| `view-only.locusplace` | one Destination/View |
| `room-only.locusplace` | one Space/Room |
| `combined.locusplace` | one View, one Room, and one virtual-space Experience |

```sh
python3 examples/locusplace/build_examples.py /tmp/locusplace-examples
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /tmp/locusplace-examples/view-only.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /tmp/locusplace-examples/room-only.locusplace
python3 tools/validate_locusplace.py --current-app-version 1.4.4 /tmp/locusplace-examples/combined.locusplace
```

The output directory must be absent or empty; the builder never overwrites an
archive. To edit a fixture, extract it, then use the packer to regenerate the
`files` list and `contentHash` before validation:

```sh
mkdir /tmp/editable-view
unzip -q /tmp/locusplace-examples/view-only.locusplace -d /tmp/editable-view
python3 tools/pack_locusplace.py --current-app-version 1.4.4 /tmp/editable-view /tmp/my-view.locusplace
```
