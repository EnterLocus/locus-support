# SPDX-License-Identifier: Apache-2.0
"""Real CLI behavior: reduce sky exposure wrap while protecting lower sphere."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"tools/skybox/sky_wrap_tone.py"


class SkyWrapToneTests(unittest.TestCase):
    def test_sky_boundary_balanced_and_ground_exact(self):
        with tempfile.TemporaryDirectory(prefix="sky-wrap-") as tmp:
            p=Path(tmp)
            a=np.full((128,256,3),[70,130,200],dtype=np.uint8)
            a[:64,:128]+=8
            a[:64,128:]-=8
            a[64:]=[210,180,120]
            Image.fromarray(a).save(p/"source.png")
            r=subprocess.run([sys.executable,str(CLI),str(p/"source.png"),
                              str(p/"out.png"),str(p/"mask.png")],
                             capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            result=np.asarray(Image.open(p/"out.png"))
            self.assertLessEqual(np.abs(result[:40,0].astype(int)-result[:40,-1]).max(),1)
            self.assertTrue(np.array_equal(result[64:],a[64:]))
            self.assertTrue(np.array_equal(result[:,64:192],a[:,64:192]))
            report=json.loads((p/"out.png.tone.json").read_text())
            self.assertTrue(report["groundUnchanged"])
            self.assertEqual(report["size"],[256,128])


if __name__=="__main__":
    unittest.main()
