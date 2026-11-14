#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Task-local, deterministic sand texture reuse; no provider calls.

The source API repair, input and native donor pixels remain immutable. This
reconstructs an invalid radial sand texture; it does not generate new detail.
"""
from pathlib import Path
import argparse
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def sha(data):
    return hashlib.sha256(data).hexdigest()


def design(x, y):
    return np.stack([np.ones_like(x), x, y], axis=-1)


def compact_particles(source_image, center, radii):
    """Protect existing compact particles; reject elongated radial scratches."""
    pixels=np.asarray(source_image,dtype=np.float32)
    low=np.asarray(source_image.filter(ImageFilter.GaussianBlur(8)),dtype=np.float32)
    dark=np.mean(pixels-low,axis=2)<-8
    width,height=source_image.size
    yy,xx=np.mgrid[:height,:width]
    dark&=(((xx-center[0])/radii[0])**2+((yy-center[1])/radii[1])**2)<1
    pending=set(map(int,np.flatnonzero(dark)))
    mask=Image.new('L',(width,height),0);draw=ImageDraw.Draw(mask)
    kept=[]
    while pending:
        first=pending.pop();stack=[first];component=[first]
        while stack:
            current=stack.pop();cy,cx=divmod(current,width)
            for dy in (-1,0,1):
                for dx in (-1,0,1):
                    if 0<=cx+dx<width and 0<=cy+dy<height:
                        nxt=(cy+dy)*width+cx+dx
                        if nxt in pending:
                            pending.remove(nxt);stack.append(nxt);component.append(nxt)
        if not 6<=len(component)<=250:
            continue
        coordinates=np.array([divmod(v,width) for v in component],dtype=np.float64)
        values=np.linalg.eigvalsh(np.cov(coordinates.T))
        if values[-1]/max(values[0],.5)>4:
            continue
        ymin,xmin=coordinates.min(axis=0);ymax,xmax=coordinates.max(axis=0)
        if max(xmax-xmin,ymax-ymin)>28:
            continue
        draw.ellipse((int(xmin)-3,int(ymin)-3,int(xmax)+3,int(ymax)+3),fill=255)
        kept.append([int(xmin),int(ymin),int(xmax),int(ymax),len(component)])
    return mask.filter(ImageFilter.GaussianBlur(2)),kept


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,help='Preserved native4096 square repair input')
    parser.add_argument('--donor',required=True,help='Preserved native4096 square donor image')
    parser.add_argument('--output-dir',required=True,help='Separate candidate/evidence directory')
    parser.add_argument('--config',required=True,help='Reviewed donor/mask/landmark coordinates JSON')
    parser.add_argument('--seed',type=int,default=20261113)
    args=parser.parse_args()
    source_path=Path(args.source).expanduser().resolve()
    donor_path=Path(args.donor).expanduser().resolve()
    OUT=Path(args.output_dir).expanduser().resolve();OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'ny-healed-candidate.png').exists():
        parser.error('Output candidate already exists; choose a separate output directory')
    config=json.loads(Path(args.config).read_text())
    DONORS=config['donor_boxes'];STONES=config['protected_stones'];SEED=args.seed
    source_image = Image.open(source_path).convert('RGB')
    source = np.asarray(source_image, dtype=np.float32)
    donor_image = Image.open(donor_path).convert('RGB')
    h, w = source.shape[:2]
    assert (w,h) == (4096,4096)
    rng = np.random.default_rng(SEED)

    # Exclude distinct particles/objects from the small-patch donor pool. The
    # donor low-pass is removed, so neither cast shading nor a stone shape is
    # copied into the replacement. Native residual samples retain grain scale.
    pool = []
    donor_records = []
    for index, box in enumerate(DONORS):
        patch_image = donor_image.crop(box)
        patch_path = OUT / ('donor-%02d.png' % index)
        patch_image.save(patch_path)
        patch = np.asarray(patch_image, dtype=np.float32)
        low = np.asarray(patch_image.filter(ImageFilter.GaussianBlur(18)), dtype=np.float32)
        residual = patch-low
        for py in range(0, 512-96+1, 8):
            for px in range(0, 512-96+1, 8):
                sample = residual[py:py+96,px:px+96]
                # Large dark debris, stone edges and foam fail this screen.
                if np.quantile(np.abs(sample), .995) <= 10 and np.max(np.abs(sample)) <= 26:
                    pool.append((index,px,py,sample.copy()))
        donor_records.append({'box':list(box),'path':patch_path.name,
            'png_sha256':sha(patch_path.read_bytes()),
            'decoded_rgb_sha256':sha(patch.astype(np.uint8).tobytes())})
    if len(pool) < 40:
        raise ValueError('Insufficient clean donor texture patches')

    yy,xx = np.mgrid[:h,:w]
    cx,cy = config['center']
    rx,ry = config['outer_radii']
    rho = np.sqrt(((xx-cx)/rx)**2+((yy-cy)/ry)**2)
    inner=config['inner_fraction']
    t=np.clip((rho-inner)/(1-inner),0,1)
    alpha=(1+np.cos(np.pi*t))/2
    alpha[rho>=1]=0
    protected_image=Image.new('L',(w,h),0)
    draw=ImageDraw.Draw(protected_image)
    for sx,sy,radius in STONES:
        draw.ellipse((sx-radius,sy-radius,sx+radius,sy+radius),fill=255)
    protected_image=protected_image.filter(ImageFilter.GaussianBlur(14))
    protected=np.asarray(protected_image,dtype=np.float32)/255
    particle_mask,particle_records=compact_particles(source_image,(cx,cy),(rx,ry))
    protected=np.maximum(protected,np.asarray(particle_mask,dtype=np.float32)/255)
    # Cool cast shadows have neutral/blue RGB, unlike warm bare sand. Keep
    # their native shape and pixels instead of transferring a shadow donor.
    luma=source.mean(axis=2)
    shadow=((source[:,:,0]-source[:,:,2]<18)&(luma<225)).astype(np.uint8)*255
    shadow_image=Image.fromarray(shadow).filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(12))
    shadow_protect=np.asarray(shadow_image,dtype=np.float32)/255
    protected=np.maximum(protected,shadow_protect)
    alpha*=1-protected

    # Fit only broad local bare-sand shading. Robust iterations discard pebble
    # edges/radial scratches. No whole-ground blur is written to the result.
    low=np.asarray(source_image.filter(ImageFilter.GaussianBlur(48)),dtype=np.float32)
    samples=(rho>0.8)&(rho<1.22)&(protected<.05)
    grid=np.zeros((h,w),bool);grid[::16,::16]=True;samples&=grid
    xn=(xx[samples]-cx)/rx;yn=(yy[samples]-cy)/ry
    basis=design(xn,yn);values=low[samples]
    weights=np.ones(len(values))
    for _ in range(5):
        coefficients=np.linalg.lstsq(basis*weights[:,None],values*weights[:,None],rcond=None)[0]
        fitted=np.einsum('...k,kc->...c',basis,coefficients,optimize=False)
        error=np.sqrt(np.mean((fitted-values)**2,axis=1))
        weights=np.minimum(1.,3./np.maximum(error,.001))
    shading=np.empty_like(source)
    for y0 in range(0,h,128):
        y1=min(h,y0+128)
        shading[y0:y1]=np.einsum('...k,kc->...c',design((xx[y0:y1]-cx)/rx,(yy[y0:y1]-cy)/ry),coefficients,optimize=False)

    # Overlap-add native residual patches with rotations/reflections and
    # cosine weights; randomness is fixed and every donor coordinate recorded.
    texture=np.zeros((h+96,w+96,3),np.float32)
    total=np.zeros((h+96,w+96),np.float32)
    total_squared=np.zeros_like(total)
    edge=np.hanning(96).astype(np.float32)
    window=np.maximum(np.outer(edge,edge),.0001)
    placements=[]
    for y0 in range(-48,h,48):
        for x0 in range(-48,w,48):
            if ((x0+48-cx)/rx)**2+((y0+48-cy)/ry)**2>1.18**2:
                continue
            index=int(rng.integers(len(pool)));di,dx,dy,patch=pool[index]
            rotation=int(rng.integers(4));flip=bool(rng.integers(2))
            patch=np.rot90(patch,rotation)
            if flip:patch=patch[:,::-1]
            ty,tx=y0+48,x0+48
            texture[ty:ty+96,tx:tx+96]+=patch*window[:,:,None]
            total[ty:ty+96,tx:tx+96]+=window
            total_squared[ty:ty+96,tx:tx+96]+=window**2
            placements.append([x0,y0,di,dx,dy,rotation,int(flip)])
    # Restore variance lost by averaging independent overlapping residuals.
    texture=texture[48:h+48,48:w+48]/np.maximum(np.sqrt(total_squared[48:h+48,48:w+48,None]),.0001)
    reconstructed=np.clip(shading+texture,0,255)
    output=np.rint(source*(1-alpha[:,:,None])+reconstructed*alpha[:,:,None]).astype(np.uint8)
    exact=alpha==0
    assert np.array_equal(output[exact],source.astype(np.uint8)[exact])
    output_path=OUT/'ny-healed-candidate.png'
    Image.fromarray(output).save(output_path)
    Image.fromarray(np.rint(alpha*255).astype(np.uint8)).save(OUT/'heal-mask.png')
    Image.fromarray(np.rint(protected*255).astype(np.uint8)).save(OUT/'protection-mask.png')
    # A color overlay makes mask extent and protected objects directly visible.
    overlay=source.copy();overlay[:,:,0]=overlay[:,:,0]*(1-.4*alpha)+255*.4*alpha
    overlay[:,:,1:]*=(1-.4*alpha[:,:,None])
    Image.fromarray(np.rint(overlay).astype(np.uint8)).resize((1536,1536),Image.Resampling.LANCZOS).save(OUT/'mask-preview.png')
    review=Image.new('RGB',(2400,832),'white');d=ImageDraw.Draw(review)
    for i,(im,label) in enumerate([(donor_image,'F ny original'),(source_image,'R1 localized, residual radial pattern'),(Image.fromarray(output),'Free native-sand heal candidate')]):
        review.paste(im.resize((800,800),Image.Resampling.LANCZOS),(800*i,32));d.text((800*i+8,10),label,fill='black')
    review.save(OUT/'before-after.png')
    # 1:1 evidence of the center, feather and protected landmarks.
    for name,box in [('center',(1600,1600,2624,2624)),('feather',(950,1700,1974,2724)),('stones',(2350,1150,3374,2174))]:
        pair=Image.new('RGB',(2048,1056),'white');d=ImageDraw.Draw(pair)
        pair.paste(source_image.crop(box),(0,32));pair.paste(Image.fromarray(output).crop(box),(1024,32))
        d.text((8,10),'Before 1:1 '+str(box),fill='black');d.text((1032,10),'Free heal 1:1',fill='black')
        pair.save(OUT/('native-'+name+'.png'))
    report={'status':'LOCAL_FREE_CANDIDATE_PARENT_REVIEW_PENDING','seed':SEED,
        'source':args.source,'source_sha256':sha(source_path.read_bytes()),
        'donor_source':args.donor,'donor_source_sha256':sha(donor_path.read_bytes()),
        'configuration':args.config,'configuration_sha256':sha(Path(args.config).read_bytes()),
        'donors':donor_records,'donor_pool_count':len(pool),'patch_size':96,'patch_stride':48,
        'donor_high_pass_sigma':18,'patch_exclusion_quantile995_abs_RGB':10,
        'patch_exclusion_max_abs_RGB':26,'placements':placements,
        'mask':{'center':[cx,cy],'outer_radii':[rx,ry],'inner_fraction':inner,
            'feather':'cosine','protected_stones':STONES,'shadow_guard':'R-B<18 and meanRGB<225, dilate8px, feather12px'},
        'compact_native_particles_preserved':particle_records,'variance_preserving_patch_overlap':True,
        'shading_fit':{'method':'robust local RGB plane on bare-sand annulus;5Huber-like iterations',
            'sample_count':len(values),'coefficients':coefficients.tolist(),'fit_low_pass_sigma':48},
        'outside_mask_pixels_exact':True,'output':output_path.name,
        'output_sha256':sha(output_path.read_bytes()),'size':[4096,4096],
        'generated_detail_claim':False,'description':'Deterministic reuse and rearrangement of native donor sand grain; no new API output, no enlargement, no whole-ground blur.',
        'paid_calls':0,'originals_overwritten':False}
    (OUT/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in
        ('placements','shading_fit','mask','compact_native_particles_preserved')},indent=2))


if __name__=='__main__':main()
