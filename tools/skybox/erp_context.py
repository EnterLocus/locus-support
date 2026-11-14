#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cyclic 21:9 context for a 2:1 ERP edit; preserve raw model output separately."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pad(source, output, metadata):
    with Image.open(source) as image:
        pixels = np.asarray(image.convert('RGB'))
    h, w = pixels.shape[:2]
    if w != 2*h:
        raise ValueError('source must be a full 2:1 ERP')
    target = round(h*21/9)
    left = (target-w)//2
    right = target-w-left
    rolled = np.roll(pixels, w//2, axis=1)
    # Original wrap moves to the center of the model frame; outer context is
    # a cyclic extension, not invented scenery or black bars.
    prefix = rolled[:, -left:] if left else rolled[:, :0]
    padded = np.concatenate((prefix, rolled, rolled[:, :right]), axis=1)
    Image.fromarray(padded).save(output)
    data = {'format':'skybox-erp-context-v1', 'sourceSHA256':digest(source),
            'sourceSize':[w,h], 'paddedSize':[target,h], 'left':left,'right':right,
            'rollFraction':0.5, 'paddedSHA256':digest(output), 'aspectRatio':'21:9'}
    metadata.write_text(json.dumps(data,indent=2)+'\n')


def unpad(source, output, metadata, max_correction=0.02):
    data=json.loads(metadata.read_text())
    if data.get('format')!='skybox-erp-context-v1':
        raise ValueError('unsupported context metadata')
    with Image.open(source) as raw:
        raw=raw.convert('RGB'); w,h=raw.size
        target=data['paddedSize'][0]; original=data['sourceSize'][0]
        x0=round(w*data['left']/target)
        x1=round(w*(data['left']+original)/target)
        core=raw.crop((x0,0,x1,h))
        correction=core.width/(2*h)-1
        if abs(correction)>max_correction:
            raise ValueError('model aspect drift exceeds allowed projection correction: %.5f'%correction)
        # Only downsample to square angular ERP pixels; never enlarge a model
        # result to force a marketed size. Small aspect correction is explicit.
        oh=min(h,core.width//2);ow=2*oh
        core=core.resize((ow,oh),Image.Resampling.LANCZOS)
        pixels=np.roll(np.asarray(core),-round(ow*data['rollFraction']),axis=1)
    Image.fromarray(pixels).save(output)
    report={'inputSHA256':digest(source),'outputSHA256':digest(output),
            'sourceSize':[w,h],'crop':[x0,0,x1,h], 'cropSize':[x1-x0,h],
            'outputSize':[ow,oh],'aspectCorrectionFraction':correction,
            'maxAspectCorrectionFraction':max_correction,'upsampled':False,
            'seamAcceptance':'not established by unpadding; inspect wrap and edit-frame edges'}
    Path(str(output)+'.context.json').write_text(json.dumps(report,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ['pad','unpad']:
        p=sub.add_parser(name);p.add_argument('input',type=Path);p.add_argument('output',type=Path)
        p.add_argument('--metadata',required=True,type=Path)
        if name=='unpad':p.add_argument('--max-aspect-correction',type=float,default=.02)
    a=parser.parse_args()
    try:
        if a.command=='pad':pad(a.input,a.output,a.metadata)
        else:unpad(a.input,a.output,a.metadata,a.max_aspect_correction)
    except (ValueError,OSError,KeyError) as exc:parser.error(str(exc))

if __name__=='__main__':main()
