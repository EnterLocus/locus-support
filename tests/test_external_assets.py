import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('external_assets', ROOT / 'tools/external_assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class ExternalAssetsTests(unittest.TestCase):
    def record(self, data=b'fixture'):
        return {'path': 'examples/fixture.zip', 'url': 'https://example.test/fixture.zip',
                'byteCount': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def test_hydrate_uses_only_hash_verified_ignored_cache(self):
        data = b'fixture'
        record = self.record(data)
        with tempfile.TemporaryDirectory() as directory:
            target = assets.hydrate(record['path'], Path(directory), {record['path']: record},
                                    downloader=lambda _: data)
            self.assertEqual(target.parent, Path(directory))
            self.assertEqual(target.read_bytes(), data)
            self.assertIn(record['sha256'], target.name)

    def test_hydrate_rejects_wrong_download_hash_and_leaves_no_fixture(self):
        record = self.record()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                assets.hydrate(record['path'], Path(directory), {record['path']: record},
                               downloader=lambda _: b'changed')
            self.assertFalse(list(Path(directory).iterdir()))

    def test_verify_mode_bypasses_a_valid_cache_for_a_fresh_readback(self):
        data = b'fixture'
        record = self.record(data)
        with tempfile.TemporaryDirectory() as directory:
            assets.hydrate(record['path'], Path(directory), {record['path']: record},
                           downloader=lambda _: data)
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                assets.hydrate(record['path'], Path(directory), {record['path']: record},
                               downloader=lambda _: b'changed', use_cache=False)

    def test_manifest_covers_external_gallery_promo_and_download_contracts(self):
        manifest = assets.load_manifest()
        gallery = [item for path, item in manifest.items() if path.startswith('assets/gallery/')]
        promo = [item for path, item in manifest.items() if path.startswith('assets/promo/')]
        examples = [item for path, item in manifest.items() if path.startswith('examples/')]
        self.assertEqual(len(gallery), 327)
        self.assertEqual(len(promo), 5)
        self.assertEqual(len(examples), 5)
        self.assertTrue(all(item['url'] == 'https://media.enterlocus.net/gallery/' + Path(item['path']).name
                            for item in gallery))
        self.assertTrue(all(item['url'] == 'https://media.enterlocus.net/promo/' + Path(item['path']).name
                            for item in promo))
        release = 'https://github.com/EnterLocus/locus-support/releases/download/site-downloads-2026-11-05/'
        self.assertTrue(all(item['url'] == release + Path(item['path']).name for item in examples))
        legacy = {path: item for path, item in manifest.items() if path.startswith('legacy-examples/')}
        self.assertEqual({path: (item['byteCount'], item['sha256']) for path, item in legacy.items()}, {
            'legacy-examples/atrium-loft-room.zip': (8176551, '588c14c5b1226ec677fada112df1346bb105f0cbdb0344db9d1e1be03b3b9ff1'),
            'legacy-examples/courtyard-gallery-room.zip': (8510411, '1d4be79f0c69c6d34e285729c02bd1870bf11133497277a1f1d94d7b0dd9f21f'),
            'legacy-examples/horizon-atelier-room.zip': (8644903, 'dd3551316cae67c01a114a6130db37823f03dcebcec703f15a8fedf7dc291fe7'),
        })


if __name__ == '__main__':
    unittest.main()
