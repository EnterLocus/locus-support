#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Match clean-blue sky tone to coherent source cube-face projections.

The default uses one measured median RGB offset per face. --spatial instead
fits a robust quadratic low-frequency RGB residual field. Both modes use soft
source/candidate chroma guards to exclude foreground and cloud whites.
This local authoring recipe makes no API calls, invents no detail and warps
no geometry. Native enhanced-face pixel grids and raw input files stay intact.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-faces',type=Path,required=True,
               help='Coherent G projections with six face PNGs and metadata.json')
p.add_argument('--enhanced-faces',type=Path,required=True,
               help='Native F face PNGs on the same projection and full framing')
p.add_argument('--output-dir',type=Path,required=True)
p.add_argument('--audit-dir',type=Path,required=True)
p.add_argument('--spatial',action='store_true',help='Fit robust quadratic RGB residuals')
args=p.parse_args()
if args.output_dir.resolve() in (args.source_faces.resolve(),args.enhanced_faces.resolve()):
    p.error('Output directory must differ from both input directories')
OUT=args.output_dir;AUDIT=args.audit_dir
OUT.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
shutil.copyfile(args.source_faces/'metadata.json',OUT/'metadata.json')

def smooth(x):
    x=np.clip(x,0,1);return x*x*(3-2*x)

def blue_weight(p):
    r,g,b=[p[:,:,i] for i in range(3)]
    return smooth((b-g-18)/24)*smooth((g-r-12)/24)*smooth((190-r)/70)

def hemisphere(face,n):
    if face=='ny':return np.zeros((n,1),dtype=np.float32)
    if face=='py':return np.ones((n,1),dtype=np.float32)
    row=(np.arange(n,dtype=np.float32)+.5)/n
    return (1-smooth((row-.485)/.015))[:,None]

rows=[]
for face in ['px','nx','pz','nz','py','ny']:
    src_im=Image.open(args.source_faces/(face+'.png')).convert('RGB')
    raw_im=Image.open(args.enhanced_faces/(face+'.png')).convert('RGB')
    src=np.asarray(src_im,dtype=np.float32)
    low=np.asarray(raw_im.resize(src_im.size,Image.Resampling.LANCZOS),dtype=np.float32)
    fit_mask=(blue_weight(src)>.98)&(blue_weight(low)>.98)&(hemisphere(face,src_im.width)>.98)
    offset=np.median((src-low)[fit_mask],axis=0) if np.any(fit_mask) else np.zeros(3)
    coefficients=None
    if args.spatial and np.any(fit_mask):
        yy,xx=np.nonzero(fit_mask)
        # Bounded deterministic subsampling; robust quadratic fit contains no image detail.
        yy,xx=yy[::8],xx[::8]
        x=2*(xx+.5)/src_im.width-1;y=2*(yy+.5)/src_im.height-1
        design=np.stack([np.ones_like(x),x,y,x*x,x*y,y*y],axis=1)
        target=(src-low)[yy,xx]
        coefficients=np.linalg.lstsq(design,target,rcond=None)[0]
        for _ in range(3):
            error=np.linalg.norm(target-np.einsum('ij,jk->ik',design,coefficients),axis=1)
            weight=np.sqrt(np.minimum(1,6/np.maximum(error,1e-6)))
            coefficients=np.linalg.lstsq(design*weight[:,None],target*weight[:,None],rcond=None)[0]
        if not np.isfinite(coefficients).all():
            raise RuntimeError('Nonfinite spatial color fit; stop without exporting')
    raw=np.asarray(raw_im,dtype=np.float32)
    reference=np.asarray(src_im.resize(raw_im.size,Image.Resampling.LANCZOS),dtype=np.float32)
    alpha=np.minimum(blue_weight(reference),blue_weight(raw))*hemisphere(face,raw_im.width)
    correction=offset
    if coefficients is not None:
        x=(2*(np.arange(raw_im.width,dtype=np.float32)+.5)/raw_im.width-1)[None,:]
        y=(2*(np.arange(raw_im.height,dtype=np.float32)+.5)/raw_im.height-1)[:,None]
        correction=np.broadcast_to(coefficients[0],raw.shape).copy()
        for term,c in zip([x,y,x*x,x*y,y*y],coefficients[1:]):
            correction+=term[:,:,None]*c
        correction=np.clip(correction,-40,40)
    corrected=np.rint(np.clip(raw+alpha[:,:,None]*correction,0,255)).astype(np.uint8)
    Image.fromarray(corrected).save(OUT/(face+'.png'))
    Image.fromarray(np.rint(alpha*255).astype(np.uint8),'L').save(AUDIT/(face+'-mask.png'))
    difference=np.abs(corrected.astype(np.float32)-raw)
    Image.fromarray(np.clip(difference*8,0,255).astype(np.uint8)).save(AUDIT/(face+'-difference-x8.png'))
    sheet=Image.new('RGB',(1536,554),'white');d=ImageDraw.Draw(sheet)
    for i,(im,label) in enumerate([(raw_im,'Raw F'),(Image.fromarray(corrected),'Sky tone corrected'),(Image.fromarray(np.rint(alpha*255).astype(np.uint8)).convert('RGB'),'Source/candidate chroma mask')]):
        sheet.paste(im.resize((512,512)),(i*512,42));d.text((i*512+8,10),face+' '+label,fill='black')
    sheet.save(AUDIT/(face+'-comparison.png'))
    rows.append({'face':face,'native_source_dimensions':list(src_im.size),'native_dimensions':list(raw_im.size),'fit_sample_pixels':int(fit_mask.sum()),'additive_RGB_offset_at_full_mask':offset.tolist(),'spatial_coefficients_1_x_y_x2_xy_y2':coefficients.tolist() if coefficients is not None else None,'mask_nonzero_fraction':float(np.mean(alpha>0)),'mask_full_fraction':float(np.mean(alpha>.98)),'actual_max_abs_RGB_change':difference.max(axis=(0,1)).tolist(),'source':str(args.source_faces/(face+'.png')),'raw':str(args.enhanced_faces/(face+'.png')),'output':str(OUT/(face+'.png'))})
report={'method':'Independent constant per-face RGB offset fitted by median G-minus-F in clean blue sky, with soft source/candidate chroma guard; no cloud/foliage geometry change','source':'Coherent source projections, upsampled for mask only; not new detail','parameters':{key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items()},'fit':'median of source minus F-downsample in both blue_weight>.98 and upper hemisphere','soft_mask':'min(source_blue_weight,candidate_blue_weight)*upper_hemisphere; cloudwhite and vegetation excluded by chroma','blue_weight':'smoothstep((B-G-18)/24)*smoothstep((G-R-12)/24)*smoothstep((190-R)/70)','hemisphere':'py all, ny none, side faces fade from normalized row.485 to.5','difference_preview_multiplier':8,'raws_unchanged':True,'paid_calls':0,'rows':rows}
if args.spatial:
    report['method']='Robust quadratic low-frequency per-face RGB correction fitted to coherent G blue-sky reference, with unchanged soft source/candidate chroma guard'
    report['fit']='3 Huber-style robust reweighting passes, threshold6 RGB norm, every8th clean-sky fit pixel; basis1,x,y,x2,xy,y2; correction bounded+/-40 RGB'
(AUDIT/'method.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
