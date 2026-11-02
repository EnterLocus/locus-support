"""Shared source fixtures exercised through the public checker interface."""
import platform
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import check_room
import export_room_contract_fixtures
import room_contract_cases


@unittest.skipUnless(platform.system() == 'Darwin', 'macOS RealityKit required')
class SharedCheckerContract(unittest.TestCase):
    def test_generated_contract_cases(self):
        with tempfile.TemporaryDirectory(prefix='locus-shared-contract-') as directory:
            root = Path(directory)
            export_room_contract_fixtures.build(root)
            for case in room_contract_cases.CASES:
                for suffix in ('flat.zip', 'locusplace'):
                    with self.subTest(case=case.identifier, format=suffix):
                        report = check_room.check(root / (case.identifier + '.' + suffix), '1.4.5')
                        expected_error = case.importer_outcome == 'reject' or case.checker_e_code is not None
                        self.assertEqual(report['valid'], not expected_error, report)
                        if case.importer_outcome == 'reject':
                            self.assertNotIn('E', report['layers'], report)
                        if case.importer_outcome == 'accept' and case.checker_e_code is not None:
                            self.assertIn(case.checker_e_code, [e.get('code') for e in report['errors']], report)
