# SPDX-License-Identifier: Apache-2.0
"""Optional real-Blender adapter/CLI check: BLENDER_BIN=/path/to/blender python3 -m unittest tests.test_coplanar_blender."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BLENDER = os.environ.get('BLENDER_BIN')
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(BLENDER, 'Set BLENDER_BIN to run the real Blender integration check')
class BlenderSurfaceAuditTests(unittest.TestCase):
    def test_source_export_transforms_units_and_incomplete_scope(self):
        with tempfile.TemporaryDirectory(prefix='surface-audit-', dir=os.environ.get('LOCUS_AUDIT_SCRATCH')) as folder:
            folder = Path(folder)
            setup = folder/'setup.py'
            # Two separate transformed meshes, 0.1 cm apart: source units and
            # exported metre geometry must both fall within the 2 mm threshold.
            setup.write_text('''import bpy, math
from pathlib import Path
bpy.ops.wm.read_factory_settings(use_empty=True)
p = Path(__file__).parent
bpy.context.scene.unit_settings.scale_length = .01
for name, z, faces in [('A',0,[(0,1,2)]),('B',.1,[(2,1,0)])]:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0,0,0),(100,0,0),(0,100,0)], [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (-50,30,z)
    obj.rotation_euler.z = .3
bpy.ops.wm.save_as_mainfile(filepath=str(p/'risk.blend'))
# Normalize the non-metre authoring scene before USD export. The USD
# exporter unit selector declares/scales stage units; it does not fix a
# source whose coordinates were authored in centimetres.
for obj in bpy.context.scene.objects:
    obj.location *= .01
    obj.scale *= .01
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.wm.usd_export(filepath=str(p/'risk.usdz'), convert_scene_units='CENTIMETERS')
collection = bpy.data.collections.new('Prototype')
prototype = bpy.data.objects['A'].copy()
collection.objects.link(prototype)
instancer = bpy.data.objects.new('Instancer', None)
instancer.instance_type = 'COLLECTION'
instancer.instance_collection = collection
bpy.context.collection.objects.link(instancer)
bpy.ops.wm.save_as_mainfile(filepath=str(p/'instanced.blend'))
''')
            base = [BLENDER, '--factory-startup', '-b', '--disable-autoexec', '-t', '1', '--python-exit-code', '2']
            result = subprocess.run(base+['--python', str(setup)], capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

            def run(source_args, audit_args):
                report = folder/'report.json'
                result = subprocess.run(base+source_args+['--python', str(ROOT/'tools/audit_coplanar_surfaces.py'), '--', '--json', str(report)]+audit_args, capture_output=True, text=True, timeout=90)
                self.assertTrue(report.exists(), result.stdout+result.stderr)
                data = json.loads(report.read_text())
                self.assertEqual(result.returncode, data['exitCode'], result.stdout+result.stderr)
                return data

            for source_args, audit_args in [([str(folder/'risk.blend')], []), ([], ['--usdz', str(folder/'risk.usdz')])]:
                r = run(source_args, audit_args)
                self.assertTrue(r['scopeComplete'], r)
                self.assertEqual(r['exitCode'], 1, r)
                self.assertAlmostEqual(r['findings'][0]['overlapAreaM2'], .5, places=4)
                self.assertEqual(r['findings'][0]['winding'], 'opposite')
            r = run([str(folder/'risk.blend')], ['--max-triangles', '1'])
            self.assertEqual(r['exitCode'], 2)
            self.assertFalse(r['scopeComplete'])
            self.assertEqual(r['skippedMeshes'][0]['object'], 'B')
            r = run([str(folder/'instanced.blend')], [])
            self.assertEqual(r['exitCode'], 2)
            self.assertTrue(any(row.get('instances',0) > 0 for row in r['skippedMeshes']), r)
            r = run([str(folder/'risk.blend')], ['--object', 'missing'])
            self.assertEqual(r['exitCode'], 2)
            self.assertIn('does not exist', r.get('error','').replace('Objects do not exist', 'Object does not exist'))


if __name__ == '__main__':
    unittest.main()
