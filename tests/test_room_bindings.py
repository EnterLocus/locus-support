import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import json
import io
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicRoomBindingTests(unittest.TestCase):
    def test_standalone_validator_rejects_nested_object_mesh_name_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            tool = root / "validate_locus_asset.py"
            shutil.copyfile(ROOT / "tools/validate_locus_asset.py", tool)
            with zipfile.ZipFile(ROOT / "examples/atrium-loft-room.zip") as source:
                files = {name: source.read(name) for name in source.namelist()}
            manifest = json.loads(files["space.json"])
            manifest["formatVersion"] = 5
            for key in ["spatialAdaptation", "lighting", "ambientAnimations"]:
                manifest.pop(key, None)
            manifest["rendering"] = {"softenedReflectionEntities": [], "uiFadeEntities": ["Cup"]}
            files["space.json"] = json.dumps(manifest).encode()
            usda = b'''#usda 1.0
(defaultPrim = "Root"
 upAxis = "Y"
 metersPerUnit = 1)
def Xform "Root" {
 def Xform "Cup" {
  def Cube "Cup" {
   double size = 1
  }
 }
}
'''
            model = io.BytesIO()
            with zipfile.ZipFile(model, "w") as output:
                info = zipfile.ZipInfo("root.usda")
                info.extra = struct.pack("<HH", 0xFFFF, 21) + bytes(21)
                output.writestr(info, usda)
            files["scene.usdz"] = model.getvalue()
            archive = root / "duplicate.zip"
            with zipfile.ZipFile(archive, "w") as output:
                for name, data in files.items():
                    output.writestr(name, data)
            result = subprocess.run([sys.executable, str(tool), str(archive)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("Cup", result.stderr)
            self.assertIn("not uniquely named", result.stderr)

    def test_standalone_download_rejects_missing_reference_and_packer_leaves_no_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            for tool in ["validate_locus_asset.py", "pack_locus_asset.py"]:
                shutil.copyfile(ROOT / "tools" / tool, root / tool)
            source = root / "room"
            source.mkdir()
            with zipfile.ZipFile(ROOT / "examples/atrium-loft-room.zip") as archive:
                archive.extractall(source)
            manifest = json.loads((source / "space.json").read_text())
            manifest["formatVersion"] = 5
            manifest["rendering"] = {"softenedReflectionEntities": [], "uiFadeEntities": ["Missing_Model_Entity"]}
            (source / "space.json").write_text(json.dumps(manifest))
            output = root / "rejected.zip"
            result = subprocess.run([sys.executable, str(root / "pack_locus_asset.py"), str(source), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("Missing_Model_Entity", result.stderr)
            self.assertIn("was not found", result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(list(root.glob(".*.packing-*")))


if __name__ == "__main__":
    unittest.main()
