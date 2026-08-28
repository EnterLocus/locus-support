# Reproducible `.locusplace` examples

[`build_examples.py`](build_examples.py) creates three small but structurally
real archives:

| Archive | Declared content | Selection behavior |
|---|---|---|
| `view-only.locusplace` | one Destination/View | validator fixture only; the current product UI imports Views as direct images |
| `room-only.locusplace` | one Space/Room | supported by **Import a Room** |
| `combined.locusplace` | one View, one Room, one virtual-space Experience | supported by **Import a Room** as an atomic Room bundle |

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

For Room authoring, unzip `room-only.locusplace` or `combined.locusplace`, edit
its public files, and repack it as an ordinary ZIP. The packer regenerates
`files` and `contentHash`, then runs the same validator:

```sh
mkdir /tmp/my-editable-room
ditto -x -k /tmp/locusplace-examples/room-only.locusplace /tmp/my-editable-room
python3 scripts/pack_locusplace.py /tmp/my-editable-room /tmp/my-room.zip
```

The combined fixture proves **Import a Room** can install the Room together with
its paired View and Experience.
Runtime ZIPs exclude Blender/GLB/FBX/OBJ authoring sources and original HDR
captures; retain those outside the package.

See the [public author guide](../../../create-your-own-place/) for the
supported View input, Room bundle, provenance, and asset-format contract.
