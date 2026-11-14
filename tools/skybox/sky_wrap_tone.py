#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Two-pass row-local repair of a small exposure line in an inspected sky wrap.

Step cancellation uses adjacent samples, never distant sky regions. Residual
horizontal smoothing is gated to smooth neighborhoods. Shifted clouds/objects
need a content edit. All pixel parameters scale from a 12288-wide reference.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import skybox


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kernel(sigma):
    radius=max(1,int(np.ceil(3*sigma)))
    x=np.arange(-radius,radius+1)
    k=np.exp(-.5*(x/max(sigma,1e-6))**2)
    return k/k.sum()


def gaussian(values,sigma,axis=0):
    if sigma<=0:
        return values.copy()
    k=kernel(sigma);radius=len(k)//2
    return np.apply_along_axis(lambda v: np.convolve(
        np.pad(v,(radius,radius),mode="edge"),k,mode="valid"),axis,values)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source");p.add_argument("output");p.add_argument("mask")
    p.add_argument("--full-v",type=float,default=.40)
    p.add_argument("--end-v",type=float,default=.48)
    p.add_argument("--max-offset",type=float,default=12)
    a=p.parse_args()
    if not 0<=a.full_v<a.end_v<=.5 or a.max_offset<=0:
        p.error("use 0<=full-v<end-v<=.5 and a positive maximum offset")
    if Path(a.output).suffix.lower()!=".png" or Path(a.source).resolve()==Path(a.output).resolve():
        p.error("use a separate PNG output")
    raw=skybox.image_array(a.source);h,w=raw.shape[:2]
    if w!=2*h or w<128:
        p.error("source must be 2:1 ERP at least128 pixels wide")
    before_hash=sha(a.source);scale=w/12288
    block=max(1,round(16*scale));ramp=max(2,round(400*scale))
    window=max(2,round(96*scale));radius=max(1,round(48*scale))
    span=min(w//4,max(ramp,window)+max(4,round(80*scale)))
    original=np.concatenate((raw[:,-span:],raw[:,:span]),axis=1).astype(np.float32)
    c=span
    xs=np.arange(2*span)
    dist=np.where(xs<c,c-1-xs,xs-c)
    rc=np.where(dist<ramp,.5*(1+np.cos(np.pi*np.minimum(dist,ramp)/ramp)),0)
    smoothed=gaussian(original,3*scale,axis=1)
    step=smoothed[:,c:c+block].mean(axis=1)-smoothed[:,c-block:c].mean(axis=1)
    half=np.clip(gaussian(step,40*scale,axis=0)/2,-a.max_offset,a.max_offset)
    sign=np.where(xs<c,1.,-1.)
    step1=original+rc[None,:,None]*sign[None,:,None]*half[:,None,:]
    luma=np.einsum("...i,i->...",step1,np.array([.299,.587,.114]))
    seam=np.abs(luma[:,c]-luma[:,c-1])
    dx=np.abs(np.diff(luma[:,c-window:c+window],axis=1))
    neighborhood=np.delete(dx,window-1,axis=1).mean(axis=1)
    lap=(np.roll(luma,1,axis=1)+np.roll(luma,-1,axis=1)+
         np.concatenate((luma[:1],luma[:-1]))+
         np.concatenate((luma[1:],luma[-1:]))-4*luma)
    nearby=np.concatenate((lap[:,c-window:c-radius],lap[:,c+radius:c+window]),axis=1)
    energy=(nearby**2).mean(axis=1) if nearby.shape[1] else np.zeros(h)
    flagged=(seam/np.maximum(neighborhood,1e-6)>1.2)&(energy<25)
    row_weight=gaussian(flagged.astype(float),30*scale,axis=0)
    feather=np.clip(1-dist/radius,0,1)
    weight=row_weight[:,None]*feather[None,:]
    corrected=step1+weight[...,None]*(gaussian(step1,20*scale,axis=1)-step1)
    v=(np.arange(h)+.5)/h
    sky=1-skybox.smoothstep((v-a.full_v)/(a.end_v-a.full_v))
    corrected=np.rint(np.clip(original+sky[:,None,None]*(corrected-original),0,255)).astype(np.uint8)
    output=raw.copy()
    output[:,-span:]=corrected[:,:span]
    output[:,:span]=corrected[:,span:]
    skybox.save_array(a.output,output)
    mask=np.zeros((h,w),dtype=np.uint8)
    alpha=sky[:,None]*np.maximum(rc[None,:],weight)
    mask[:,-span:]=np.rint(alpha[:,:span]*255).astype(np.uint8)
    mask[:,:span]=np.rint(alpha[:,span:]*255).astype(np.uint8)
    Image.fromarray(mask,"L").save(a.mask)
    delta=np.abs(output.astype(float)-raw)
    report={"method":"Adjacent row-local step cancellation plus smooth-neighborhood residual-line touchup",
            "sourceSHA256":before_hash,"outputSHA256":sha(a.output),"size":[w,h],
            "referenceWidth":12288,"scale":scale,"parametersAtReferenceWidth":{
                "presmoothSigma":3,"adjacentBlock":16,"rowSigma":40,"cosineRamp":400,
                "residualWindow":96,"localSigma":20,"localRadius":48,"flagRowSigma":30},
            "fullV":a.full_v,"endV":a.end_v,"maxPerSideStepOffsetRGB":a.max_offset,
            "residualRowsFlagged":int(flagged.sum()),
            "actualMaxChangeRGB":delta.max(axis=(0,1)).tolist(),
            "changedPixels":int(np.any(output!=raw,axis=2).sum()),
            "groundUnchanged":bool(np.array_equal(output[h//2+1:],raw[h//2+1:])),
            "detailClaim":"Source geometry retained; gated local horizontal smoothing is not generated detail",
            "paidCalls":0}
    Path(str(a.output)+".tone.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    main()
