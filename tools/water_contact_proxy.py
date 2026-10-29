"""Source-side layered-contact mesh and nearest-hit reflection authoring (3.9).

The viewer consumes explicit assets; it never guesses contact from an unlabelled
water mask. A semantic near-land mask selects only authored objects. A separate
background plate supplies disoccluded sky/sea. The original water mask remains
the bathymetry source; the coverage override is used only for water opacity.
"""
import io
import json
import math
import bisect


def direction(uv):
    a,e=(uv[0]-.5)*2*math.pi,(.5-uv[1])*math.pi
    return (math.cos(e)*math.sin(a),math.sin(e),-math.cos(e)*math.cos(a))


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def uv(v):
    n=math.sqrt(dot(v,v))
    return ((.5+math.atan2(v[0],-v[2])/(2*math.pi))%1,.5-math.asin(max(-1,min(1,v[1]/n)))/math.pi)


def latitude_parameter(source_horizon_degrees, eye_height, sky_center, radius=80):
    if not math.isfinite(source_horizon_degrees) or abs(source_horizon_degrees)>=89:
        raise ValueError('source horizon must be finite and nonpolar')
    if sky_center[0] != 0 or sky_center[2] != 0:
        raise ValueError('latitude horizon calibration requires a vertically centered source sphere')
    target=(eye_height-sky_center[1])/radius
    if not -1<target<1:raise ValueError('reference eye must lie inside source sphere')
    source=math.sin(math.radians(source_horizon_degrees))
    return (target-source)/(1-target*source)


def latitude_v(v, a):
    value=math.sin((.5-v)*math.pi)
    return .5-math.asin(max(-1,min(1,(value+a)/(1+a*value))))/math.pi


def periodic_horizon(samples, u):
    """Linear periodic interpolation of an admitted authored horizon profile."""
    u %= 1
    index = max(0, bisect.bisect_right([p[0] for p in samples], u)-1)
    left = samples[index]
    right = samples[index+1] if index+1 < len(samples) else [1, samples[0][1]]
    return left[1]+(right[1]-left[1])*(u-left[0])/(right[0]-left[0])


def latitude_profile_reproject(image, samples, eye_height, sky_center):
    """Columnwise source preprocessing; positive latitude derivative everywhere.

    Chunked arrays bound temporary sampling memory. No horizontal resampling
    occurs, and the periodic authored profile agrees at the ERP seam.
    """
    import numpy as np
    from PIL import Image
    w,h=image.size
    parameters=np.array([latitude_parameter(periodic_horizon(samples,(x+.5)/w),eye_height,sky_center)
                         for x in range(w)])[None,:]
    source=np.asarray(image)
    output=np.empty_like(source)
    columns=np.arange(w)[None,:]
    for first in range(0,h,64):
        last=min(h,first+64)
        sine=np.sin((.5-(np.arange(first,last)[:,None]+.5)/h)*math.pi)
        source_y=(.5-np.arcsin(np.clip((sine-parameters)/(1-parameters*sine),-1,1))/math.pi)*h-.5
        row=np.floor(source_y).astype(np.int32)
        weight=source_y-row
        low=source[np.clip(row,0,h-1),columns].astype(np.float32)
        high=source[np.clip(row+1,0,h-1),columns].astype(np.float32)
        if source.ndim==3:weight=weight[:,:,None]
        output[first:last]=(low+(high-low)*weight).astype(np.uint8)
    result=Image.fromarray(output)
    result.info.update(image.info)
    return result


def latitude_reproject(image, a):
    """Source-only monotone latitude map, bilinear rows with periodic U intact."""
    from PIL import Image
    w,h=image.size;output=Image.new(image.mode,image.size);output.info.update(image.info)
    for y in range(h):
        source_y=latitude_v((y+.5)/h,-a)*h-.5
        row=math.floor(source_y);weight=source_y-row
        first=max(0,min(h-1,row));second=max(0,min(h-1,row+1))
        line=Image.blend(image.crop((0,first,w,first+1)),image.crop((0,second,w,second+1)),weight)
        output.paste(line,(0,y))
    return output


def register_plate_horizon(image, contour, target_v):
    """Register an explicitly authored crop contour, preserving every column.

    Coordinates are normalized pixel-boundary coordinates. Each column uses
    two positive affine maps: top -> top, target -> authored horizon, bottom
    -> bottom. This preprocesses only the repair plate, never the source photo.
    """
    from PIL import Image
    if (not isinstance(contour, list) or len(contour) < 2
            or (not callable(target_v) and not 0 < target_v < 1)
            or any(not isinstance(p, list) or len(p) != 2
                   or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                   or not 0 <= p[0] <= 1 or not 0 < p[1] < 1 for p in contour)
            or contour[0][0] != 0 or contour[-1][0] != 1
            or any(a[0] >= b[0] for a, b in zip(contour, contour[1:]))):
        raise ValueError('invalid authored background horizon contour')
    width, height = image.size
    output = Image.new(image.mode, image.size)
    output.info.update(image.info)
    segment = 0
    for x in range(width):
        u = (x + .5) / width
        target = target_v(u) if callable(target_v) else target_v
        if not math.isfinite(target) or not 0 < target < 1:
            raise ValueError('invalid target background horizon')
        while segment + 1 < len(contour) - 1 and u > contour[segment + 1][0]:
            segment += 1
        a, b = contour[segment:segment + 2]
        source_v = a[1] + (b[1] - a[1]) * (u - a[0]) / (b[0] - a[0])
        column = image.crop((x, 0, x + 1, height))
        for y in range(height):
            v = (y + .5) / height
            source_y = (v * source_v / target if v <= target else
                        source_v + (v - target) * (1 - source_v) / (1 - target)) * height - .5
            row = math.floor(source_y)
            first = max(0, min(height - 1, row))
            second = max(0, min(height - 1, row + 1))
            output.putpixel((x, y), tuple(round(a + (b - a) * (source_y - row))
                            for a, b in zip(column.getpixel((0, first)), column.getpixel((0, second)))))
    return output


def match_repair_boundary(source, fill, removal, bounds_uv):
    """Harmonic RGB correction of an authored fill, with known-photo boundary.

    Only pixels outside removal constrain the correction, so original land
    colors cannot leak back into the repaired interior. Solve on the bounded
    mask grid, refine from coarse to fine, then interpolate the smooth color
    correction at source resolution. The caller composites through removal.
    """
    import numpy as np
    from PIL import Image
    def crop_periodic(image, box):
        left,top,right,bottom=box;result=Image.new(image.mode,(right-left,bottom-top))
        x=left
        while x<right:
            end=min(right,x+image.width-x%image.width)
            result.paste(image.crop((x%image.width,top,x%image.width+end-x,bottom)),(x-left,0));x=end
        return result
    w,h=removal.size
    box=tuple(round(v*n) for v,n in zip(bounds_uv,(w,h,w,h)))
    mask=crop_periodic(removal,box)
    active=mask.getbbox()
    if active is None:return fill.copy()
    a,b,c,d=active;a=max(0,a-2);b=max(0,b-2);c=min(mask.width,c+2);d=min(mask.height,d+2)
    box=(box[0]+a,box[1]+b,box[0]+c,box[1]+d)
    mask=crop_periodic(removal,box);unknown=np.asarray(mask)>0
    if unknown[0].any() or unknown[-1].any() or unknown[:,0].any() or unknown[:,-1].any():
        raise ValueError('repair boundary must be inside the explicit author region')
    original=np.asarray(crop_periodic(source.resize((w,h),Image.Resampling.BOX),box),dtype=np.float32)
    proposed=np.asarray(crop_periodic(fill.resize((w,h),Image.Resampling.BOX),box),dtype=np.float32)
    boundary=original-proposed
    known_values=boundary[~unknown]
    minimum,maximum,mean=known_values.min(axis=0),known_values.max(axis=0),known_values.mean(axis=0)
    def resized(field,size):
        return np.stack([np.asarray(Image.fromarray(field[:,:,k]).resize(size,Image.Resampling.BILINEAR)) for k in range(3)],axis=2)
    correction=None
    for divisor in (8,4,2,1):
        size=(max(3,math.ceil(mask.width/divisor)),max(3,math.ceil(mask.height/divisor)))
        known=(~unknown).astype(np.float32)
        weights=np.asarray(Image.fromarray(known).resize(size,Image.Resampling.BILINEAR))
        weighted=resized(boundary*known[:,:,None],size)
        fixed=np.divide(weighted,weights[:,:,None],out=np.broadcast_to(mean,weighted.shape).copy(),where=weights[:,:,None]>0)
        inside=np.asarray(mask.resize(size,Image.Resampling.NEAREST))>0
        correction=fixed.copy() if correction is None else resized(correction,size)
        correction=np.clip(correction,minimum,maximum)
        correction[~inside]=fixed[~inside]
        selected=inside[1:-1,1:-1]
        for iteration in range(1200 if divisor==8 else 250):
            average=(correction[:-2,1:-1]+correction[2:,1:-1]+correction[1:-1,:-2]+correction[1:-1,2:])*.25
            interior=correction[1:-1,1:-1]
            error=np.max(np.abs(average[selected]-interior[selected])) if selected.any() else 0
            interior[selected]=average[selected]
            if error<.025:break
    scale_x,scale_y=source.width/w,source.height/h
    native=tuple(round(v*n) for v,n in zip(box,(scale_x,scale_y,scale_x,scale_y)))
    patch=crop_periodic(fill,native)
    corrected=np.clip(np.asarray(patch,dtype=np.float32)+resized(correction,patch.size),0,255).round().astype(np.uint8)
    patch=Image.fromarray(corrected);result=fill.copy();left,top,right,bottom=native;x=left
    while x<right:
        end=min(right,x+source.width-x%source.width)
        result.paste(patch.crop((x-left,0,end-left,bottom-top)),(x%source.width,top));x=end
    return result


def far_reflection_plate(background, eye_height, sky_center, reference_yaw_degrees=0, width=2048, height=1024):
    """Directional far radiance from E, explicitly accounting for E != C."""
    from PIL import Image
    source=background.convert('RGB');pixels=source.load();sw,sh=source.size
    result=Image.new('RGB',(width,height));result.info.update(source.info);out=result.load()
    angle=math.radians(reference_yaw_degrees);cy,sy=math.cos(angle),math.sin(angle)
    origin=sub((0,eye_height,0),sky_center);oo=dot(origin,origin)
    if not math.isfinite(oo) or oo>=80*80:raise ValueError('reference eye must lie inside source sphere')
    for y in range(height):
        for x in range(width):
            dx,dy,dz=direction(((x+.5)/width,(y+.5)/height))
            ray=(cy*dx+sy*dz,dy,-sy*dx+cy*dz)
            projection=dot(origin,ray);t=-projection+math.sqrt(projection*projection+80*80-oo)
            px,py,pz=tuple(origin[i]+t*ray[i] for i in range(3))
            u,v=uv((cy*px-sy*pz,py,sy*px+cy*pz))
            xx,yy=u*sw-.5,v*sh-.5;ix,iy=math.floor(xx),math.floor(yy);fx,fy=xx-ix,yy-iy
            def pixel(a,b):return pixels[a%sw,max(0,min(sh-1,b))]
            a,b,c,d=pixel(ix,iy),pixel(ix+1,iy),pixel(ix,iy+1),pixel(ix+1,iy+1)
            out[x,y]=tuple(round((a[k]*(1-fx)+b[k]*fx)*(1-fy)+(c[k]*(1-fx)+d[k]*fx)*fy) for k in range(3))
    return result


def validate_payload(p, maximum_contact_distance, reference_eye_height=None):
    def number(x):
        try:return type(x) in (int,float) and math.isfinite(x)
        except OverflowError:return False
    def integer(x):
        # JSON has one number type. Match Codable Int/UInt32: 1.0 is an
        # integer value, while booleans and fractional numbers are rejected.
        return number(x) and x == int(x)
    if not isinstance(p,dict) or set(p)!={'formatVersion','positionsMeters','sourceUV','textureUV','indices','contacts'} or not integer(p['formatVersion']) or p['formatVersion']!=1:
        raise ValueError('unsupported contact mesh')
    if not all(isinstance(p[key],list) for key in ('positionsMeters','sourceUV','textureUV','indices','contacts')):
        raise ValueError('invalid contact mesh arrays')
    n=len(p['positionsMeters'])
    if not 3<=n<=250000 or len(p['sourceUV'])!=n or len(p['textureUV'])!=n or not p['indices'] or len(p['indices'])>750000 or len(p['indices'])%3:
        raise ValueError('invalid contact mesh counts')
    if any(not isinstance(v,list) or len(v)!=3 or any(not number(x) or abs(x)>1000 for x in v) or v[1]<-1e-6 for v in p['positionsMeters']):
        raise ValueError('invalid dry terrain position')
    if any(not isinstance(v,list) or len(v)!=2 or any(not number(x) or not 0<=x<=1 for x in v) for v in p['sourceUV']+p['textureUV']):
        raise ValueError('invalid contact texture coordinate')
    if any(not integer(i) or not 0<=i<n for i in p['indices']) or not p['contacts']:
        raise ValueError('invalid contact mesh indices')
    used=set(p['indices']);seen=set()
    for c in p['contacts']:
        if not isinstance(c,dict) or set(c)!={'vertex','distanceMeters','kind'}:
            raise ValueError('invalid authored contact fields')
        i=c['vertex']; d=c['distanceMeters']
        if not integer(i) or i not in used or i in seen or c['kind'] not in ('shore','rock') or not number(d) or not .5<=d<maximum_contact_distance:
            raise ValueError('invalid authored contact')
        seen.add(i)
        x,y,z=p['positionsMeters'][int(i)]
        if abs(y)>1e-6 or abs(math.hypot(x,z)-d)>1e-4:raise ValueError('rendered contact misses the water plane or range')
    for i in range(0,len(p['indices']),3):
        a,b,c=[p['positionsMeters'][int(j)] for j in p['indices'][i:i+3]]
        normal=cross(sub(b,a),sub(c,a))
        if dot(normal,normal)<=1e-16:raise ValueError('degenerate contact triangle')
        if reference_eye_height is not None:
            view=sub((0,reference_eye_height,0),tuple((a[j]+b[j]+c[j])/3 for j in range(3)))
            if dot(normal,view)<=0:raise ValueError('contact triangle faces away from the reference eye')


def validate_assets(source, background, original_mask, removal, coverage, payload, maximum_contact_distance,
                    reference_eye_height=None, source_projection=None, reference_sky_center=None):
    """Actual pixel and geometry admission, also used by the ZIP publisher."""
    from PIL import Image, ImageChops
    images=[Image.open(io.BytesIO(x)) for x in (source,background,original_mask,removal,coverage)]
    photo,plate,mask,removed,shown=images
    if any(max(im.size)>32768 or im.width*im.height>150000000 for im in images):
        raise ValueError('contact image exceeds the image budget')
    if photo.size!=plate.size or mask.size!=removed.size or mask.size!=shown.size or mask.width!=mask.height*2 or photo.width%mask.width or photo.height%mask.height:
        raise ValueError('layered proxy asset dimensions do not match')
    if any(im.mode!='L' for im in (mask,removed,shown)):raise ValueError('contact masks must be grayscale')
    if removed.getextrema()!=(0,255):raise ValueError('removal mask must explicitly select a bounded region')
    # The author removal can include an antialias/disocclusion margin. The
    # remaining photo is invariant in decoded pixels, not JPEG encoding.
    protected=removed.resize(photo.size,Image.Resampling.NEAREST).point(lambda x:255 if x==0 else 0)
    changed=ImageChops.difference(photo.convert('RGB'),plate.convert('RGB'))
    if any(ImageChops.multiply(c,protected).getbbox() for c in changed.split()):
        raise ValueError('background changes pixels outside authored removal')
    if source_projection is not None:
        if source_projection['model']=='latitude-mobius-profile-v1':
            mask=latitude_profile_reproject(mask,source_projection['sourceHorizonSamples'],reference_eye_height,reference_sky_center)
        else:
            mask=latitude_reproject(mask,latitude_parameter(source_projection['sourceHorizonElevationDegrees'],reference_eye_height,reference_sky_center))
    expected=ImageChops.lighter(mask,removed)
    # One gray level allows platform rounding in the analytic bilinear reprojection.
    tolerance=1 if source_projection is not None else 0
    if (ImageChops.subtract(expected,shown).getextrema()[1]>tolerance
            or ImageChops.subtract(removed,shown).getbbox()):
        raise ValueError('water coverage must cover projected original wet pixels and authored removal')
    validate_payload(payload,maximum_contact_distance,reference_eye_height)
    for source_uv in payload['sourceUV']:
        x=int(source_uv[0]*removed.width)%removed.width;y=min(removed.height-1,int(source_uv[1]*removed.height))
        if not removed.getpixel((x,y)):raise ValueError('land vertex is outside authored removal support')
    return dict(vertices=len(payload['positionsMeters']),triangles=len(payload['indices'])//3,
                contacts=len(payload['contacts']),protectedPixelsUnchanged=True)


def reflection_plate(payload, background, source, capture_origin, width=2048, height=1024, reference_yaw_degrees=0):
    """Radiance arriving along +ray from mirrored reference eye. NOT mirrored RGB.

    The original shader reflects its view ray once, then samples this texture.
    Separate patches may overlap; choose nearest positive ray/triangle hit with
    the directional far plate behind all positive land hits. Results are
    independent of draw order.
    """
    from PIL import Image
    output=background.convert('RGB').resize((width,height),Image.Resampling.LANCZOS)
    pixels=output.load();original=source.convert('RGB');rgb=original.load()
    depths=[math.inf]*(width*height)
    angle=-math.radians(reference_yaw_degrees);cy,sy=math.cos(angle),math.sin(angle)
    def canonical(point):
        x,y,z=sub(point,capture_origin)
        return (cy*x+sy*z,y,-sy*x+cy*z)
    for index in range(0,len(payload['indices']),3):
        ids=[int(i) for i in payload['indices'][index:index+3]]
        points=[canonical(payload['positionsMeters'][i]) for i in ids]
        mapped=[list(uv(p)) for p in points]
        if max(p[0] for p in mapped)-min(p[0] for p in mapped)>.5:
            for p in mapped:
                if p[0]<.5:p[0]+=1
        x0=math.floor(min(p[0] for p in mapped)*width-.5);x1=math.ceil(max(p[0] for p in mapped)*width-.5)
        y0=max(0,math.floor(min(p[1] for p in mapped)*height-.5));y1=min(height-1,math.ceil(max(p[1] for p in mapped)*height-.5))
        if x1-x0>=width or y0>y1:continue
        a,b,c=points;e1,e2=sub(b,a),sub(c,a);normal=cross(e1,e2)
        d00,d01,d11=dot(e1,e1),dot(e1,e2),dot(e2,e2);denom=d00*d11-d01*d01
        if denom<1e-18:continue
        suvs=[payload['sourceUV'][i] for i in ids]
        if max(p[0] for p in suvs)-min(p[0] for p in suvs)>.5:
            suvs=[(u+1 if u<.5 else u,v) for u,v in suvs]
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                ray=direction(((x+.5)/width,(y+.5)/height));dn=dot(normal,ray)
                if abs(dn)<1e-14:continue
                t=dot(normal,a)/dn;pixel=y*width+x%width
                if t<=0 or t>=depths[pixel]:continue
                offset=sub(tuple(t*r for r in ray),a);d20,d21=dot(offset,e1),dot(offset,e2)
                beta=(d11*d20-d01*d21)/denom;gamma=(d00*d21-d01*d20)/denom
                if beta< -1e-7 or gamma< -1e-7 or beta+gamma>1+1e-7:continue
                u=sum(suvs[i][0]*q for i,q in enumerate((1-beta-gamma,beta,gamma)))%1
                v=sum(suvs[i][1]*q for i,q in enumerate((1-beta-gamma,beta,gamma)))
                pixels[x%width,y]=rgb[min(original.width-1,int(u*original.width)),max(0,min(original.height-1,int(v*original.height)))]
                depths[pixel]=t
    return output


def bake_patch(alpha, water_mask, bounds_pixels, frame, kind, range_scale, inland_depth=20, slope=.15, step=6,
               source_v_transform=None):
    """Bake one explicitly selected land patch; no other panorama pixels enter.

    Per-column contact samples come only from the authored near-land selection
    intersecting the original water contour. The emitted asset records those
    samples as real vertices, rather than asking the viewer to infer them.
    """
    w,h=alpha.size;land=alpha.load();water=water_mask.load();ww,wh=water_mask.size;x0,y0,x1,y1=bounds_pixels
    eye=frame['referenceEyeHeightMeters'];center=frame['referenceSkyCenterMeters'];yaw=math.radians(frame['referenceYawDegrees'])
    def sample(im,u,v,iw=w,ih=h):
        x=u*iw-.5;y=v*ih-.5;ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
        def p(a,b):return im[a%iw,max(0,min(ih-1,b))]/255
        return (p(ix,iy)*(1-fx)+p(ix+1,iy)*fx)*(1-fy)+(p(ix,iy+1)*(1-fx)+p(ix+1,iy+1)*fx)*fy
    def source_point(u,v):
        if source_v_transform is not None:v=source_v_transform(u%1,v)
        x,y,z=direction((u,v));x,z=math.cos(yaw)*x+math.sin(yaw)*z,-math.sin(yaw)*x+math.cos(yaw)*z
        return (center[0]+80*x,center[1]+80*y,center[2]+80*z)
    feet={}
    for x in range(math.floor(x0*ww/w),math.ceil(x1*ww/w)+1):
        for y in range(max(1,math.floor(y0*wh/h)),min(wh,math.ceil(y1*wh/h))):
            a=water[x%ww,y-1]/255;b=water[x%ww,y]/255
            if a<.5<=b and sample(land,(x+.5)/ww,(y-.5)/wh)>.25:
                feet[x]=(y-.5+(.5-a)/(b-a))/wh
    if not feet:raise ValueError('authored patch has no selected water contact')
    from bisect import bisect_left,bisect_right
    foot_columns=sorted(feet)
    def foot(u):
        x=u*ww-.5;i=bisect_right(foot_columns,x)
        if i==0:return feet[foot_columns[0]]
        if i==len(foot_columns):return feet[foot_columns[-1]]
        left,right=foot_columns[i-1:i+1]
        return feet[left]*(right-x)/(right-left)+feet[right]*(x-left)/(right-left)
    payload=dict(formatVersion=1,positionsMeters=[],sourceUV=[],textureUV=[],indices=[],contacts=[])
    cache={};contour=[]
    for x,v in sorted(feet.items()):
        u=(x+.5)/ww;bx,by,bz=source_point(u,v);rho=math.hypot(bx,bz)
        contour.append([u%1,v,eye*rho/(eye-by)*range_scale])
    def add(u,v,contact=False):
        key=(round(u,10),round(v,10),contact)
        if key in cache:return cache[key]
        fv=foot(u);bx,by,bz=source_point(u,fv);rho=math.hypot(bx,bz)
        if eye<=by:raise ValueError('selected contact is above the reference geometric horizon')
        d=eye*rho/(eye-by)*range_scale
        shift=-math.atan2(eye,d)-math.atan2(by-eye,rho)
        px,py,pz=source_point(u,v);horizontal=math.hypot(px,pz);elevation=math.atan2(py-eye,horizontal)+shift
        if kind=='rock':r=d
        else:
            denominator=slope-math.tan(elevation)
            r=(eye+slope*d)/denominator if denominator>1e-5 else d+inland_depth
            r=max(d,min(d+inland_depth,r))
        p=[r*px/horizontal,eye+r*math.tan(elevation),r*pz/horizontal]
        if contact:p=[d*px/horizontal,0,d*pz/horizontal]
        index=len(payload['positionsMeters']);cache[key]=index
        payload['positionsMeters'].append(p);payload['sourceUV'].append([u%1,v])
        rect=frame['textureRectUV'];payload['textureUV'].append([(u-rect[0])/(rect[2]-rect[0]),(v-rect[1])/(rect[3]-rect[1])])
        if contact:payload['contacts'].append(dict(vertex=index,distanceMeters=d,kind=kind))
        return index
    def emit(triangle):
        polygon=[]
        for i,a in enumerate(triangle):
            b=triangle[(i+1)%3];inside=a[2]>=.5;other=b[2]>=.5
            if inside:polygon.append((a[0],a[1],False))
            if inside!=other:
                t=(.5-a[2])/(b[2]-a[2]);u=a[0]+(b[0]-a[0])*t;v=a[1]+(b[1]-a[1])*t
                polygon.append((u,v,False))
        # The authored lower contact is a constraint edge, not a gradient
        # label on an unrelated silhouette. Clip away all below-foot source
        # samples and insert the exact selected contour into the mesh.
        constrained=[]
        for i,a in enumerate(polygon):
            b=polygon[(i+1)%len(polygon)]
            fa=foot(a[0])-a[1];fb=foot(b[0])-b[1]
            inside=fa>=-1e-12;other=fb>=-1e-12
            if inside:constrained.append((a[0],a[1],abs(fa)<1e-12))
            if inside!=other:
                t=fa/(fa-fb);u=a[0]+(b[0]-a[0])*t
                constrained.append((u,foot(u),True))
        polygon=constrained
        for i in range(1,len(polygon)-1):
            tri=[polygon[0],polygon[i],polygon[i+1]]
            area=(tri[1][0]-tri[0][0])*(tri[2][1]-tri[0][1])-(tri[1][1]-tri[0][1])*(tri[2][0]-tri[0][0])
            if abs(area)<1e-14:continue
            ids=[add(*vertex) for vertex in tri]
            points=[payload['positionsMeters'][i] for i in ids]
            n=cross(sub(points[1],points[0]),sub(points[2],points[0]))
            if dot(n,n)>1e-16:payload['indices'].extend(ids)
    # Source-resolution silhouette, coarse interior. Refine every cell that
    # contains an alpha boundary, including a thin frond missed by its corners.
    # Stitch neighboring cell edges before triangulation, so there are no
    # T-junctions on the curved authored surface.
    leaves=[];horizontal={};vertical={}
    def extrema(a,b,c,d):
        values=[];left=a
        while left<=c:
            right=min(c,(left//w+1)*w-1)
            values.extend(alpha.crop((left%w,b,right%w+1,d+1)).getextrema())
            left=right+1
        return min(values),max(values)
    def cell(a,b,c,d):
        low,high=extrema(a,b,c,d)
        if high<128:return
        feet_at_sides=[foot((x+.5)/w)*h-.5 for x in (a,c)]
        contact_cell=min(feet_at_sides)<=d and max(feet_at_sides)>=b
        if (low<128 or contact_cell) and (c-a>1 or d-b>1):
            xs=[a,c] if c-a==1 else [a,(a+c)//2,c]
            ys=[b,d] if d-b==1 else [b,(b+d)//2,d]
            for i in range(len(xs)-1):
                for j in range(len(ys)-1):cell(xs[i],ys[j],xs[i+1],ys[j+1])
            return
        leaves.append((a,b,c,d))
        for x,y in ((a,b),(a,d),(c,b),(c,d)):
            horizontal.setdefault(y,set()).add(x);vertical.setdefault(x,set()).add(y)
    for y in range(y0,y1,step):
        for x in range(x0,x1,step):cell(x,y,min(x+step,x1),min(y+step,y1))
    horizontal={y:sorted(xs) for y,xs in horizontal.items()};vertical={x:sorted(ys) for x,ys in vertical.items()}
    def between(values,a,b):return values[bisect_left(values,a):bisect_right(values,b)]
    for a,b,c,d in leaves:
        boundary=([(x,b) for x in between(horizontal[b],a,c)]+[(c,y) for y in between(vertical[c],b,d)[1:]]+
                  [(x,d) for x in reversed(between(horizontal[d],a,c)[:-1])]+[(a,y) for y in reversed(between(vertical[a],b,d)[1:-1])])
        middle=((a+c+1)/2/w,(b+d+1)/2/h)
        triangle_center=(*middle,sample(land,*middle))
        for i,(x,y) in enumerate(boundary):
            q,r=boundary[(i+1)%len(boundary)]
            # The viewer is inside the panorama. Top-left UV has downward V,
            # so source-negative winding faces the viewing side of this land.
            emit([triangle_center,((q+.5)/w,(r+.5)/h,land[q%w,r]/255),((x+.5)/w,(y+.5)/h,land[x%w,y]/255)])
    used=sorted(set(payload['indices']));mapping={old:new for new,old in enumerate(used)}
    for key in ('positionsMeters','sourceUV','textureUV'):payload[key]=[payload[key][i] for i in used]
    payload['indices']=[mapping[i] for i in payload['indices']]
    payload['contacts']=[dict(c,vertex=mapping[c['vertex']]) for c in payload['contacts'] if c['vertex'] in mapping]
    # Certify actual emitted projection, not just the interpolation formula.
    for index in range(0,len(payload['indices']),3):
        ids=payload['indices'][index:index+3]
        original=[list(payload['sourceUV'][i]) for i in ids]
        projected=[list(uv(sub(payload['positionsMeters'][i],(0,eye,0)))) for i in ids]
        for triangle in (original,projected):
            if max(p[0] for p in triangle)-min(p[0] for p in triangle)>.5:
                for point in triangle:
                    if point[0]<.5:point[0]+=1
        def area(t):return (t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0])
        if area(original)*area(projected)<=0:
            raise ValueError('authored land projection folds at triangle '+str(index//3)+': '+repr((original,projected,[payload['positionsMeters'][i] for i in ids])))
    validate_payload(payload,1e6,eye)
    return payload,contour
