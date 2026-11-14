#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Localize a reviewed native repair; retain source landmarks and outer pixels."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw,ImageFilter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--repair',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=False)
    source_path=Path(args.source);repair_path=Path(args.repair)
    source_image=Image.open(source_path).convert('RGB')
    repair_image=Image.open(repair_path).convert('RGB')
    if source_image.size!=repair_image.size:
        parser.error('Native source and repair dimensions must match; no resampling')
    if source_image.size!=(4096,4096):
        parser.error('This reviewed demo recipe requires native4096 square inputs')
    source=np.asarray(source_image,dtype=np.float32)
    repair=np.asarray(repair_image,dtype=np.float32)
    height,width=source.shape[:2]
    config=json.loads(Path(args.config).read_text())
    cx,cy=config['center'];rx,ry=config['outer_radii'];inner=config['inner_fraction']
    yy,xx=np.mgrid[:height,:width]
    rho=np.sqrt(((xx-cx)/rx)**2+((yy-cy)/ry)**2)
    t=np.clip((rho-inner)/(1-inner),0,1)
    alpha=(1+np.cos(np.pi*t))/2;alpha[rho>=1]=0
    protection=Image.new('L',(width,height),0);draw=ImageDraw.Draw(protection)
    for x,y,radius in config['protected_stones']:
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=255)
    protection=protection.filter(ImageFilter.GaussianBlur(14))
    protected=np.asarray(protection,dtype=np.float32)/255
    shadow=((source[:,:,0]-source[:,:,2]<18)&(source.mean(axis=2)<225))
    if 'shadow_protect_rectangles' in config:
        regions=np.zeros((height,width),bool)
        for x0,y0,x1,y1 in config['shadow_protect_rectangles']:
            regions[y0:y1,x0:x1]=True
        shadow&=regions
    shadow=shadow.astype(np.uint8)*255
    shadow=Image.fromarray(shadow).filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(12))
    protected=np.maximum(protected,np.asarray(shadow,dtype=np.float32)/255)
    alpha*=1-protected
    result=np.rint(source*(1-alpha[:,:,None])+repair*alpha[:,:,None]).astype(np.uint8)
    assert np.array_equal(result[alpha==0],source.astype(np.uint8)[alpha==0])
    for rows,cols in ((slice(0,128),slice(None)),(slice(-128,None),slice(None)),(slice(None),slice(0,128)),(slice(None),slice(-128,None))):
        assert np.array_equal(result[rows,cols],source.astype(np.uint8)[rows,cols])
    target=out/'ny-localized-r2.png';Image.fromarray(result).save(target)
    Image.fromarray(np.rint(alpha*255).astype(np.uint8)).save(out/'mask.png')
    Image.fromarray(np.rint(protected*255).astype(np.uint8)).save(out/'protection-mask.png')
    overlay=source.copy();overlay[:,:,0]=overlay[:,:,0]*(1-.4*alpha)+255*.4*alpha;overlay[:,:,1:]*=(1-.4*alpha[:,:,None])
    Image.fromarray(np.rint(overlay).astype(np.uint8)).resize((1536,1536),Image.Resampling.LANCZOS).save(out/'mask-preview.png')
    receipt={'source':args.source,'repair':args.repair,'config':args.config,
        'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'repair_sha256':hashlib.sha256(repair_path.read_bytes()).hexdigest(),
        'config_sha256':hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        'mask':'mask.png','mask_center':[cx,cy],'outer_radii':[rx,ry],'inner_fraction':inner,
        'protection':'Reviewed major stone circles and source cool cast-shadow pixels; no compact-particle transplant mask for API fine-texture reconstruction.',
        'shadow_protect_rectangles':config.get('shadow_protect_rectangles'),
        'outside_mask_decoded_source_exact':True,'four_128px_outer_bands_exact':True,
        'output':target.name,'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'native_size':[width,height],'resampled':False,'status':'CANDIDATE_PARENT_REVIEW_PENDING'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
