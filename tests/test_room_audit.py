"""Exercise the optional author audit using real USD stages (pip install usd-core)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from pxr import Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("room_audit", ROOT / "tools/audit_locus_room.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RoomAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.model = self.root / "scene.usda"
        stage = Usd.Stage.CreateNew(str(self.model))
        UsdGeom.Xform.Define(stage, "/Room")
        UsdGeom.Mesh.Define(stage, "/Room/Lamp")
        stage.GetRootLayer().Save()
        self.metadata = {"formatVersion": 4, "lighting": {"luminaireGroups": [{
            "entities": ["Lamp"], "proxy": {"type": "spot", "anchorEntity": "Lamp"}
        }]}}

    def run_audit(self):
        path = self.root / "space.json"
        path.write_text(json.dumps(self.metadata))
        return module.audit(path, self.model)

    def test_legacy_downward_spot_and_v5_explicit_direction(self):
        self.assertEqual(self.run_audit()["directedSpots"], 0)
        self.metadata["formatVersion"] = 5
        with self.assertRaisesRegex(ValueError, "explicit direction"):
            self.run_audit()
        self.metadata["lighting"]["luminaireGroups"][0]["proxy"]["direction"] = [0, -1, 0]
        self.assertEqual(self.run_audit()["directedSpots"], 1)

    def test_baked_indirect_requires_a_real_exported_entity(self):
        self.metadata["lighting"]["bakedIndirect"] = {"entities": ["Missing"]}
        with self.assertRaisesRegex(ValueError, "Missing: expected one exported identity, found 0"):
            self.run_audit()
        self.metadata["lighting"]["bakedIndirect"]["entities"] = ["Lamp"]
        self.run_audit()


if __name__ == "__main__":
    unittest.main()
