"""Acceptance of semantic callback routing through public seams; offline only."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(ROOT / 'outputs/token-cache')
import httpx
import yaml
from router.jev_classifier import OpenRouterJevClassifier
from router.jev_router import FamilyFilter, SemanticDecision, JevRouter
from litellm.types.router import RoutingContext
from litellm.proxy._types import UserAPIKeyAuth


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_model_guardrail_fails_closed(self):
        import litellm
        from litellm.proxy import proxy_server
        from fastapi import HTTPException
        engine = litellm.Router(model_list=[{'model_name': 'free-general-capable',
            'litellm_params': {'model': 'openai/gpt-4o-mini', 'api_key': 'fake-only', 'guardrails': ['required-guard']}}])
        with patch.object(proxy_server, 'llm_router', engine), patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}):
            with self.assertRaises(HTTPException) as failure:
                await JevRouter().async_pre_call_hook(UserAPIKeyAuth(), None,
                    {'model': 'jev', 'messages': [{'role': 'user', 'content': 'hello'}]}, 'acompletion')
        self.assertEqual(failure.exception.status_code, 503)

    async def test_config_loader_and_missing_callback_fail_locally(self):
        import litellm
        from litellm.proxy.types_utils.utils import get_instance_fn
        from litellm.utils import custom_llm_setup
        config = yaml.safe_load((ROOT / 'router/config.yaml').read_text(encoding='utf-8'))
        loaded = get_instance_fn(config['litellm_settings']['callbacks'][0], str(ROOT / 'router/config.yaml'))
        self.assertIsInstance(loaded, JevRouter)
        item = config['litellm_settings']['custom_provider_map'][0]
        guard = get_instance_fn(item['custom_handler'], str(ROOT / 'router/config.yaml'))
        with patch.object(litellm, 'custom_provider_map', [{'provider': item['provider'], 'custom_handler': guard}]):
            custom_llm_setup()
            entrypoint = next(row for row in config['model_list'] if row['model_name'] == 'jev')
            engine = litellm.Router(model_list=[entrypoint], **config['router_settings'])
            with self.assertRaises(Exception) as failure:
                await engine.acompletion(model='jev', messages=[{'role': 'user', 'content': 'hello'}])
            self.assertIn('jev routing callback is required', str(failure.exception))

    async def test_classifier_failures_default_once_and_cancellation_propagates(self):
        client = httpx.AsyncClient
        for outcome in ('UNKNOWN_CAPABLE', 'CODING_UNKNOWN', None, 'timeout', 'cancel'):
            count = []
            def upstream(request):
                if request.url.path.endswith('/key'):
                    return httpx.Response(200, json={})
                count.append(1)
                if outcome == 'timeout':
                    raise httpx.ReadTimeout('fixture')
                if outcome == 'cancel':
                    raise asyncio.CancelledError()
                return httpx.Response(200, json={'answers': {'tier': {'choice': outcome}}})
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only'}), patch('httpx.AsyncClient',
                    side_effect=lambda **kw: client(**{**kw, 'transport': httpx.MockTransport(upstream)})):
                callback = JevRouter()
                call = callback.async_pre_call_hook(UserAPIKeyAuth(), None,
                    {'model': 'jev', 'messages': [{'role': 'user', 'content': 'hello'}]}, 'completion')
                if outcome == 'cancel':
                    with self.assertRaises(asyncio.CancelledError):
                        await call
                else:
                    result = await call
                    self.assertEqual(result['model'], 'free-general-capable')
                    self.assertEqual(result['metadata']['jev']['semantic_class'], 'GENERAL_CAPABLE')
            self.assertEqual(len(count), 1)

    async def test_concurrent_twenty_callbacks_keep_one_decision_each(self):
        seen = []
        client = httpx.AsyncClient
        choices = [f'{f}_{c}' for f in ('GENERAL', 'REASONING', 'AGENTIC', 'CODING')
                   for c in ('EFFICIENT', 'CAPABLE', 'ADVANCED', 'EXPERT', 'FRONTIER')]
        async def upstream(request):
            if request.url.path.endswith('/key'):
                return httpx.Response(200, json={'data': {'free_model_daily_requests': {'used': 0, 'limit': 10, 'remaining': 10}}})
            payload = json.loads(request.content)
            # Unique task markers in transcript; classifier criteria also contain all classes.
            transcript = payload['state']
            marker = next(c for c in choices if 'TASK:' + c in json.dumps(transcript))
            seen.append(marker)
            await asyncio.sleep(0)
            return httpx.Response(200, json={'answers': {'tier': {'choice': marker}}})
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only', 'JEV_LOG_RAW_ANSWER': 'false', 'JEV_LOG_TIMING': 'false'}), \
             patch('httpx.AsyncClient', side_effect=lambda **kw: client(**{**kw, 'transport': httpx.MockTransport(upstream)})):
            callback = JevRouter()
            results = await asyncio.gather(*(callback.async_pre_call_hook(UserAPIKeyAuth(), None,
                {'model': 'jev', 'messages': [{'role': 'user', 'content': 'TASK:' + c}]}, 'completion') for c in choices))
        self.assertCountEqual(seen, choices)
        for choice, result in zip(choices, results):
            family, level = choice.split('_')
            signal = result['metadata']['jev']
            self.assertEqual(signal['semantic_class'], choice)
            self.assertEqual(signal['family'], family)
            self.assertEqual(signal['capability'], level)
            self.assertEqual(len(signal['candidates_before']), 4)
            self.assertEqual(signal['candidates_after'], [result['model']])
            self.assertEqual(result['model'], SemanticDecision(family, level).alias)

    async def test_real_proxy_callback_and_router_failure_order(self):
        import litellm
        from litellm.proxy import proxy_server
        from litellm.llms.custom_llm import CustomLLM, CustomLLMError
        from litellm.utils import custom_llm_setup
        attempts = []
        class Solver(CustomLLM):
            async def acompletion(self, model, **kwargs):
                attempts.append(model)
                if model != 'paid-general-capable':
                    raise CustomLLMError(429, 'fixture unavailable')
                return litellm.ModelResponse(model=model, choices=[{'message': {'role': 'assistant', 'content': 'ok'}}])
        callback = JevRouter()
        models = [{'model_name': row['model_name'], 'litellm_params': {'model': 'offline_solver/' + row['model_name']}}
                  for row in callback.config['model_list'] if row['model_name'] != 'jev']
        with patch.object(litellm, 'custom_provider_map', [{'provider': 'offline_solver', 'custom_handler': Solver()}]), \
             patch.object(litellm, 'callbacks', [callback]), patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}):
            custom_llm_setup()
            engine = litellm.Router(model_list=models, **callback.config['router_settings'])
            with patch.object(proxy_server, 'llm_router', engine):
                data = await proxy_server.proxy_logging_obj.pre_call_hook(UserAPIKeyAuth(),
                    {'model': 'jev', 'messages': [{'role': 'user', 'content': 'hello'}]}, 'acompletion')
                response = await engine.acompletion(**data)
        self.assertEqual(response.choices[0].message.content, 'ok')
        self.assertEqual(attempts, ['free-general-capable', 'free-general-capable-backup', 'advanced-general', 'paid-general-capable'])
        self.assertEqual(data['metadata']['jev']['semantic_class'], 'GENERAL_CAPABLE')

    async def test_real_router_http_attempt_order_for_each_capability(self):
        import litellm
        client = httpx.AsyncClient
        callback = JevRouter()
        for level in ('EFFICIENT', 'CAPABLE', 'ADVANCED', 'EXPERT', 'FRONTIER'):
            alias = SemanticDecision('CODING', level).alias
            chain = callback._chain(alias)
            attempts = []
            def upstream(request):
                body = json.loads(request.content)
                attempts.append(body['model'])
                if body['model'] != chain[-1]:
                    return httpx.Response(503, json={'error': {'message': 'offline fixture unavailable', 'type': 'server_error'}})
                return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                    'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}]})
            models = [{'model_name': name, 'litellm_params': {'model': 'openai/' + name,
                       'api_key': 'fake-only', 'api_base': 'https://offline.invalid/v1'}} for name in [alias, *chain]]
            class OfflineClient(client):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **{**kwargs, 'transport': httpx.MockTransport(upstream)})
            with patch('httpx.AsyncClient', OfflineClient):
                engine = litellm.Router(model_list=models, **callback.config['router_settings'])
                callback.quota.api_key = ''
                data = await callback.async_pre_call_hook(UserAPIKeyAuth(), None,
                    {'model': alias, 'messages': [{'role': 'user', 'content': 'hello'}]}, 'acompletion')
                await engine.acompletion(**data)
            self.assertEqual(attempts, [alias, *chain])

    async def test_stale_quota_uses_unknown_policy(self):
        from router.openrouter_quota_guard import OpenRouterQuotaGuard, QuotaSnapshot
        from fastapi import HTTPException
        guard = OpenRouterQuotaGuard()
        guard._snapshot = QuotaSnapshot(10, 10, 0, 0)
        guard.api_key = ''
        data = {'model': 'free-coding-capable'}
        self.assertEqual(await guard.async_pre_call_hook(None, None, dict(data), 'completion'), data)
        guard.fail_open = False
        with self.assertRaises(HTTPException) as failure:
            await guard.async_pre_call_hook(None, None, dict(data), 'completion')
        self.assertEqual(failure.exception.status_code, 503)

    async def test_exhausted_quota_keeps_family_and_skips_free(self):
        client = httpx.AsyncClient
        def upstream(request):
            if request.url.path.endswith('/key'):
                return httpx.Response(200, json={'data': {'free_model_daily_requests': {'used': 10, 'limit': 10, 'remaining': 0}}})
            return httpx.Response(200, json={'answers': {'tier': {'choice': 'CODING_CAPABLE'}}})
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only'}), patch('httpx.AsyncClient',
                side_effect=lambda **kw: client(**{**kw, 'transport': httpx.MockTransport(upstream)})):
            callback = JevRouter()
            data = {'model': 'jev', 'messages': [{'role': 'user', 'content': 'write code'}]}
            result = await callback.async_pre_call_hook(UserAPIKeyAuth(), None, data, 'completion')
            self.assertEqual(result['model'], 'advanced-coding')
            self.assertEqual(result['metadata']['jev']['semantic_class'], 'CODING_CAPABLE')
            direct = await callback.async_pre_call_hook(UserAPIKeyAuth(), None,
                {'model': 'free-reasoning-capable'}, 'completion')
            self.assertEqual(direct['model'], 'advanced-reasoning')
            specialist = await callback.async_pre_call_hook(UserAPIKeyAuth(), None, {'model': 'vision'}, 'completion')
            self.assertEqual(specialist['model'], 'paid-vision')

    async def test_callback_rejects_unsupported_surface_and_overrides(self):
        from fastapi import HTTPException
        for extra, call_type in [({'api_base': 'https://invalid.example'}, 'completion'),
                                 ({'fallbacks': ['paid-emergency']}, 'completion'),
                                 ({'user_config': {'model_list': []}}, 'acompletion'),
                                 ({'router_settings_override': {}}, 'acompletion'),
                                 ({'num_retries': 99}, 'acompletion'),
                                 ({'model_group_retry_policy': {'free-general-capable': {'RateLimitErrorRetries': 99}}}, 'acompletion'),
                                 ({'custom_llm_provider': 'chatgpt'}, 'completion'),
                                 ({}, 'embedding'), ({'messages': []}, 'completion')]:
            data = {'model': 'jev', 'messages': [{'role': 'user', 'content': 'hello'}], **extra}
            with self.assertRaises(HTTPException):
                await JevRouter().async_pre_call_hook(UserAPIKeyAuth(), None, data, call_type)

    async def test_selected_alias_requires_permission(self):
        from litellm.proxy._types import ProxyException
        data = {'model': 'jev', 'messages': [{'role': 'user', 'content': 'hello'}]}
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}), self.assertRaises(ProxyException):
            await JevRouter().async_pre_call_hook(UserAPIKeyAuth(models=['jev']), None, data, 'completion')

    async def test_callback_makes_one_semantic_call_and_retains_request_signal(self):
        seen = []
        client = httpx.AsyncClient
        def upstream(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={'answers': {'tier': {'choice': 'CODING_EXPERT'}}})
        data = {'model': 'jev', 'messages': [{'role': 'user', 'content': 'Fix this defect.'}],
                'metadata': {'jev': {'family': 'GENERAL'}, 'provider_hint': 'client-injected'}}
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fake-only'}), \
             patch('router.jev_classifier.httpx.AsyncClient',
                   side_effect=lambda **kw: client(**{**kw, 'transport': httpx.MockTransport(upstream)})):
            result = await JevRouter().async_pre_call_hook(UserAPIKeyAuth(), None, data, 'completion')
        self.assertEqual(len(seen), 1)
        self.assertEqual(result['model'], 'expert-coding')
        self.assertEqual(result['metadata']['jev']['semantic_class'], 'CODING_EXPERT')
        self.assertEqual(result['metadata']['jev']['family'], 'CODING')
        self.assertNotIn('client-injected', json.dumps(seen))
        self.assertNotIn('chatgpt/', json.dumps(seen))
        self.assertNotIn('gpt-5.6', json.dumps(seen))

    async def test_all_twenty_decisions_narrow_to_one_family(self):
        for family in ('GENERAL', 'REASONING', 'AGENTIC', 'CODING'):
            for capability in ('EFFICIENT', 'CAPABLE', 'ADVANCED', 'EXPERT', 'FRONTIER'):
                with self.subTest(family=family, capability=capability):
                    decision = SemanticDecision(family, capability)
                    pool = [SemanticDecision(f, capability).alias for f in ('GENERAL', 'REASONING', 'AGENTIC', 'CODING')]
                    context = RoutingContext(raw_messages=[], structured_messages=[], candidate_models=pool,
                                             signals={'jev': decision.as_dict()})
                    result = await FamilyFilter().run(context)
                    expected = (f'free-{family.lower()}-{capability.lower()}' if capability in ('EFFICIENT', 'CAPABLE')
                                else f'{capability.lower()}-{family.lower()}')
                    self.assertEqual(decision.semantic_class, f'{family}_{capability}')
                    self.assertEqual(result.candidate_models, [expected])
                    self.assertEqual(len(pool), 4)
                    self.assertTrue(set(result.candidate_models) <= set(pool))

    async def test_invalid_decisions_and_missing_candidates_fail_closed(self):
        for family, level in [('UNKNOWN', 'CAPABLE'), ('CODING', 'UNKNOWN'), (None, 'CAPABLE')]:
            with self.assertRaises(ValueError):
                SemanticDecision(family, level)
        for signals, pool in [({}, ['expert-coding']), ({'jev': {'family': 'CODING', 'capability': 'EXPERT'}}, ['expert-general'])]:
            context = RoutingContext(raw_messages=[], structured_messages=[], candidate_models=pool, signals=signals)
            with self.assertRaises(ValueError):
                await FamilyFilter().run(context)


if __name__ == '__main__':
    unittest.main(verbosity=2)

