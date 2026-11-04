# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('coplanar', Path(__file__).resolve().parents[1]/'tools/audit_coplanar_surfaces.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def triangle(name, face, points):
    return {'object': name, 'face': face, 'vertices': points}


class CoplanarSurfaceTests(unittest.TestCase):
    def test_opposite_faces_inside_one_mesh_are_found(self):
        v = [(0,0,0),(1,0,0),(0,1,0)]
        r = audit.audit_triangles([triangle('lamp',0,v),triangle('lamp',1,v[::-1])])
        self.assertTrue(r['scopeComplete'])
        self.assertEqual(r['findingCount'],1)
        self.assertEqual(r['findings'][0]['winding'],'opposite')
        self.assertAlmostEqual(r['findings'][0]['overlapAreaM2'],.5)

    def test_adjacent_tiles_touching_only_at_edge_are_not_overlaps(self):
        r = audit.audit_triangles([triangle('a',0,[(0,0,0),(1,0,0),(0,1,0)]),triangle('b',0,[(1,0,0),(1,1,0),(0,1,0)])])
        self.assertEqual(r['findingCount'],0)

    def test_parallel_gap_threshold_and_nested_overlap(self):
        for gap, expected in [(.001,1),(.01,0)]:
            r = audit.audit_triangles([triangle('large',0,[(0,0,0),(2,0,0),(0,2,0)]),triangle('small',0,[(.2,.2,gap),(.4,.2,gap),(.2,.4,gap)])])
            self.assertEqual(r['findingCount'],expected)

    def test_crossing_nonparallel_surfaces_are_not_z_fighting(self):
        r = audit.audit_triangles([triangle('floor',0,[(0,0,0),(1,0,0),(0,1,0)]),triangle('wall',0,[(.3,0,-1),(.3,1,0),(.3,0,1)])])
        self.assertEqual(r['findingCount'],0)

    def test_same_polygon_triangulation_is_not_duplicate(self):
        v = [(0,0,0),(1,0,0),(0,1,0)]
        self.assertEqual(audit.audit_triangles([triangle('a',1,v),triangle('a',1,v)])['findingCount'],0)

    def test_bucket_boundaries_and_negative_coordinates(self):
        v = [(-2,-3,-4),(-1,-3,-4),(-2,-2,-4)]
        b = [(x,y,z+.001) for x,y,z in v[::-1]]
        self.assertEqual(audit.audit_triangles([triangle('a',0,v),triangle('b',0,b)])['findingCount'],1)

    def test_skips_and_pair_limit_never_report_complete(self):
        v = [(0,0,0),(1,0,0),(0,1,0)]
        r = audit.audit_triangles([triangle(str(i),0,v) for i in range(3)],max_pairs=1)
        self.assertFalse(r['scopeComplete'])
        self.assertTrue(r['pairLimitReached'])
        r = audit.audit_triangles([triangle('a',0,v)],skipped=[{'object':'dense'}])
        self.assertFalse(r['scopeComplete'])

    def test_non_finite_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            audit.audit_triangles([triangle('a',0,[(0,0,0),(1,0,0),(0,float('nan'),0)])])


if __name__ == '__main__':
    unittest.main()
