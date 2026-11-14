"""Reconcile published usage calculations without claiming provider invoices."""
from decimal import Decimal
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MILLION = Decimal(1000000)


class SkyboxCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.usage = json.loads((ROOT / 'examples/skybox-comparison/usage.json').read_text(),
                              parse_float=Decimal)
        cls.comparison = json.loads((ROOT / 'examples/skybox-comparison/comparison.json').read_text(),
                                   parse_float=Decimal)

    def test_authorization_cohorts_preserve_original_and_separate_trial(self):
        counts = {}
        for request in self.usage['requests']:
            cohort = request['approval_cohort']
            counts[cohort] = counts.get(cohort, 0) + 1
            self.assertFalse(request['invoice_verified'])
        self.assertEqual(counts, {'original_two_models_20261113': 18, 'nano21_20261114': 9})
        self.assertEqual(sum(counts.values()), self.usage['paid_output_count'])
        self.assertEqual(sum(counts.values()), self.comparison['paid_outputs_all_cohorts'])
        self.assertEqual(self.usage['cohorts']['original_two_models_20261113']
                         ['creator_authorized_combined_cap_usd'], 5)
        self.assertEqual(self.usage['cohorts']['nano21_20261114']['creator_authorized_cap_usd'], 2)
        self.assertEqual(self.comparison['accounting']['paid_outputs'], 18)
        self.assertEqual(self.comparison['accounting']['creator_combined_cap_usd'], 5)
        self.assertFalse(self.comparison['model_default_changed'])
        self.assertFalse(self.usage['provider_invoice_verified'])

    def test_nano21_costs_reconcile_from_modality_and_thinking_counters(self):
        requests = [r for r in self.usage['requests'] if r['route'] == 'nano_banana_2_1']
        self.assertEqual({r['stage'] for r in requests},
                         {'G', 'F-px', 'F-nx', 'F-py', 'F-ny', 'F-pz', 'F-nz', 'R1', 'R2'})
        self.assertEqual(len({r['id'] for r in requests}), 9)
        totals = dict.fromkeys(['known_classified_usd', 'if_residual_text_rate_usd',
                               'conservative_accounted_usd'], Decimal(0))
        images = Decimal(0)
        residual_total = 0
        for request in requests:
            self.assertEqual(request['mode'], 'Standard')
            self.assertEqual(request['api_model'], 'gemini-nano-banana-2.1')
            usage = request['usage']
            self.assertEqual(sum(d['tokenCount'] for d in usage['promptTokensDetails']),
                             usage['promptTokenCount'])
            image = sum(d['tokenCount'] for d in usage['candidatesTokensDetails']
                        if d['modality'] == 'IMAGE')
            text = sum(d['tokenCount'] for d in usage['candidatesTokensDetails']
                       if d['modality'] == 'TEXT')
            residual = usage['candidatesTokenCount'] - image - text
            self.assertGreaterEqual(residual, 0)
            self.assertEqual(image, 3780)
            self.assertEqual(usage['totalTokenCount'], usage['promptTokenCount'] +
                             usage['candidatesTokenCount'] + usage['thoughtsTokenCount'])
            known = (Decimal('1.5') * usage['promptTokenCount'] + 30 * image +
                     Decimal('7.5') * (text + usage['thoughtsTokenCount'])) / MILLION
            expected = {'known_classified_usd': known,
                        'if_residual_text_rate_usd': known + Decimal('7.5') * residual / MILLION,
                        'conservative_accounted_usd': known + 30 * residual / MILLION}
            for key, value in expected.items():
                self.assertAlmostEqual(request['cost_accounting'][key], value, places=10)
                totals[key] += value
            self.assertEqual(request['cost_accounting']['unclassified_candidate_tokens'], residual)
            images += 30 * image / MILLION
            residual_total += residual
        self.assertEqual(images, Decimal('1.0206'))
        self.assertEqual(residual_total, 3992)
        self.assertEqual(totals, {'known_classified_usd': Decimal('1.0643055'),
                                 'if_residual_text_rate_usd': Decimal('1.0942455'),
                                 'conservative_accounted_usd': Decimal('1.1840655')})
        route = self.comparison['routes']['nano_banana_2_1']
        self.assertEqual(route['output_fee_subtotal_usd'], images)
        self.assertEqual(route['known_classified_usd'], totals['known_classified_usd'])
        self.assertEqual(route['usage_price_if_residual_text_usd'], totals['if_residual_text_rate_usd'])
        self.assertEqual(route['conservative_accounted_usd'], totals['conservative_accounted_usd'])
        cohort = self.usage['cohorts']['nano21_20261114']
        self.assertEqual(cohort['conservative_accounted_usd'], totals['conservative_accounted_usd'])
        self.assertLess(totals['conservative_accounted_usd'], cohort['creator_authorized_cap_usd'])
        self.assertFalse(route['batch']['generation_tested'])
        self.assertEqual(route['owner_headset_review'], 'PENDING')

    def test_nano21_modeled_batch_schedule_uses_discount_only_on_six_faces(self):
        standard = Decimal(3780) * 30 / MILLION
        batch = standard / 2
        self.assertEqual(standard, Decimal('0.1134'))
        self.assertEqual(batch, Decimal('0.0567'))
        for repairs in range(3):
            actual_schedule = (7 + repairs) * standard
            modeled_schedule = (1 + repairs) * standard + 6 * batch
            self.assertEqual(actual_schedule, Decimal('0.7938') + repairs * Decimal('0.1134'))
            self.assertEqual(modeled_schedule, Decimal('0.4536') + repairs * Decimal('0.1134'))
            self.assertEqual(actual_schedule - modeled_schedule, Decimal('0.3402'))

    def test_public_receipts_do_not_copy_machine_paths_or_provider_response_ids(self):
        serialized = (ROOT / 'examples/skybox-comparison/usage.json').read_text()
        for private in ['/Users/', '/Volumes/', 'responseId', 'request_sha256', 'GEMINI_API_KEY=']:
            self.assertNotIn(private, serialized)
        for request in self.usage['requests']:
            self.assertFalse(request.get('invoice_verified'))


if __name__ == '__main__':
    unittest.main()
