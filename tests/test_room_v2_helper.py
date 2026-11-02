"""Public Package v2 Room-seat helper contracts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".agents/skills/build-original-locus-room/scripts/locus_room_v2.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("locus_room_v2", HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RoomV2HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = load_helper()

    def write_json(self, directory, name, value):
        path = directory / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_seats_derive_package_v2_anchors_from_saved_export_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bounds = self.write_json(root, "bounds.json", {
                "min": [10, 2, -4], "max": [30, 8, 16],
            })
            seats = self.write_json(root, "seats.json", {"seats": [{
                "id": "window-seat", "title": "Window Seat", "floor": [15, 2.5, 6],
                "eyeHeight": 1.15, "lookAt": [15, 2.5, -4],
            }]})
            output = root / "teleports.json"
            result = subprocess.run([
                sys.executable, str(HELPER), "seats", "--bounds-json", str(bounds),
                "--seats", str(seats), "--house-id", "space.example-room", "--output", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text()), {"houses": {"space.example-room": [{
                "id": "window-seat", "title": "Window Seat", "anchorXZ": [0.25, 0.5],
                "sourceFloorOffset": 0.5, "eyeHeight": 1.15, "yawRadians": 0.0,
            }]}})

    def test_blender_input_frame_and_eye_points_are_converted_before_normalizing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bounds = self.write_json(root, "bounds.json", {"min": [0, 0, 0], "max": [10, 8, 20]})
            seats = self.write_json(root, "seats.json", {"seats": [{
                "id": "desk", "title": "Desk", "floor": [5, -10, 1], "eyeHeight": 1.2,
                "facing": [0, 1, 0],
            }]})
            output = root / "teleports.json"
            command = [sys.executable, str(HELPER), "seats", "--bounds-json", str(bounds),
                       "--seats", str(seats), "--house-id", "space.example-room", "--frame", "blender",
                       "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True, text=True).returncode, 0)
            eyes = subprocess.run([
                sys.executable, str(HELPER), "eye-points", "--bounds-json", str(bounds),
                "--teleports", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(eyes.returncode, 0, eyes.stderr)
            self.assertEqual(json.loads(eyes.stdout)[0]["eye"], [5.0, 2.2, 10.0])
            self.assertEqual(json.loads(eyes.stdout)[0]["facing"], [0.0, 0.0, -1.0])

    def test_legacy_points_conversion_is_lossless_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            points = [{"id": "seat.one", "title": "One", "anchorXZ": [0.5, 0.5],
                       "sourceFloorOffset": 0, "eyeHeight": 1.1, "yawRadians": 0}]
            source = self.write_json(root, "flat.json", {"formatVersion": 1, "points": points})
            output = root / "teleports.json"
            command = [sys.executable, str(HELPER), "convert-points", str(source),
                       "--house-id", "space.example-room", "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(output.read_text()), {"houses": {"space.example-room": points}})
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertIn("refusing to overwrite", second.stderr)

    def test_rejects_out_of_bounds_and_ambiguous_seat_data(self):
        bounds = ((0.0, 0.0, 0.0), (1.0, 2.0, 1.0))
        with self.assertRaisesRegex(self.helper.HelperError, "outside"):
            self.helper.seat_record({"id": "outside", "title": "Outside", "floor": [2, 0, 0],
                                     "eyeHeight": 1, "yawRadians": 0}, 0, bounds, "usd")
        with self.assertRaisesRegex(self.helper.HelperError, "exactly one"):
            self.helper.seat_record({"id": "ambiguous", "title": "Ambiguous", "floor": [0, 0, 0],
                                     "eye": [0, 1, 0], "eyeHeight": 1, "yawRadians": 0}, 0, bounds, "usd")


if __name__ == "__main__":
    unittest.main()
