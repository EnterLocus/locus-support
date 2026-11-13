#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Split a perspective face into overlapping detail patches; rejoin without tone edits."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def split(source, directory, grid=4, context=32):
    if grid < 1 or context < 1:
        raise ValueError('grid and context must be positive')
    with Image.open(source) as image:
        image = image.convert('RGB')
        width, height = image.size
        if width != height or grid > width:
            raise ValueError('source must be square and grid must fit its width')
        directory.mkdir(parents=True, exist_ok=True)
        records = []
        for row in range(grid):
            for col in range(grid):
                core = [col*width//grid, row*height//grid,
                        (col+1)*width//grid, (row+1)*height//grid]
                # Equal square context even at image edges; clamp extension is
                # discarded by assembly outside the original face bounds.
                side = max(core[2]-core[0], core[3]-core[1])+2*context
                left, top = core[0]-context, core[1]-context
                a = np.asarray(image)
                xs = np.clip(np.arange(left, left+side), 0, width-1)
                ys = np.clip(np.arange(top, top+side), 0, height-1)
                name = 'r%d-c%d.png' % (row, col)
                Image.fromarray(a[ys[:, None], xs[None, :]]).save(directory/name)
                records.append({'file': name, 'core': core, 'origin': [left, top], 'size': side})
        metadata = {'width': width, 'height': height, 'grid': grid,
                    'context': context, 'tiles': records}
        (directory/'tiles.json').write_text(json.dumps(metadata, indent=2)+'\n')


def join(directory, output, normalize=False):
    data = json.loads((directory/'tiles.json').read_text())
    width, height = data['width'], data['height']
    total = np.zeros((height, width, 3), dtype=np.float64)
    weights = np.zeros((height, width), dtype=np.float64)
    provenance = []
    for tile in data['tiles']:
        side = tile['size']
        with Image.open(directory/tile['file']) as image:
            image = image.convert('RGB')
            if image.width != image.height:
                raise ValueError('tile must remain square: '+tile['file'])
            native = image.width
            if native != side:
                if not normalize:
                    raise ValueError('tile size changed; use --normalize-tiles explicitly')
                image = image.resize((side, side), Image.Resampling.LANCZOS)
            pixels = np.asarray(image)
        left, top = tile['origin']
        core = tile['core']
        x0, y0, x1, y1 = max(0,left), max(0,top), min(width,left+side), min(height,top+side)
        xs, ys = np.arange(x0,x1)+0.5, np.arange(y0,y1)+0.5
        c = data['context']
        # Core fully weighted; cosine fades only in context. Normalize summed
        # weights at crossings, preserving an unedited split/join exactly.
        def ramp(axis, lo, hi):
            distance = np.maximum(lo-axis, axis-hi).clip(0,c)
            return 0.5+0.5*np.cos(np.pi*distance/c)
        w = ramp(ys, core[1], core[3])[:,None]*ramp(xs, core[0], core[2])[None,:]
        total[y0:y1,x0:x1] += pixels[y0-top:y1-top,x0-left:x1-left]*w[:,:,None]
        weights[y0:y1,x0:x1] += w
        provenance.append({'file':tile['file'], 'nativeSide':native,
                           'storedSide':side, 'resizeScale':side/native})
    if np.any(weights == 0):
        raise ValueError('tile coverage incomplete')
    image = Image.fromarray(np.rint(total/weights[:,:,None]).clip(0,255).astype(np.uint8))
    image.save(output)
    Path(str(output)+'.tiles.json').write_text(json.dumps({'tiles':provenance},indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    sp=commands.add_parser('split')
    sp.add_argument('source',type=Path);sp.add_argument('directory',type=Path)
    sp.add_argument('--grid',type=int,default=4);sp.add_argument('--context',type=int,default=32)
    jo=commands.add_parser('join')
    jo.add_argument('directory',type=Path);jo.add_argument('output',type=Path)
    jo.add_argument('--normalize-tiles',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='split':split(args.source,args.directory,args.grid,args.context)
        else:join(args.directory,args.output,args.normalize_tiles)
    except (ValueError,OSError,KeyError) as exc:parser.error(str(exc))

if __name__=='__main__':main()
