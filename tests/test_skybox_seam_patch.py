# SPDX-License-Identifier: Apache-2.0
"""Local repair CLI: camera roundtrip, protected pixels, and source identity."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools/skybox/seam_patch.py"


class SeamPatchCliTests(unittest.TestCase):
    def call(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *map(str,args)],
                                capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_wrap_camera_roundtrip_and_larger_patch_preserve_canvas(self):
        with tempfile.TemporaryDirectory(prefix="seam-patch-") as tmp:
            p = Path(tmp)
            # Direction-coded sphere is continuous at ERP wrap and near poles.
            yaw = (np.arange(256)[None,:]+.5)/256*2*np.pi-np.pi
            polar = (np.arange(128)[:,None]+.5)/128*np.pi
            rgb = np.stack((np.sin(polar)*np.sin(yaw),
                            np.broadcast_to(np.cos(polar),(128,256)),
                            -np.sin(polar)*np.cos(yaw)),axis=-1)
            original = np.rint((rgb+1)*100+20).astype(np.uint8)
            Image.fromarray(original).save(p/"source.png")
            for pitch in [0, 85]:
                self.call("extract",p/"source.png",p/"patch.png",p/"camera.json",
                          "--yaw",180,"--pitch",pitch,"--size",96)
                # A different native returned grid must keep camera/FOV and ERP size.
                with Image.open(p/"patch.png") as patch:
                    patch.resize((128,128),Image.Resampling.BILINEAR).save(p/"returned.png")
                self.call("insert",p/"source.png",p/"returned.png",p/"camera.json",
                          p/"final.png",p/"mask.png")
                output=np.asarray(Image.open(p/"final.png"))
                mask=np.asarray(Image.open(p/"mask.png"))
                self.assertEqual(output.shape,original.shape)
                self.assertTrue(np.any(mask>0))
                self.assertTrue(np.array_equal(output[mask==0],original[mask==0]))
                self.assertLess(np.abs(output.astype(int)-original).max(),3)
                receipt=json.loads((p/"final.png.patch.json").read_text())
                self.assertTrue(receipt["outsideZeroAlphaUnchanged"])

    def test_modified_source_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="seam-patch-") as tmp:
            p=Path(tmp)
            Image.new("RGB",(128,64),(50,100,150)).save(p/"source.png")
            self.call("extract",p/"source.png",p/"patch.png",p/"camera.json","--yaw",135,"--size",32)
            Image.new("RGB",(128,64),(51,100,150)).save(p/"source.png")
            result=self.call("insert",p/"source.png",p/"patch.png",p/"camera.json",
                             p/"final.png",p/"mask.png",ok=False)
            self.assertIn("source hash changed",result.stderr)
            self.assertFalse((p/"final.png").exists())


if __name__=="__main__":
    unittest.main()
