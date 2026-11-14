# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

SCRIPT=Path(__file__).resolve().parents[1]/'tools/skybox/erp_context.py'


class ERPContextTests(unittest.TestCase):
    def test_cyclic_context_roundtrip_and_aspect_guard_through_cli(self):
        with tempfile.TemporaryDirectory(prefix='erp-context-') as folder:
            root=Path(folder)
            pixels=np.random.default_rng(7).integers(0,256,(54,108,3),dtype=np.uint8)
            Image.fromarray(pixels).save(root/'source.png')
            def run(command,*args):
                return subprocess.run([sys.executable,str(SCRIPT),command,*map(str,args)],capture_output=True,text=True)
            result=run('pad',root/'source.png',root/'padded.png','--metadata',root/'meta.json')
            self.assertEqual(result.returncode,0,result.stderr)
            meta=json.loads((root/'meta.json').read_text())
            rolled=np.roll(pixels,54,axis=1)
            with Image.open(root/'padded.png') as image:
                self.assertTrue(np.array_equal(np.asarray(image)[:,:meta['left']],rolled[:,-meta['left']:]))
            result=run('unpad',root/'padded.png',root/'out.png','--metadata',root/'meta.json')
            self.assertEqual(result.returncode,0,result.stderr)
            with Image.open(root/'out.png') as image:
                self.assertTrue(np.array_equal(np.asarray(image),pixels))
            with Image.open(root/'padded.png') as image:
                image.resize((160,54)).save(root/'drift.png')
            result=run('unpad',root/'drift.png',root/'bad.png','--metadata',root/'meta.json')
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'bad.png').exists())
