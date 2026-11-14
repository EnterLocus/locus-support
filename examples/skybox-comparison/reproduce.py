#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reassemble this Maldives comparison from its saved API outputs, with no API calls."""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TOOLS=ROOT/"tools/skybox"
FACES=("px","nx","py","ny","pz","nz")


def run(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],check=True)


def unpack(archive,destination):
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target=(destination/entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("archive contains an unsafe path")
        z.extractall(destination)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gpt-archive",type=Path,required=True)
    p.add_argument("--nano-archive",type=Path,required=True)
    p.add_argument("--outdir",type=Path,required=True)
    args=p.parse_args()
    if args.outdir.exists():
        p.error("choose a new output directory")
    args.outdir.mkdir(parents=True)
    g=args.outdir/"gpt";n=args.outdir/"nano"
    unpack(args.gpt_archive,g);unpack(args.nano_archive,n)
    run(HERE/"recipes/correct_sky_tone.py","--source-faces",g/"F/input",
        "--enhanced-faces",g/"F/raw","--output-dir",g/"F/tone",
        "--audit-dir",g/"review/tone","--spatial")
    run(TOOLS/"skybox.py","merge",g/"F/tone",g/"tone.png","--native-resolution","--blend",.25)
    run(HERE/"recipes/retain_g_sky.py","--skybox-tool",TOOLS/"skybox.py",
        "--reference",g/"G/raw-3840x1920.png","--candidate",g/"tone.png",
        "--output",g/"sky.png","--audit-dir",g/"review/sky","--wrap-guard")
    current=g/"sky.png"
    for number,yaw in [(1,135),(2,-135)]:
        run(TOOLS/"seam_patch.py","extract",current,g/f"R/{number}-input.png",
            g/f"R/{number}-camera.json","--yaw",yaw,"--size",1536,"--fov",60)
        target=g/f"R/{number}-merged.png"
        run(TOOLS/"seam_patch.py","insert",current,g/f"R/R{number}-raw.png",
            g/f"R/{number}-camera.json",target,g/f"R/{number}-mask.png")
        current=target
    shutil.copyfile(current,args.outdir/"gpt-native.png")

    enhanced=n/"F/enhanced";enhanced.mkdir()
    for face in FACES:
        with Image.open(n/f"F/raw/{face}.jpg") as raw:
            raw.convert("RGB").save(enhanced/f"{face}.png")
    shutil.copyfile(n/"F/metadata.json",enhanced/"metadata.json")
    run(HERE/"recipes/localize_sand_repair.py","--source",n/"F/raw/ny.jpg",
        "--repair",n/"R/R2-raw.jpg","--config",HERE/"recipes/sand-localize.json",
        "--output-dir",n/"R/localized")
    shutil.copyfile(n/"R/localized/ny-localized-r2.png",enhanced/"ny.png")
    # This trial used an existing quality100/4:4:4 JPEG checkpoint before wrap
    # correction; reproduce that explicit encoding rather than imply it was PNG.
    run(TOOLS/"skybox.py","merge",enhanced,n/"pre-wrap.jpg","--native-resolution","--blend",.25)
    run(TOOLS/"sky_wrap_tone.py",n/"pre-wrap.jpg",args.outdir/"nano-native.png",
        n/"R/wrap-mask.png")
    sizes={}
    for model in ["gpt","nano"]:
        with Image.open(args.outdir/f"{model}-native.png") as image:
            image.save(args.outdir/f"{model}-delivery.jpg",quality=95,subsampling=0,optimize=True)
            sizes[model]=list(image.size)
    (args.outdir/"reproduction.json").write_text(json.dumps({
        "apiCalls":0,"sizes":sizes,
        "limitation":"Reuses saved stochastic model outputs; local masks/coordinates apply to this image only. Review residual defects and dependency-version effects."},indent=2)+"\n")


if __name__=="__main__":
    main()
