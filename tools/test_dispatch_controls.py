"""Final physical dispatch regressions: no real network or provider accounts."""
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from router.cost_transport import CostTransport, AccountedStream, dispatch_context, register_request_context
from router.spend_ledger import Ledger, BudgetDenied


def contract(**extra):
    return dict(kind='loopback-fixed-bound', canonical='shared', origin='http://127.0.0.1:9999',
                path='/v1/chat/completions', input_nanos_per_token=0, output_nanos_per_token=1,
                max_output_tokens=90, revision='test-v1', evidence_ref='local-fixture',
                valid_from='2020-01-01T00:00:00+00:00', expires_at='2099-01-01T00:00:00+00:00',
                supported_surfaces=['text-chat'], final_usage_rule='complete-response-cost', **extra)


class Bytes(httpx.AsyncByteStream):
    def __init__(self, chunks): self.chunks = chunks
    async def __aiter__(self):
        for chunk in self.chunks: yield chunk


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(str(Path(self.tmp.name) / 'spend.sqlite'),
            {'daily': 1000, 'monthly': 1000, 'request': 1000,
             'models': {'shared': {'daily': 1000, 'monthly': 1000}}})
    def tearDown(self): self.tmp.cleanup()

    async def test_partial_usage_without_done_keeps_bound(self):
        self.ledger.reserve('a', 'r', 'shared', 'alias', 'dep', 90)
        stream = AccountedStream(Bytes([b'data: {"usage":{"cost":0.00000001}}\n\n']),
                                 self.ledger, 'a', 'text/event-stream')
        async for _ in stream: pass
        await stream.aclose()
        self.assertEqual(self.ledger.report()['overall']['today']['exposure'], 90)

    async def test_absent_output_limit_is_sent_to_upstream(self):
        seen = []
        async def receive(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={'usage': {'cost': 0.00000001}})
        policy = {'deployments': {'dep': {'alias': 'actual-alias', 'provider_model': 'fake',
                  'contract': 'fake', 'capabilities': ['general'], 'free': False}}}
        transport = CostTransport(self.ledger, {'fake': contract()}, inner=httpx.MockTransport(receive), policy=policy)
        context = register_request_context('entry', {}, ['general'], ['dep'], 'test')
        dispatch_context.set({'request': context['id'], 'deployment': 'dep', 'policy_revision': 'test'})
        async with httpx.AsyncClient(transport=transport) as client:
            await client.post('http://127.0.0.1:9999/v1/chat/completions',
                              json={'model': 'fake', 'messages': [{'role': 'user', 'content': 'hi'}]})
        self.assertEqual(seen[0].get('max_tokens'), 90)

    async def test_conflicting_output_limits_are_refused(self):
        from router.cost_policy import request_charge
        with self.assertRaises(BudgetDenied):
            request_charge(contract(), {'messages': [], 'max_tokens': 1, 'max_completion_tokens': 90})

    async def test_expired_and_multimodal_contracts_are_refused(self):
        from router.cost_policy import request_charge
        stale = contract(); stale['expires_at'] = '2020-01-02T00:00:00+00:00'
        with self.assertRaises(BudgetDenied): request_charge(stale, {'messages': []})
        with self.assertRaises(BudgetDenied):
            request_charge(contract(), {'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'http://example.invalid/x'}}]}]})

    async def test_final_gate_rejects_incompatible_and_unlisted_fallbacks(self):
        seen = []
        async def receive(request):
            seen.append(request)
            return httpx.Response(200, json={'usage': {'cost': 0}})
        policy = {'deployments': {
            'text': {'alias': 'emergency', 'provider_model': 'fake', 'contract': 'c',
                     'capabilities': ['general'], 'free': False},
            'vision': {'alias': 'vision', 'provider_model': 'fake', 'contract': 'c',
                     'capabilities': ['vision'], 'free': False}}}
        transport = CostTransport(self.ledger, {'c': contract()}, policy=policy, inner=httpx.MockTransport(receive))
        context = register_request_context('vision-entry', {}, ['vision'], ['text'], 'test')
        async with httpx.AsyncClient(transport=transport) as client:
            for identifier, diagnostic in [('text', 'capability_mismatch'), ('vision', 'not_allowed')]:
                dispatch_context.set({'request': context['id'], 'deployment': identifier, 'policy_revision': 'test'})
                with self.assertRaisesRegex(BudgetDenied, diagnostic):
                    await client.post('http://127.0.0.1:9999/v1/chat/completions', json={'model':'fake','messages':[]})
        self.assertEqual(seen, [])
        self.assertEqual(self.ledger.report()['attempts'], [])

    async def test_free_first_and_paid_fallback_after_recorded_failure(self):
        seen = []
        async def receive(request):
            payload = json.loads(request.content); seen.append(payload['model'])
            return httpx.Response(503 if payload['model'] == 'free' else 200, json={'usage': {'cost': 0}})
        zero = contract(); zero['output_nanos_per_token'] = 0
        policy = {'deployments': {identifier: {'alias': identifier, 'provider_model': identifier,
                    'contract': identifier, 'capabilities': ['general'], 'free': identifier == 'free'}
                    for identifier in ('free', 'paid')}}
        transport = CostTransport(self.ledger, {'free': zero, 'paid': contract()},
                                  policy=policy, inner=httpx.MockTransport(receive))
        context = register_request_context('entry', {}, ['general'], ['free', 'paid'], 'test')
        async with httpx.AsyncClient(transport=transport) as client:
            dispatch_context.set({'request': context['id'], 'deployment': 'paid', 'policy_revision': 'test'})
            with self.assertRaisesRegex(BudgetDenied, 'free_first_required'):
                await client.post('http://127.0.0.1:9999/v1/chat/completions', json={'model':'paid','messages':[]})
            for identifier in ('free', 'paid'):
                dispatch_context.set({'request': context['id'], 'deployment': identifier, 'policy_revision': 'test'})
                await client.post('http://127.0.0.1:9999/v1/chat/completions', json={'model':identifier,'messages':[]})
        self.assertEqual(seen, ['free', 'paid'])

    async def test_shared_provider_preserves_each_alias_and_deployment(self):
        async def receive(request): return httpx.Response(200, headers={'content-type':'application/json'},
                stream=Bytes([b'{"usage":{"cost":0.00000001}}']))
        policy = {'deployments': {identifier: {'alias': identifier + '-alias', 'provider_model': 'same',
                    'contract': 'c', 'capabilities': [], 'free': False} for identifier in ('one', 'two')}}
        transport = CostTransport(self.ledger, {'c': contract()}, policy=policy, inner=httpx.MockTransport(receive))
        async with httpx.AsyncClient(transport=transport) as client:
            for identifier in ('one', 'two'):
                context = register_request_context('entry-' + identifier, {}, [], [identifier], 'test')
                dispatch_context.set({'request': context['id'], 'deployment': identifier, 'policy_revision': 'test'})
                await client.post('http://127.0.0.1:9999/v1/chat/completions', json={'model':'same','messages':[]})
        attempts = self.ledger.report()['attempts']
        self.assertEqual({a['alias'] for a in attempts}, {'one-alias','two-alias'})
        self.assertEqual({a['deployment'] for a in attempts}, {'one','two'})
        self.assertEqual({a['provider_model'] for a in attempts}, {'same'})
        self.assertEqual({a['entry_alias'] for a in attempts}, {'entry-one','entry-two'})
        self.assertEqual(self.ledger.report()['models']['shared']['today']['exposure'], 20)

    async def test_complete_split_sse_settles_but_conflicting_costs_do_not(self):
        for identifier, chunks, expected in [
            ('complete', [b'data: {"usage":{"co', b'st":0.00000001}}\n\ndata: [DONE]\n\n'], 10),
            ('conflict', [b'data: {"usage":{"cost":0.00000001}}\n\ndata: {"usage":{"cost":0.00000002}}\n\ndata: [DONE]\n\n'], 90),
        ]:
            self.ledger.reserve(identifier, identifier, 'shared', 'alias', 'dep', 90)
            stream = AccountedStream(Bytes(chunks), self.ledger, identifier, 'text/event-stream')
            async for _ in stream: pass
            await stream.aclose()
            row = next(a for a in self.ledger.report()['attempts'] if a['id'] == identifier)
            self.assertEqual(self.ledger._exposure(row), expected)

    async def test_cancel_after_partial_usage_retains_bound(self):
        self.ledger.reserve('cancel', 'cancel', 'shared', 'alias', 'dep', 90)
        stream = AccountedStream(Bytes([b'data: {"usage":{"cost":0.00000001}}\n\n', b'data: [DONE]\n\n']),
                                 self.ledger, 'cancel', 'text/event-stream')
        iterator = stream.__aiter__()
        await anext(iterator)
        await iterator.aclose()
        await stream.aclose()
        self.assertEqual(self.ledger.report()['overall']['today']['exposure'], 90)


    async def test_transport_denial_has_typed_proxy_failure_diagnostic(self):
        import os
        os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
        os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(Path(__file__).resolve().parents[1] / 'outputs/token-cache')
        from router.cost_guard import CostGuard
        context = register_request_context('entry', {}, [], [], 'test')
        context['last_denial'] = 'Per-request ceiling exceeded'
        guard = CostGuard.__new__(CostGuard)
        transformed = await guard.async_post_call_failure_hook(
            {'metadata': {'_cost_request': context['id']}}, RuntimeError('Connection error'), None)
        self.assertIsNotNone(transformed)
        self.assertEqual(transformed.status_code, 429)
        self.assertIn('Per-request ceiling', str(transformed.detail))

    async def test_provider_executed_tools_are_not_a_bounded_text_surface(self):
        from router.cost_policy import request_charge
        with self.assertRaisesRegex(BudgetDenied, 'unsupported_request_surface'):
            request_charge(contract(), {'messages':[], 'tools':[{'type':'web_search'}]})

    async def test_contract_expiring_while_reservation_waits_never_dispatches(self):
        import time
        from datetime import datetime, timezone, timedelta
        from unittest.mock import patch
        seen = []
        async def receive(request):
            seen.append(request)
            return httpx.Response(200, json={'usage': {'cost': 0}})
        billing = contract()
        policy = {'deployments': {'dep': {'alias':'paid', 'provider_model':'fake',
                  'contract':'c', 'capabilities':[], 'free':False}}}
        transport = CostTransport(self.ledger, {'c': billing}, policy=policy, inner=httpx.MockTransport(receive))
        context = register_request_context('paid', {}, [], ['dep'], 'test')
        dispatch_context.set({'request': context['id'], 'deployment':'dep', 'policy_revision':'test'})
        reserve = self.ledger.reserve
        def delayed_reservation(*args, **kwargs):
            result = reserve(*args, **kwargs)
            time.sleep(0.6)
            return result
        billing['expires_at'] = (datetime.now(timezone.utc) + timedelta(seconds=0.5)).isoformat()
        async with httpx.AsyncClient(transport=transport) as client:
            with patch.object(self.ledger, 'reserve', side_effect=delayed_reservation):
                with self.assertRaisesRegex(BudgetDenied, 'billing_contract_invalid'):
                    await client.post('http://127.0.0.1:9999/v1/chat/completions', json={'model':'fake','messages':[]})
        self.assertEqual(seen, [])
        rows = self.ledger.report()['attempts']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['state'], 'unknown')
        self.assertEqual(self.ledger.report()['overall']['today']['exposure'], 90)


if __name__ == '__main__': unittest.main()
