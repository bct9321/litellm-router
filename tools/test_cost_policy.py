import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from router.cost_policy import Candidate, choose, request_charge
from router.spend_ledger import Ledger, BudgetDenied
from router.cost_policy import validate_policy


LIMITS = {'daily': 100, 'monthly': 100, 'request': 80, 'models': {'paid': {'daily': 100, 'monthly': 100}}}


BOUND = {'kind':'loopback-fixed-bound','canonical':'paid','origin':'http://127.0.0.1:1',
         'path':'/v1/chat/completions','valid_from':'2020-01-01T00:00:00+00:00',
         'expires_at':'2099-01-01T00:00:00+00:00','revision':'fixture-v1','evidence_ref':'fixture',
         'supported_surfaces':['text-chat'],'final_usage_rule':'complete-response-cost'}


class PolicyTests(unittest.TestCase):
    def test_request_charge_uses_full_request_and_output_ceiling(self):
        contract = dict(BOUND, input_nanos_per_token=2, output_nanos_per_token=3,
                        fixed_overhead_nanos=7, max_output_tokens=10)
        small = request_charge(contract, {'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 2})
        tool = request_charge(contract, {'messages': [{'role': 'user', 'content': 'x'}],
                                         'tools': [{'type': 'function', 'function': {'name': 'long', 'parameters': {'description': 'z' * 300}}}],
                                         'max_tokens': 2})
        longer_output = request_charge(contract, {'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 5})
        self.assertGreater(tool[0], small[0])
        self.assertGreater(longer_output[0], small[0])
        self.assertEqual(small[1] - small[0], 7)
        with self.assertRaises(BudgetDenied):
            request_charge(contract, {'messages': [], 'max_tokens': 11})
        with self.assertRaises(BudgetDenied):
            request_charge(contract, {'messages': [], 'max_tokens': 2, 'n': 2})

    def test_policy_rejects_missing_contract_price_or_model_limit(self):
        policy = {'ledger': 'x.sqlite', 'limits': LIMITS, 'routes': {'jev': {'candidates': [
                    {'alias': 'GENERAL_EFFICIENT', 'canonical': 'paid', 'capabilities': [], 'free': False,
                     'deployment_ids':['dep'], 'contract':'fixture'}]}},
                  'deployments': {'dep': {'alias':'fixture','provider_model':'provider','contract':'fixture',
                                         'capabilities':[], 'free':False}},
                  'contracts': {'fixture': dict(BOUND, input_nanos_per_token=1, output_nanos_per_token=1,
                                                max_output_tokens=2)}}
        validate_policy(policy)
        del policy['contracts']['fixture']['output_nanos_per_token']
        with self.assertRaises(ValueError):
            validate_policy(policy)
        policy['contracts']['fixture']['output_nanos_per_token'] = 1
        del policy['deployments']['dep']['alias']
        with self.assertRaises(ValueError):
            validate_policy(policy)
        policy['deployments']['dep']['alias'] = 'fixture'
        del policy['routes']
        with self.assertRaises(ValueError):
            validate_policy(policy)

    def test_free_first_capability_and_unknown_price_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(str(Path(folder) / 'ledger.sqlite'), LIMITS)
            free = Candidate('free', 'unused', frozenset({'vision'}), True, None, None)
            paid = Candidate('paid', 'paid', frozenset({'vision'}), False, 20, 40)
            unknown = Candidate('unknown', 'paid', frozenset({'vision'}), False, None, None)
            self.assertEqual(choose([paid, free], {'vision'}, ledger.report()).alias, 'free')
            self.assertEqual(choose([unknown, paid], {'vision'}, ledger.report()).alias, 'paid')
            with self.assertRaises(BudgetDenied):
                choose([unknown], {'vision'}, ledger.report())

    def test_paid_candidate_respects_overall_capacity(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = Ledger(str(Path(folder) / 'ledger.sqlite'), LIMITS)
            ledger.reserve('held', 'other', 'paid', 'alias', 'deployment', 70)
            candidate = Candidate('paid', 'paid', frozenset({'general'}), False, 20, 40)
            with self.assertRaises(BudgetDenied):
                choose([candidate], {'general'}, ledger.report())

    def test_report_and_history_import_are_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); config = root / 'config.json'; activity = root / 'activity.json'
            config.write_text(json.dumps({'ledger': str(root / 'ledger.sqlite'), 'limits': LIMITS}))
            activity.write_text(json.dumps({'data': [{'date':'2026-09-20','model':'provider/model','usage':0.00000002,'requests':2,'endpoint_id':'ep'}]}))
            command = [sys.executable, 'tools/cost_report.py', '--config', str(config), '--openrouter-activity', str(activity)]
            first = json.loads(subprocess.check_output(command, cwd=Path(__file__).resolve().parents[1], text=True))
            second = json.loads(subprocess.check_output(command, cwd=Path(__file__).resolve().parents[1], text=True))
            third = json.loads(subprocess.check_output(command + ['--source', 'renamed-source'], cwd=Path(__file__).resolve().parents[1], text=True))
            self.assertEqual(len(first['historical_imports']), 1)
            self.assertEqual(first['historical_imports'], second['historical_imports'])
            self.assertEqual(first['historical_imports'], third['historical_imports'])
            self.assertEqual(first['historical_models']['provider/model']['month']['provider_reported'], 20)
            self.assertEqual(first['historical_models']['provider/model']['month']['requests'], 2)
            self.assertEqual(first['overall']['today']['estimated'], 0)


if __name__ == '__main__':
    unittest.main()
