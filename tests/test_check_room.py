"""Source-generated entry-condition regressions, using actual macOS RealityKit."""
import json
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.room_fixtures import Room

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(platform.system() == 'Darwin', 'macOS RealityKit required')
class EntryConditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='locus-entry-tests-')
        cls.root = Path(cls.temporary.name)
        cls.build = cls.root / 'build'
        subprocess.run(['xcrun', '--sdk', 'macosx', 'swift', 'build', '--package-path',
                        str(ROOT / 'tools/locus-room-check'), '--scratch-path', str(cls.build)],
                       check=True, capture_output=True, timeout=300)
        cls.binary = cls.build / 'debug/locus-room-check'

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def check(self, room):
        model = self.root / 'scene.usdz'
        space = self.root / 'space.json'
        seats = self.root / 'seats.json'
        model.write_bytes(room.usdz())
        space.write_text(json.dumps(room.space))
        seats.write_text(json.dumps(room.seats))
        process = subprocess.run([str(self.binary), str(model), str(space), str(seats)],
                                 capture_output=True, text=True, timeout=60)
        report = json.loads(process.stdout.strip().splitlines()[-1])
        self.assertEqual(process.returncode, 1 if report['errors'] else 0)
        return report

    def assert_code(self, room, code):
        self.assertIn(code, [e['code'] for e in self.check(room)['errors']])

    def test_valid_minimal_room(self):
        result = self.check(Room())
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['seats']), 1)
        self.assertAlmostEqual(result['seats'][0]['eye'][1], 1.2, places=4)

    def test_tilted_seated_origin(self):
        r = Room()
        r.space['seatedOrigin']['orientationXYZW'] = [0.1, 0, 0, 0.995]
        self.assert_code(r, 'seatedOrigin')

    def test_zero_quaternion(self):
        r = Room()
        r.space['seatedOrigin']['orientationXYZW'] = [0, 0, 0, 0]
        self.assert_code(r, 'seatedOrigin')

    def test_non_emissive_fixture(self):
        r = Room()
        r.materials['Lamp_Glow'] = ((1, .64, .3), .5, None, 1)
        self.assert_code(r, 'entityHasNoPositiveEmissive')

    def test_missing_animation(self):
        r = Room()
        r.space['ambientAnimations'] = [{'entityName': 'Pendant_Glow', 'animationName': 'Missing'}]
        self.assert_code(r, 'missingAnimation')

    def test_desktop_outside_hide_group(self):
        r = Room()
        r.space['spatialAdaptation']['deskGroupEntitiesByTeleportID'] = {'seat.primary': 'Chair_Seat'}
        self.assert_code(r, 'deskGroupSurfaceMismatch')

    def test_flat_desktop(self):
        r = Room()
        r.box('Table_Top')['size'] = (1.5, 0, .7)
        self.assert_code(r, 'deskBounds')

    def test_degenerate_model(self):
        r = Room()
        r.boxes = [r.box('Floor')]
        r.boxes[0]['size'] = (0, 0, 0)
        self.assert_code(r, 'invalidModelBounds')

    def test_outlying_mesh_warns_without_failing(self):
        r = Room()
        r.boxes.append({'name': 'StrayMesh', 'center': (100, 1, 0), 'size': (.1, .1, .1), 'material': 'Warm_Wood'})
        report = self.check(r)
        self.assertEqual(report['errors'], [])
        self.assertIn('boundsPollution', [w['code'] for w in report['warnings']])

    def test_embedded_backdrop_warns_once_per_root_entity(self):
        self.assertNotIn('embeddedBackdrop', [w['code'] for w in self.check(Room())['warnings']])
        r = Room()
        r.boxes.append({'name': 'Alpine_Window_Backdrop_1', 'center': (0, 1.4, -3.5),
                        'size': (3.5, 2.4, .05), 'material': 'Lamp_Glow'})
        report = self.check(r)
        self.assertEqual(report['errors'], [])
        backdrop_warnings = [w for w in report['warnings'] if w['code'] == 'embeddedBackdrop']
        self.assertEqual(len(backdrop_warnings), 1)
        self.assertIn('Alpine_Window_Backdrop_1', backdrop_warnings[0]['message'])

    def test_no_seats(self):
        r = Room()
        r.seats = []
        self.assert_code(r, 'missingTeleportPoints')

    def test_illuminated_transparency(self):
        r = Room()
        r.materials['Lamp_Glow'] = ((1, .64, .3), .5, (1, .64, .3), .5)
        r.space['lighting']['luminaireGroups'][0]['illuminatedEntities'] = ['Pendant_Glow']
        self.assert_code(r, 'nonOpaqueEmission')


class CommandInterface(unittest.TestCase):
    def test_requires_installed_version(self):
        result = subprocess.run(['python3', str(ROOT / 'tools/check_room.py'), 'room.zip'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--current-app-version', result.stderr)
