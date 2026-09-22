"""Offline public routing seams. No authentication or live provider calls."""
import json
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
ROOT = Path(__file__).resolve().parents[1]
os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(ROOT / 'outputs/token-cache')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'router'))
import httpx
import yaml
from router.jev_classifier import OpenRouterJevClassifier

FAMILIES = ('GENERAL', 'REASONING', 'AGENTIC', 'CODING')
LEVELS = ('EFFICIENT', 'CAPABLE', 'ADVANCED', 'EXPERT', 'FRONTIER')
EXPECTED = {f'{family}_{level}' for family in FAMILIES for level in LEVELS}


class TwentyTierTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_eight_criteria_and_capable_wording_are_preserved(self):
        spec = importlib.util.spec_from_file_location('raw_classifier_reference', ROOT / 'raw/jev_classifier.py')
        baseline = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'dont_write_bytecode', True):
            spec.loader.exec_module(baseline)
        captured = []
        client = httpx.AsyncClient

        def upstream(request):
            captured.append(json.loads(request.content)['questions']['tier'])
            return httpx.Response(200, json={'answers': {'tier': {'choice': 'GENERAL_CAPABLE'}}})

        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only',
                                     'JEV_LOG_RAW_ANSWER': 'false', 'JEV_LOG_TIMING': 'false'}), \
             patch('httpx.AsyncClient', side_effect=lambda **kw: client(transport=httpx.MockTransport(upstream), **kw)):
            for classifier in (baseline.OpenRouterJevClassifier(), OpenRouterJevClassifier()):
                await classifier.classify({'raw_messages': [{'role': 'user', 'content': 'Review this plan.'}]})
        original, current = captured
        for tier, description in original['criteria'].items():
            self.assertEqual(current['criteria'][tier], description, tier)
        old_instruction = original['instructions'].split('Choose CAPABLE', 1)[1].split('Use the full transcript', 1)[0]
        self.assertIn('Choose CAPABLE' + old_instruction, current['instructions'])

    async def test_chatgpt_routes_never_fetch_or_apply_openrouter_quota(self):
        from router.openrouter_quota_guard import OpenRouterQuotaGuard
        guard = OpenRouterQuotaGuard()
        requests = [{'model': f'{level}-{family.lower()}'}
                    for family in FAMILIES for level in ('advanced', 'expert', 'frontier')]
        requests += [{'model': 'chatgpt/gpt-5.6-luna'},
                     {'model': 'custom:free', 'custom_llm_provider': 'chatgpt'},
                     {'model': 'custom:free', 'litellm_params': {'custom_llm_provider': 'chatgpt'}}]
        with patch.object(guard, '_get_snapshot', new_callable=AsyncMock) as quota:
            quota.side_effect = AssertionError('ChatGPT must not fetch OpenRouter quota')
            for data in requests:
                with self.subTest(data=data):
                    original = dict(data)
                    self.assertEqual(await guard.async_pre_call_hook(None, None, data, 'completion'), original)
                    self.assertEqual(await guard.async_post_call_response_headers_hook(data, None, None), {})
            self.assertEqual(await guard.async_post_call_response_headers_hook(
                {'model': 'jev'}, None,
                type('Response', (), {'_hidden_params': {'custom_llm_provider': 'chatgpt'}})()), {})
            quota.assert_not_awaited()

    async def test_classifier_offers_and_accepts_all_twenty_semantic_choices(self):
        client = httpx.AsyncClient
        for tier in sorted(EXPECTED):
            with self.subTest(tier=tier):
                def upstream(request):
                    payload = json.loads(request.content)
                    self.assertEqual(set(payload['questions']), {'tier'})
                    self.assertEqual(set(payload['questions']['tier']['criteria']), EXPECTED)
                    self.assertNotIn('FREE solver tier', payload['state']['description'])
                    return httpx.Response(200, json={'answers': {'tier': {'choice': tier}}})
                with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only',
                                             'JEV_LOG_RAW_ANSWER': 'false', 'JEV_LOG_TIMING': 'false'}), \
                     patch('router.jev_classifier.httpx.AsyncClient',
                           side_effect=lambda **kw: client(transport=httpx.MockTransport(upstream), **kw)):
                    result = await OpenRouterJevClassifier().classify(
                        {'raw_messages': [{'role': 'user', 'content': 'Evaluate this task.'}]})
                self.assertEqual(result, tier)

    def test_config_preserves_deployments_and_inserts_subscription_before_paid(self):
        config = yaml.safe_load((ROOT / 'router/config.yaml').read_text(encoding='utf-8'))
        original = yaml.safe_load((ROOT / 'raw/config.yaml').read_text(encoding='utf-8'))
        deployments = {row['model_name']: row for row in config['model_list']}
        self.assertEqual(deployments['jev']['litellm_params']['model'], 'jev_guard/required')
        self.assertNotIn('complexity_router_config', deployments['jev']['litellm_params'])
        self.assertEqual(config['litellm_settings']['callbacks'], ['router.jev_router.proxy_handler_instance'])
        chains = {k: v for item in config['router_settings']['fallbacks'] for k, v in item.items()}
        self.assertNotIn('jev', chains)
        for item in original['router_settings']['fallbacks']:
            for alias, chain in item.items():
                if alias == 'jev':
                    continue
                if alias.startswith('free-') and alias.split('-')[1].upper() in FAMILIES:
                    expected = list(chain)
                    expected.insert(next(i for i, name in enumerate(chain) if name.startswith('paid-')),
                                    'advanced-' + alias.split('-')[1])
                    self.assertEqual(chains[alias], expected)
                else:
                    self.assertEqual(chains[alias], chain)
        for row in original['model_list']:
            if row['model_name'] != 'jev':
                self.assertEqual(deployments[row['model_name']], row)
        for family in FAMILIES:
            for level, model in [('ADVANCED', 'luna'), ('EXPERT', 'terra'), ('FRONTIER', 'sol')]:
                alias = f'{level.lower()}-{family.lower()}'
                self.assertEqual(deployments[alias]['litellm_params']['model'], f'chatgpt/gpt-5.6-{model}')
                self.assertEqual(chains[alias], [f'paid-{family.lower()}-capable',
                                                f'paid-{family.lower()}-capable-backup', 'paid-emergency'])


if __name__ == '__main__':
    unittest.main()
