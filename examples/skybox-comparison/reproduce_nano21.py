#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reassemble the saved Nano Banana 2.1 trial without any API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from PIL import Image, ImageCms

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1] / 'tools' / 'skybox'
FACES = ('px', 'nx', 'py', 'ny', 'pz', 'nz')
SOURCE_SHA256 = '839693327e5ce645ec0c5be03be22e4123db47543168a823b26946eab8f27c9d'


def run(script, *args):
    subprocess.run([sys.executable, str(script), *map(str, args)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--outdir', type=Path, required=True)
    args = parser.parse_args()
    if args.outdir.exists():
        parser.error('choose a new output directory')
    source = args.outdir / 'saved'
    source.mkdir(parents=True)
    with zipfile.ZipFile(args.archive) as archive:
        for entry in archive.infolist():
            if not (source / entry.filename).resolve().is_relative_to(source.resolve()):
                parser.error('archive contains an unsafe path')
        archive.extractall(source)
    if hashlib.sha256((source / 'input/source.png').read_bytes()).hexdigest() != SOURCE_SHA256:
        parser.error('the frozen source differs from this trial')
    faces = args.outdir / 'faces'
    faces.mkdir()
    shutil.copyfile(source / 'F/metadata.json', faces / 'metadata.json')
    for face in FACES:
        selected = source / 'selected/ny.png' if face == 'ny' else source / ('F/raw/' + face + '.jpg')
        with Image.open(selected) as image:
            if image.size != (4096, 4096):
                parser.error('saved face must retain its native 4096-square grid')
            image.convert('RGB').save(faces / (face + '.png'))
    # The selected nadir includes the reviewed R2 localization and tiny ghost cleanup.
    # Its complete raw repair lineage is retained separately in the archive.
    merged = args.outdir / 'merged.png'
    final = args.outdir / 'nano21-native.png'
    run(TOOLS / 'skybox.py', 'merge', faces, merged, '--native-resolution', '--blend', .25)
    run(TOOLS / 'sky_wrap_tone.py', merged, final, args.outdir / 'sky-mask.png')
    with Image.open(final) as image:
        image = image.convert('RGB')
        if image.size != (10418, 5209):
            raise ValueError('native panorama size differs from the measured trial')
        pixel_hash = hashlib.sha256(image.tobytes()).hexdigest()
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        image.save(args.outdir / 'nano21-delivery.jpg', quality=95, subsampling=0,
                   optimize=True, icc_profile=profile)
    (args.outdir / 'reproduction.json').write_text(json.dumps({
        'apiCalls': 0, 'model': 'gemini-nano-banana-2.1', 'size': [10418, 5209],
        'sourceSHA256': SOURCE_SHA256, 'decodedRGBSHA256': pixel_hash,
        'nativePNGSHA256': hashlib.sha256(final.read_bytes()).hexdigest(),
        'scope': 'Reassembly of saved stochastic model outputs and reviewed selected nadir; no new generation.',
        'limitation': 'Encoder bytes can vary with dependency versions. Local masks are specific to this trial; headset acceptance remains separate.'
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
