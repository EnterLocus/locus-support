# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Physics and projection checks for black_hole_lens.py.

The reference numbers come from an independent radial quadrature: the shadow
half-angle for a static observer at 50 M, far-field deflection angles for
impact parameters 20-1000 M, and the capture threshold b = 3*sqrt(3) M.
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/black_hole
import black_hole_lens as L  # noqa: E402


def direct(lens, d, disc, step=0.0005):
    """One ray integrated on its own at a finer step: (escape dir | None, first hit radius | None)."""
    e1 = -lens.direction
    alpha = math.acos(float(np.clip(L.dot(d, lens.direction), -1, 1)))
    perp = d - L.dot(d, e1) * e1
    e2 = perp / np.linalg.norm(perp)
    b = lens.observer_radius * math.sin(alpha) / lens.redshift_observer
    outcome, phi_end, samples = L.integrate(
        np.array([1 / lens.observer_radius]), np.array([math.cos(alpha) / b]),
        np.array([step]), 8 * math.pi, store=True)
    escape = None
    if outcome[0] == L.ESCAPED:
        escape = math.cos(phi_end[0]) * e1 + math.sin(phi_end[0]) * e2
    n = disc.normal
    phi0 = math.atan2(-L.dot(e1, n), L.dot(e2, n)) % math.pi or math.pi
    for k in range(8):
        phi = phi0 + k * math.pi
        if phi >= phi_end[0]:
            break
        pos = phi / step
        j = int(pos)
        u = samples[0, j] + (samples[0, j + 1] - samples[0, j]) * (pos - j)
        if disc.inner <= 1 / u <= disc.outer:
            return escape, 1 / u
    return escape, None


class LensPhysicsTests(unittest.TestCase):
    def test_shadow_angle_for_static_observer(self):
        self.assertAlmostEqual(math.degrees(L.critical_alpha(50)), 5.844178294, places=8)

    def test_deflection_from_infinity_matches_reference_quadrature(self):
        # Values from an independent radial quadrature.
        got = L.deflection_from_infinity([20, 50, 100, 1000])
        want = [0.2361359954, 0.08508345038, 0.04122253975, 0.004011823810]
        np.testing.assert_allclose(got, want, atol=1e-9)

    def test_capture_threshold_is_three_root_three(self):
        lo, hi = 5.0, 5.4
        for _ in range(26):
            mid = (lo + hi) / 2
            outcome, _, _ = L.integrate(np.zeros(1), np.array([1 / mid]), np.array([0.004]), 12 * math.pi)
            lo, hi = (mid, hi) if outcome[0] == L.CAPTURED else (lo, mid)
        self.assertAlmostEqual(lo, L.B_CRIT, delta=1e-6)


class LensTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = L.view_direction(20, 10)
        cls.lens = L.Lens(40, cls.c, rows=3000)
        cls.disc = L.Disc(cls.c, 78, 10, 6, 16, 1)

    def test_shadow_edge(self):
        right, _ = L.tangent_basis(self.c)
        a = self.lens.alpha_crit
        dirs = np.array([math.cos(x) * self.c + math.sin(x) * right for x in (a - 1e-6, a + 1e-6)])
        captured = self.lens.trace(dirs)["captured"]
        self.assertEqual(captured.tolist(), [True, False])

    def test_table_matches_direct_integration(self):
        rng = np.random.default_rng(7)
        dirs = L.unit(self.c + rng.normal(0, 0.3, (60, 3)))
        traced = self.lens.trace(dirs, self.disc)
        compared_hits = 0
        for i, d in enumerate(dirs):
            alpha = math.acos(float(np.clip(L.dot(d, self.c), -1, 1)))
            if abs(alpha - self.lens.alpha_crit) < 1e-4:
                continue
            escape, radius = direct(self.lens, d, self.disc)
            self.assertEqual(escape is None, bool(traced["captured"][i]))
            if escape is not None:
                angle = math.acos(min(1.0, float(L.dot(escape, traced["escape"][i]))))
                # Linear interpolation between alpha rows (error ~ 1/rows^2);
                # 5e-5 rad is a tenth of a Vision Pro display pixel.
                self.assertLess(angle, 5e-5)
            self.assertEqual(radius is not None, bool(traced["hit"][i]))
            if radius is not None:
                compared_hits += 1
                self.assertAlmostEqual(traced["radius"][i], radius, delta=2e-3)
        self.assertGreater(compared_hits, 5)

    def test_approaching_side_is_blueshifted(self):
        c = L.view_direction(0, 0)
        lens = L.Lens(40, c, rows=2000)
        for spin in (1, -1):
            disc = L.Disc(c, 90, 0, 6, 16, spin)
            left, right = lens.trace(np.array([L.view_direction(-12, 0), L.view_direction(12, 0)]), disc)["g"]
            # Normal up, spin +1: counter-clockwise from above, so the -X side approaches.
            self.assertGreater(left if spin > 0 else right, 1.0)
            self.assertLess(right if spin > 0 else left, 1.0)


class ProjectionTests(unittest.TestCase):
    def test_equirect_round_trip_and_convention(self):
        d = L.equirect_directions(8, 4)
        u, v = L.direction_to_equirect(d)
        np.testing.assert_allclose(u, (np.arange(8) + 0.5)[None, :] / 8 * np.ones((4, 1)), atol=1e-12)
        np.testing.assert_allclose(v, (np.arange(4) + 0.5)[:, None] / 4 * np.ones((1, 8)), atol=1e-12)
        np.testing.assert_allclose(L.view_direction(0, 0), [0, 0, -1], atol=1e-12)
        np.testing.assert_allclose(L.view_direction(90, 0), [1, 0, 0], atol=1e-12)

    def test_gnomonic_map_centre_and_orientation(self):
        c = L.view_direction(0, 0)
        d = L.gnomonic_directions(c, 30, 3)
        np.testing.assert_allclose(d[1, 1], c, atol=1e-12)
        self.assertGreater(d[1, 2, 0], 0)   # x grows to the right (+X)
        self.assertGreater(d[0, 1, 1], 0)   # row 0 is the top


if __name__ == "__main__":
    unittest.main()
