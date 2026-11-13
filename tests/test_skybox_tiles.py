# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/skybox/tiles.py'


class TileCLITests(unittest.TestCase):
    def test_overlap_roundtrip_and_explicit_normalization(self):
        with tempfile.TemporaryDirectory(prefix='skybox-tiles-') as folder:
            root = Path(folder)
            pixels = np.random.default_rng(42).integers(0, 256, (83, 83, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(root/'in.png')
            def run(*args):
                return subprocess.run([sys.executable, str(SCRIPT)]+list(map(str,args)),capture_output=True,text=True)
            result = run('split',root/'in.png',root/'tiles','--grid',4,'--context',3)
            self.assertEqual(result.returncode,0,result.stderr)
            result = run('join',root/'tiles',root/'out.png')
            self.assertEqual(result.returncode,0,result.stderr)
            with Image.open(root/'out.png') as image:
                self.assertTrue(np.array_equal(pixels,np.asarray(image)))
            tile = root/'tiles/r0-c0.png'
            with Image.open(tile) as image:
                image.resize((32,32)).save(root/'resized.png')
            tile.write_bytes((root/'resized.png').read_bytes())
            self.assertNotEqual(run('join',root/'tiles',root/'out.png').returncode,0)
            result=run('join',root/'tiles',root/'out.png','--normalize-tiles')
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads((root/'out.png.tiles.json').read_text())
            self.assertEqual(data['tiles'][0]['nativeSide'],32)
            tile.unlink()
            self.assertNotEqual(run('join',root/'tiles',root/'out.png').returncode,0)
