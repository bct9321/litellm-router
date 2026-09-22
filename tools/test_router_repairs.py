"""Focused public-seam regressions; fake HTTP only, no account credentials."""
import asyncio
import importlib.util
import json
import tempfile
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['OPENROUTER_API_KEY'] = 'local-test-only'
os.environ['LITELLM_API_KEY'] = 'local-test-only'
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(Path(__file__).resolve().parents[1] / 'outputs/token-cache')
os.environ['DISCOVERY_OUTPUT_DIR'] = str(Path(__file__).resolve().parents[1] / 'outputs/test-discovery')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from router.jev_classifier import OpenRouterJevClassifier


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class BenchmarkTests(unittest.TestCase):
    def test_paid_discovery_requires_complete_pricing(self):
        discovery = load_tool('discover-free-models')
        summary = {'id': 'fake', 'variant': 'paid', 'status': 'AVAILABLE',
                   'performance': {'success_rate': 1, 'p95': 0.1}, 'context_length': 2000000,
                   'capabilities': {name: {'pass': True} for name in ('fast', 'format', 'json', 'reasoning', 'tools', 'coding', 'vision', 'compression')},
                   'supported_parameters': ['tools'], 'architecture': {'input_modalities': ['text','image']},
                   'pricing_per_million': {}}
        score = discovery.score_for_tier(next(iter(discovery.TIERS.values())), summary, {})
        self.assertFalse(score['eligible'])
        self.assertTrue(any('price' in reason for reason in score['reasons']))
    def test_jev_benchmark_calls_production_payload(self):
        benchmark = load_tool('benchmark-classifiers')
        seen = []
        def upstream(request):
            import json
            payload = json.loads(request.content)
            seen.append(payload)
            return httpx.Response(200, json={'answers': {'tier': {'choice': 'CODING_EFFICIENT'}}, 'usage': {'cost': 0.001}})
        real_client = httpx.AsyncClient
        with patch('router.jev_classifier.httpx.AsyncClient',
                   side_effect=lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw)), \
             httpx.Client(transport=httpx.MockTransport(upstream)) as client:
            result = benchmark.classify_jev(client, benchmark.TESTS[0])
        self.assertIn('tier', seen[0]['questions'])
        self.assertIn('records', seen[0]['state'])
        self.assertEqual(result['cost'], 0.001)
    def test_http_error_charge_is_retained(self):
        benchmark = load_tool('benchmark-classifiers')
        def upstream(request):
            return httpx.Response(429, json={'usage': {'cost': 0.5}})
        with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
            result = benchmark.classify_chat(client, 'paid-fixture', benchmark.TESTS[0])
        self.assertEqual(result['cost'], 0.5)
        self.assertIsNone(benchmark.get_cost({'usage': {'cost': True}}))
    def test_missing_fallback_diagnostics_are_unknown(self):
        health = load_tool('test-models')
        self.assertIsNone(health.extract_headers(httpx.Response(200))['fallbacks'])

    def test_vision_prompt_does_not_supply_answer(self):
        health = load_tool('test-models')
        def upstream(request):
            import json
            payload = json.loads(request.content)
            question = payload['messages'][0]['content'][0]['text']
            self.assertNotIn('red', question.lower())
            return httpx.Response(200, json={'choices': [{'message': {'content': 'FINAL=red'}}]})
        with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
            health.capability_vision(client, 'paid-vision')

    def test_unknown_request_price_stays_unknown(self):
        discovery = load_tool('discover-free-models')
        price = discovery.normalized_pricing({'pricing': {'prompt': '0.001', 'completion': '0.002'}})
        self.assertIsNone(price['request'])
        self.assertIsNone(discovery.price_per_million({'pricing': {'prompt': 'NaN'}}, 'prompt'))
        self.assertFalse(discovery.is_zero_cost_model({'id':'fixture:free', 'pricing':{'prompt':'0','completion':'0'}}))
        self.assertFalse(discovery.is_zero_cost_model({'pricing':{'prompt':False,'completion':'0','request':'0'}}))

    def test_failed_billable_attempt_is_counted_and_unknown_coverage_visible(self):
        benchmark = load_tool('benchmark-classifiers')
        summary = benchmark.summarize('fake', [
            {'ok': True, 'correct': True, 'latency': 1, 'cost': 0.25},
            {'ok': False, 'correct': False, 'latency': 2, 'cost': 0.5},
            {'ok': False, 'correct': False, 'latency': 3, 'cost': None},
        ])
        self.assertEqual(summary['known_cost'], 0.75)
        self.assertIsNone(summary['total_cost'])
        self.assertEqual(summary['unknown_cost_requests'], 1)


class ClassifierTests(unittest.IsolatedAsyncioTestCase):
    async def strict_case(self, handler):
        from tools.test_classifier_controls import fixture
        with tempfile.TemporaryDirectory() as folder:
            config, policy = fixture(folder)
            real_client = httpx.AsyncClient
            with patch.dict(os.environ, {'COST_ROUTER_CONFIG': str(config)}), \
                 patch('router.jev_classifier.httpx.AsyncClient', side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
                classifier = OpenRouterJevClassifier()
                diagnostics = {}
                from router.cost_policy import policy_revision
                from router.cost_transport import register_request_context
                trusted = register_request_context('jev', {'messages':[{'role':'user','content':'hello'}]}, [], ['free','paid'], policy_revision(classifier.cost_config))
                result = await classifier.classify({'raw_messages': [{'role':'user','content':'hello'}],
                    'metadata': {'_cost_request':trusted['id']}}, diagnostics=diagnostics)
                return result, diagnostics, classifier.accounting.ledger.report()

    async def test_strict_jev_receives_server_owned_eligible_snapshot(self):
        sent=[]
        def upstream(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200,json={'answers':{'model':{'choice':'GENERAL_EFFICIENT'}},'usage':{'cost':0}})
        result, diagnostics, _ = await self.strict_case(upstream)
        self.assertEqual(result,'GENERAL_EFFICIENT')
        self.assertTrue(diagnostics['ok'])
        self.assertEqual([row['alias'] for row in sent[0]['state']['eligible_models']], ['GENERAL_EFFICIENT'])
        self.assertIn('remaining_request',sent[0]['state']['eligible_models'][0])

    async def test_cost_aware_classifier_reserves_and_settles(self):
        def upstream(request):
            return httpx.Response(200,json={'answers':{'model':{'choice':'GENERAL_EFFICIENT'}},'usage':{'cost':0.00000002}})
        result, diagnostics, report = await self.strict_case(upstream)
        self.assertEqual(result,'GENERAL_EFFICIENT')
        self.assertTrue(diagnostics['ok'])
        self.assertEqual(report['models']['jev']['today']['provider_reported'],20)

    async def test_classifier_failure_keeps_unknown_reservation(self):
        def upstream(request):
            raise httpx.ConnectError('fixture unavailable',request=request)
        result, diagnostics, report = await self.strict_case(upstream)
        self.assertEqual(result,'GENERAL_EFFICIENT')
        self.assertFalse(diagnostics['ok'])
        self.assertEqual(report['attempts'][0]['state'],'unknown')
        self.assertGreater(report['models']['jev']['today']['exposure'],0)
    async def test_invalid_timeout_is_rejected_at_configuration_boundary(self):
        for value in ('nan', 'inf', '-1', 'bad'):
            with patch.dict(os.environ, {'JEV_TIMEOUT_SECONDS': value}):
                with self.assertRaises(ValueError):
                    OpenRouterJevClassifier()
    async def test_invalid_transcript_limit_has_controlled_fallback(self):
        with patch.dict(os.environ, {'JEV_MAX_MESSAGES': 'bad'}):
            result = await OpenRouterJevClassifier().classify({'raw_messages': [{'role': 'user', 'content': 'Hello'}]})
        self.assertEqual(result, 'GENERAL_CAPABLE')
    async def test_real_request_with_metadata_words_reaches_production_classifier(self):
        sent = []
        def upstream(request):
            sent.append(request.read().decode())
            return httpx.Response(200, json={'answers': {'tier': {'choice': 'CODING_EFFICIENT'}}})
        real_client = httpx.AsyncClient
        with patch('router.jev_classifier.httpx.AsyncClient',
                   side_effect=lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw)):
            result = await OpenRouterJevClassifier().classify({'raw_messages': [
                {'role': 'user', 'content': 'Fix the chat_id parser and message_id validation.'}]})
        self.assertEqual(result, 'CODING_EFFICIENT')
        self.assertIn('Fix the chat_id parser', sent[0])


class QuotaTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_counts_do_not_authorize_strict_traffic(self):
        from router.openrouter_quota_guard import OpenRouterQuotaGuard
        real_client = httpx.AsyncClient
        for values in ((-1, 50, 51), (True, 50, 49), (1.5, 50, 49), (1, 50, 50)):
            def upstream(request):
                return httpx.Response(200, json={'data': {'free_model_daily_requests': dict(zip(('used','limit','remaining'), values))}})
            with patch.dict(os.environ, {'OPENROUTER_QUOTA_FAIL_OPEN': 'false'}), \
                 patch('router.openrouter_quota_guard.httpx.AsyncClient',
                       side_effect=lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw)):
                with self.assertRaises(Exception) as error:
                    await OpenRouterQuotaGuard().async_pre_call_hook(None, None, {'model':'fast'}, None)
                self.assertEqual(error.exception.status_code, 503)
    async def test_stale_quota_fails_closed_and_failed_refresh_is_backed_off(self):
        from router.openrouter_quota_guard import OpenRouterQuotaGuard
        clock = [100.0]
        requests = []

        def upstream(request):
            requests.append(request)
            if len(requests) == 1:
                return httpx.Response(200, json={'data': {'free_model_daily_requests':
                    {'used': 1, 'limit': 50, 'remaining': 49}}})
            return httpx.Response(503)

        real_client = httpx.AsyncClient
        with patch.dict(os.environ, {'OPENROUTER_QUOTA_FAIL_OPEN': 'false'}), \
             patch('router.openrouter_quota_guard.time.monotonic', side_effect=lambda: clock[0]), \
             patch('router.openrouter_quota_guard.httpx.AsyncClient',
                   side_effect=lambda **kw: real_client(transport=httpx.MockTransport(upstream), **kw)):
            guard = OpenRouterQuotaGuard()
            self.assertEqual((await guard.async_pre_call_hook(None, None, {'model': 'fast'}, None))['model'], 'fast')
            clock[0] += 31
            for _ in range(3):
                with self.assertRaises(Exception) as error:
                    await guard.async_pre_call_hook(None, None, {'model': 'fast'}, None)
                self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(len(requests), 2)
            headers = await guard.async_post_call_response_headers_hook({}, None, None)
            self.assertEqual(headers['x-openrouter-free-status'], 'unknown')
            self.assertEqual(len(requests), 2)


if __name__ == '__main__':
    unittest.main()
