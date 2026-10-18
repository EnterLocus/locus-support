# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Schwarzschild lens for a far-field Locus black-hole View.

Authoring-only numerics (NumPy, no SciPy) that bake everything a black-hole
View needs except time:

- Where every viewing direction ends up: the celestial sphere at infinity
  (an escape direction), the horizon (captured), or a thin opaque accretion
  disc (radius, disc azimuth and the frequency shift g of the first hit).
- Because the observer and the hole are fixed in the View frame (head pose
  never repositions far-field content), that map never changes. Locus only animates the disc's emission along the baked
  coordinates, so no ray is traced on device.

Units: G = c = M = 1, so the horizon is r = 2, the photon sphere r = 3, the
ISCO r = 6 and the critical impact parameter 3*sqrt(3). The observer is a
static observer at radius `observer_radius`; its local viewing directions are
the View-frame directions. Rays are traced backwards from the observer.

Each ray lies in the plane spanned by e1 (BH -> observer) and e2 (the ray's
component perpendicular to e1); with u = 1/r and the in-plane angle phi from
e1 it obeys u'' = -u + 3u^2, u'(0) = cos(alpha)/b, where alpha is the angle
from the direction of the hole and b = r_O sin(alpha) / sqrt(1 - 2/r_O). The
in-plane solution depends on alpha alone, so u(phi) is tabulated once per
alpha (rows log-spaced about the critical angle) and every pixel only
interpolates. The disc plane meets the ray's plane along a line through the
hole, so the ray crosses it at phi0 + k*pi.

Disc emitters move on circular geodesics (Omega = r^-3/2 about the disc normal
n); for the physical photon (opposite to the traced ray) with lambda = L_n/E,
g = sqrt(1 - 3/r) / ((1 - Omega*lambda) * sqrt(1 - 2/r_O)).
"""
import math

import numpy as np

B_CRIT = 3.0 * math.sqrt(3.0)
HORIZON_U = 0.5
CAPTURED, ESCAPED, UNRESOLVED = 1, 2, 0


def _rk4(u, v, h):
    """One RK4 step of u'' = -u + 3u^2 written as (u, v = u')."""
    def acc(x):
        return -x + 3.0 * x * x
    k1u, k1v = v, acc(u)
    k2u, k2v = v + 0.5 * h * k1v, acc(u + 0.5 * h * k1u)
    k3u, k3v = v + 0.5 * h * k2v, acc(u + 0.5 * h * k2u)
    k4u, k4v = v + h * k3v, acc(u + h * k3u)
    return (u + h / 6.0 * (k1u + 2 * k2u + 2 * k3u + k4u),
            v + h / 6.0 * (k1v + 2 * k2v + 2 * k3v + k4v))


def integrate(u0, v0, steps, phi_max, store=False):
    """Integrate many rays (arrays u0, v0, per-ray steps) to the horizon or infinity.

    Returns (outcome, phi_end, samples). `phi_end` is where u reaches the
    horizon (captured) or zero while decreasing (escaped); UNRESOLVED rays ran
    out of `phi_max`. With `store`, `samples[i, j]` is u at phi = j*steps[i],
    including the one sample just past the end so linear interpolation is
    valid up to `phi_end`; unused entries are NaN.
    """
    u = np.array(u0, dtype=np.float64)
    v = np.array(v0, dtype=np.float64)
    h = np.array(steps, dtype=np.float64)
    count = u.shape[0]
    outcome = np.full(count, UNRESOLVED, dtype=np.int8)
    phi_end = np.full(count, phi_max)
    # Rows with smaller steps (nearly radial rays) finish in fewer steps, so
    # the widest row bounds the step count.
    columns = int(math.ceil(phi_max / h.max())) + 2
    samples = np.full((count, columns), np.nan, dtype=np.float32) if store else None
    if store:
        samples[:, 0] = u
    active = np.arange(count)
    j = 0
    while active.size:
        j += 1
        hu = h[active]
        nu, nv = _rk4(u[active], v[active], hu)
        if store:
            samples[active, j] = nu
        u[active], v[active] = nu, nv
        phi = j * hu
        cap = nu >= HORIZON_U
        esc = (nu <= 0.0) & (nv < 0.0)
        # Root of u - target inside the last step (u is nearly linear there).
        prev = samples[active, j - 1].astype(np.float64) if store else None
        if prev is None:
            prev = nu - nv * hu
        for mask, target, label in ((cap, HORIZON_U, CAPTURED), (esc, 0.0, ESCAPED)):
            if mask.any():
                idx = active[mask]
                denom = nu[mask] - prev[mask]
                frac = np.where(np.abs(denom) > 0, (target - prev[mask]) / np.where(denom == 0, 1, denom), 1.0)
                phi_end[idx] = (j - 1 + np.clip(frac, 0, 1)) * hu[mask]
                outcome[idx] = label
        done = cap | esc | (phi + hu > phi_max) | (j + 1 >= columns)
        active = active[~done]
    return outcome, phi_end, samples


def deflection_from_infinity(b, step=0.002, phi_max=8 * math.pi):
    """Total bending of a ray from infinity with impact b (escaping rays only)."""
    b = np.atleast_1d(np.asarray(b, dtype=np.float64))
    outcome, phi_end, _ = integrate(np.zeros_like(b), 1.0 / b, np.full_like(b, step), phi_max)
    return np.where(outcome == ESCAPED, phi_end - math.pi, np.nan)


def critical_alpha(observer_radius):
    """Angular radius of the shadow for a static observer (alpha from the hole)."""
    r = float(observer_radius)
    return math.asin(B_CRIT * math.sqrt(1.0 - 2.0 / r) / r)


def dot(a, b):
    """Row-wise dot product (avoids spurious matmul FP warnings on Accelerate)."""
    return (np.asarray(a) * np.asarray(b)).sum(axis=-1)


def unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def view_direction(yaw_degrees, elevation_degrees):
    """View-frame direction (u=0.5 is yaw 0 = -Z, yaw grows toward +X, +Y up)."""
    yaw, el = math.radians(yaw_degrees), math.radians(elevation_degrees)
    return np.array([math.sin(yaw) * math.cos(el), math.sin(el), -math.cos(yaw) * math.cos(el)])


def tangent_basis(c):
    """(right, up) on the sky around direction c, right = c x +Y."""
    right = unit(np.cross(c, [0.0, 1.0, 0.0]))
    return right, np.cross(right, c)


class Disc:
    """Thin opaque disc through the hole between `inner` and `outer` radii (M).

    `inclination_degrees` is the angle between the disc normal and the
    direction from the hole to the observer (0 face-on, 90 edge-on);
    `roll_degrees` turns the normal about the line of sight from screen-up
    toward screen-right. `spin` = +1 rotates counter-clockwise seen from the
    normal's side, -1 the other way.
    """

    def __init__(self, c, inclination_degrees, roll_degrees=0.0, inner=6.0, outer=16.0, spin=1):
        right, up = tangent_basis(c)
        i, roll = math.radians(inclination_degrees), math.radians(roll_degrees)
        in_sky = math.cos(roll) * up + math.sin(roll) * right
        self.normal = unit(math.cos(i) * -np.asarray(c) + math.sin(i) * in_sky)
        a1 = right - np.dot(right, self.normal) * self.normal
        if np.linalg.norm(a1) < 1e-6:
            a1 = up - np.dot(up, self.normal) * self.normal
        self.axis1 = unit(a1)
        self.axis2 = np.cross(self.normal, self.axis1)
        self.inner, self.outer, self.spin = float(inner), float(outer), 1 if spin >= 0 else -1


class Lens:
    """Tabulated lens for one observer radius and hole direction."""

    def __init__(self, observer_radius, direction, rows=4000, step=0.002, phi_max=8 * math.pi):
        r_o = float(observer_radius)
        if r_o <= 3.0:
            raise ValueError("the observer must be outside the photon sphere")
        self.observer_radius = r_o
        self.redshift_observer = math.sqrt(1.0 - 2.0 / r_o)
        self.direction = unit(direction)
        self.alpha_crit = critical_alpha(r_o)
        half = rows // 2
        # Closer than ~1e-9 rad the rays need more than 8*pi to decide; they
        # stay UNRESOLVED and draw as shadow.
        near = 1e-9
        captured = self.alpha_crit - np.exp(np.linspace(math.log(self.alpha_crit - 1e-7), math.log(near), half))
        escaped = self.alpha_crit + np.exp(np.linspace(math.log(near), math.log(math.pi - 1e-7 - self.alpha_crit), rows - half))
        self.alphas = np.concatenate([captured, escaped])
        sin_a = np.sin(self.alphas)
        self.impact = r_o * sin_a / self.redshift_observer
        u0 = 1.0 / r_o
        v0 = np.cos(self.alphas) / self.impact
        # Nearly radial rays sweep little phi; shrink their step so du per step stays small.
        self.steps = step * np.minimum(1.0, self.impact / 2.0)
        self.outcome, self.phi_end, self.samples = integrate(
            np.full(rows, u0), v0, self.steps, phi_max, store=True)

    def _rows(self, alpha):
        fi = np.interp(alpha, self.alphas, np.arange(self.alphas.size, dtype=np.float64))
        i0 = np.clip(np.floor(fi).astype(np.int64), 0, self.alphas.size - 2)
        return i0, np.clip(fi - i0, 0.0, 1.0)

    def _u_at(self, row, phi):
        valid = phi < self.phi_end[row]
        pos = phi / self.steps[row]
        j0 = np.clip(np.floor(pos).astype(np.int64), 0, self.samples.shape[1] - 2)
        t = pos - j0
        a = self.samples[row, j0].astype(np.float64)
        b = self.samples[row, j0 + 1].astype(np.float64)
        u = a + (b - a) * t
        return np.where(valid & np.isfinite(u), u, np.nan)

    def trace(self, dirs, disc=None, crossings=6):
        """Trace View-frame unit directions (..., 3).

        Returns a dict of arrays shaped like dirs[..., 0]: `captured` (bool),
        `escape` (..., 3) celestial direction (NaN when captured), and with a
        disc `hit`, `radius`, `azimuth` (radians in the disc's axis1->axis2
        sense) and `g`.
        """
        dirs = np.asarray(dirs, dtype=np.float64)
        shape = dirs.shape[:-1]
        d = dirs.reshape(-1, 3)
        e1 = -self.direction
        cos_a = np.clip(dot(d, self.direction), -1.0, 1.0)
        alpha = np.arccos(cos_a)
        perp = d - dot(d, e1)[:, None] * e1
        norm = np.linalg.norm(perp, axis=1)
        fallback = tangent_basis(self.direction)[1]
        e2 = np.where(norm[:, None] > 1e-12, perp / np.maximum(norm, 1e-300)[:, None], fallback)
        i0, w = self._rows(alpha)
        i1 = i0 + 1
        below = alpha < self.alpha_crit
        resolved_escape = (self.outcome[i0] == ESCAPED) & (self.outcome[i1] == ESCAPED)
        escaped = ~below & resolved_escape
        phi_inf = (1 - w) * self.phi_end[i0] + w * self.phi_end[i1]
        escape = np.where(escaped[:, None],
                          np.cos(phi_inf)[:, None] * e1 + np.sin(phi_inf)[:, None] * e2, np.nan)
        result = {"captured": (~escaped).reshape(shape), "escape": escape.reshape(shape + (3,))}
        if disc is None:
            return result
        n = disc.normal
        phi0 = np.mod(np.arctan2(-dot(e1, n) * np.ones_like(alpha), dot(e2, n)), math.pi)
        phi0 = np.where(phi0 <= 1e-9, phi0 + math.pi, phi0)
        hit = np.zeros(alpha.shape, dtype=bool)
        radius = np.full(alpha.shape, np.nan)
        cross_phi = np.full(alpha.shape, np.nan)
        for k in range(crossings):
            phi = phi0 + k * math.pi
            ua, ub = self._u_at(i0, phi), self._u_at(i1, phi)
            both = np.isfinite(ua) & np.isfinite(ub)
            u = np.where(both, (1 - w) * ua + w * ub,
                         np.where(w < 0.5, ua, ub))
            r = 1.0 / u
            new = ~hit & np.isfinite(r) & (r >= disc.inner) & (r <= disc.outer)
            radius = np.where(new, r, radius)
            cross_phi = np.where(new, phi, cross_phi)
            hit |= new
        pos = radius[:, None] * (np.cos(cross_phi)[:, None] * e1 + np.sin(cross_phi)[:, None] * e2)
        azimuth = np.arctan2(dot(pos, disc.axis2), dot(pos, disc.axis1))
        b = self.observer_radius * np.sin(alpha) / self.redshift_observer
        lam = -b * dot(np.cross(e1, e2), n)  # the physical photon runs opposite to the traced ray
        omega = disc.spin * radius ** -1.5
        g = np.sqrt(1.0 - 3.0 / radius) / ((1.0 - omega * lam) * self.redshift_observer)
        result.update(hit=hit.reshape(shape), radius=radius.reshape(shape),
                      azimuth=np.where(hit, azimuth, np.nan).reshape(shape),
                      g=np.where(hit, g, np.nan).reshape(shape))
        return result


def equirect_directions(width, height, y0=0, y1=None, jitter=(0.5, 0.5)):
    """View-frame directions of equirect pixel centres (rows y0..y1)."""
    y1 = height if y1 is None else y1
    x = (np.arange(width) + jitter[0]) / width
    y = (np.arange(y0, y1) + jitter[1]) / height
    yaw = (x - 0.5) * 2 * math.pi
    pitch = (0.5 - y) * math.pi
    yaw, pitch = np.meshgrid(yaw, pitch)
    return np.stack([np.sin(yaw) * np.cos(pitch), np.sin(pitch), -np.cos(yaw) * np.cos(pitch)], axis=-1)


def direction_to_equirect(d):
    """Inverse of `equirect_directions`: (u, v) in [0,1) image space."""
    yaw = np.arctan2(d[..., 0], -d[..., 2])
    pitch = np.arcsin(np.clip(d[..., 1], -1, 1))
    return np.mod(yaw / (2 * math.pi) + 0.5, 1.0), 0.5 - pitch / math.pi


def gnomonic_directions(c, half_angle_degrees, size, jitter=(0.5, 0.5)):
    """Directions of a size x size map on the plane perpendicular to c.

    The map is what a flat quad facing the observer shows: texel (x, y) with
    x right and y down covers tan(half_angle) * [-1, 1]^2 of that plane.
    """
    right, up = tangent_basis(c)
    extent = math.tan(math.radians(half_angle_degrees))
    s = (2 * (np.arange(size) + np.asarray(jitter)[:, None]) / size - 1) * extent
    xs, ys = s[0], -s[1]
    gx, gy = np.meshgrid(xs, ys)
    return unit(c + gx[..., None] * right + gy[..., None] * up)
