# Reproducible `.locusplace` examples

[`build_examples.py`](build_examples.py) creates three small but structurally
real archives:

| Archive | Declared content | Selection behavior |
|---|---|---|
| `view-only.locusplace` | one Destination/View | installs reusable content; no synthetic Experience |
| `room-only.locusplace` | one Space/Room | installs reusable content; no synthetic Experience |
| `combined.locusplace` | one View, one Room, one virtual-space Experience | resolves and appears as an Experience |

The builder creates a decoded 16x8 PNG, strict provenance, an uncompressed USDZ
with a root USDA layer, Package-v2 manifests, per-file SHA-256 records, and the
canonical envelope `contentHash`. No network, provider, paid generation, or
private asset is involved.

```sh
python3 docs/examples/locusplace/build_examples.py /tmp/locusplace-examples
python3 scripts/validate_locusplace.py /tmp/locusplace-examples/view-only.locusplace
python3 scripts/validate_locusplace.py /tmp/locusplace-examples/room-only.locusplace
python3 scripts/validate_locusplace.py /tmp/locusplace-examples/combined.locusplace
```

The output directory must already be absent or empty; the builder never
overwrites an existing archive.

For author customization, unzip one of these fixtures, edit its public files,
and repack it as an ordinary ZIP. The packer regenerates `files` and
`contentHash`, then runs the same validator:

```sh
mkdir /tmp/my-editable-view
ditto -x -k /tmp/locusplace-examples/view-only.locusplace /tmp/my-editable-view
python3 scripts/pack_locusplace.py /tmp/my-editable-view /tmp/my-view.zip
```

The combined fixture proves the transport can install an atomic multi-content
bundle. Public starter convention is simpler: distribute one reusable View,
Room, or Experience per ordinary ZIP. Runtime ZIPs exclude Blender/GLB/FBX/OBJ
authoring sources and original HDR captures; retain those outside the package.

See the [public author guide](../../../create-your-own-place/) for the
transparent View, Room, Experience, provenance, and asset-format contract.
