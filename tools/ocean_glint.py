"""Portable authored-water optics. Masks are never inferred from RGB albedo."""
import math
from pathlib import PurePosixPath

CAPABILITY = 'locus.view.ocean-glint.v1'
MINIMUM_APP = (1, 3, 2)


def validate(value):
    if not isinstance(value, dict) or set(value) != {'mask', 'intensity', 'roughness'}:
        raise ValueError('oceanGlint requires exactly mask, intensity, roughness')
    path = value['mask']
    if (not isinstance(path, str) or not path or len(path.encode('utf-8')) > 512
            or '\\' in path or any(ord(c) < 32 for c in path)
            or PurePosixPath(path).is_absolute() or not path.lower().endswith('.png')
            or any(p in ('', '.', '..') for p in path.split('/'))):
        raise ValueError('oceanGlint.mask must be a portable PNG path')
    for field, low, high in [('intensity', 0, 4), ('roughness', .08, 1)]:
        n = value[field]
        if type(n) not in (int, float) or not math.isfinite(n) or not low <= n <= high:
            raise ValueError('invalid oceanGlint.' + field)
    return value


def smoothstep(low, high, x):
    import numpy as np
    t = np.clip((x-low)/(high-low), 0, 1)
    return t*t*(3-2*t)


def cloud_transmission(mask):
    # Independent of the artistic diffuse shadow: optically thick clouds
    # block sunlight and the reflected eye ray completely.
    return 1-smoothstep(.05, .85, mask)


def radiance(n, view, light, mask, intensity, roughness, sun_cloud=0, eye_cloud=0):
    """GGX + separable exact Smith G1 + Schlick water F0=.02, linear scalar.

    n/view/light share one coordinate frame. view points FROM the surface TO
    the finite-distance eye. The graph generator mirrors these operations.
    """
    import numpy as np
    def unit(v):
        return v/np.sqrt(np.maximum(np.sum(v*v, axis=-1, keepdims=True), 1e-8))
    n, view, light = unit(np.asarray(n)), unit(np.asarray(view)), unit(np.asarray(light))
    half_raw = view+light
    half = unit(half_raw)
    nl = np.clip(np.sum(n*light, axis=-1), 0, 1)
    nv = np.clip(np.sum(n*view, axis=-1), 0, 1)
    nh = np.clip(np.sum(n*half, axis=-1), 0, 1)
    vh = np.clip(np.sum(view*half, axis=-1), 0, 1)
    a2 = np.clip(roughness, .08, 1)**4
    denominator = nh*nh*(a2-1)+1
    distribution = a2/(np.pi*np.maximum(denominator*denominator, 1e-8))
    def smith(x):
        return 2*x/np.maximum(x+np.sqrt(a2+(1-a2)*x*x), 1e-6)
    fresnel = .02+.98*(1-vh)**5
    spec = distribution*smith(nl)*smith(nv)*fresnel*nl/np.maximum(4*nl*nv, 1e-6)
    gates = smoothstep(0, .02, nl)*smoothstep(0, .02, nv)
    gates *= smoothstep(1e-8, 1e-6, np.sum(half_raw*half_raw, axis=-1))
    gates *= smoothstep(.9, .99, mask)*cloud_transmission(sun_cloud)*cloud_transmission(eye_cloud)
    return np.minimum(spec, 8)*np.clip(intensity, 0, 4)*gates
