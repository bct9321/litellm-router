import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from router.jev_classifier import OpenRouterJevClassifier
from router.spend_ledger import BudgetDenied


def fixture(folder):
    contract = dict(provider_model='typesafe/jev-1.13', alias='jev', kind='loopback-fixed-bound', origin='http://127.0.0.1:9', path='/decisions',
        canonical='jev', input_nanos_per_token=1, output_nanos_per_token=1, fixed_overhead_nanos=0,
        max_output_tokens=16, valid_from='2020-01-01T00:00:00Z', expires_at='2099-01-01T00:00:00Z',
        revision='fixture-v1', evidence_ref='local-test', supported_surfaces=['decisions'], final_usage_rule='complete-response-cost')
    solver = dict(contract, canonical='paid', path='/v1/chat/completions', supported_surfaces=['text-chat'])
    config = dict(ledger=str(Path(folder)/'ledger.sqlite'), limits=dict(daily=100000,monthly=100000,request=100000,
        models={name:dict(daily=100000,monthly=100000) for name in ('jev','paid','free')}),
        classifier=contract, contracts={'paid':solver}, routes={'jev':{'candidates':[
        dict(alias='GENERAL_EFFICIENT',canonical='free',capabilities=['general'],free=True),
        dict(alias='GENERAL_CAPABLE',canonical='paid',capabilities=['general'],free=False,contract='paid')]}})
    config['contracts']['free']=dict(solver, canonical='free', input_nanos_per_token=0, output_nanos_per_token=0)
    config['deployments']={name:dict(alias=name,provider_model=name,contract=name,capabilities=['general'],free=(name=='free')) for name in ('free','paid')}
    for row in config['routes']['jev']['candidates']:
        key='free' if row['free'] else 'paid'
        row['contract']=key; row['deployment_ids']=[key]
    path=Path(folder)/'config.json'; path.write_text(json.dumps(config))
    return path, config

class Controls(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, handler, mutate=None):
        with tempfile.TemporaryDirectory() as folder:
            path, config=fixture(folder)
            if mutate:
                mutate(config); path.write_text(json.dumps(config))
            real=httpx.AsyncClient
            with patch.dict(os.environ, COST_ROUTER_CONFIG=str(path), OPENROUTER_API_KEY='fixture', JEV_DECISIONS_URL='https://invalid.example/leak', JEV_MODEL='unpriced-model'), patch('router.jev_classifier.httpx.AsyncClient',side_effect=lambda **kw:real(transport=httpx.MockTransport(handler),**kw)):
                classifier=OpenRouterJevClassifier()
                from router.cost_policy import policy_revision
                from router.cost_transport import register_request_context
                trusted = register_request_context('jev', {'messages':[{'role':'user','content':'hello'}]}, [], ['free','paid'], policy_revision(classifier.cost_config))
                self.request_id = trusted['id']
                context={'raw_messages':[{'role':'user','content':'hello'}], 'metadata':{'_cost_request':self.request_id,'_cost_request_payload':{'messages':[{'role':'user','content':'hello'}]}}}
                diagnostics={}
                try:
                    result=await classifier.classify(context,diagnostics=diagnostics)
                except asyncio.CancelledError:
                    result='cancelled'
                return result, diagnostics, classifier.accounting.ledger.report()

    async def test_free_first_and_exact_classifier_wire_contract(self):
        seen=[]
        def handler(request):
            body=json.loads(request.content); seen.append((request,body))
            return httpx.Response(200,json={'answers':{'model':{'choice':'GENERAL_EFFICIENT'}},'usage':{'cost':0}})
        result,diag,_=await self.run_case(handler)
        self.assertTrue(diag['ok']); self.assertEqual(result,'GENERAL_EFFICIENT')
        request,body=seen[0]
        self.assertEqual(str(request.url),'http://127.0.0.1:9/decisions')
        self.assertEqual(body['max_tokens'],16)
        self.assertEqual(body['model'],'typesafe/jev-1.13')
        self.assertEqual([r['alias'] for r in body['state']['eligible_models']],['GENERAL_EFFICIENT'])

    async def test_cancel_marks_unknown_and_preserves_shared_request(self):
        async def handler(request): raise asyncio.CancelledError()
        result,_,report=await self.run_case(handler)
        self.assertEqual(result,'cancelled')
        attempt=report['attempts'][0]
        self.assertEqual(attempt['request_id'],self.request_id)
        self.assertEqual(attempt['state'],'unknown')
        self.assertGreater(report['overall']['today']['exposure'],0)

    async def test_classifier_charge_rechecks_request_capacity(self):
        seen=[]
        def configure(config):
            config['limits']['request']=2000
            config['routes']['jev']['candidates'].pop(0)
            config['contracts']['paid']['fixed_overhead_nanos']=1100
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json={'answers':{'model':{'choice':'GENERAL_CAPABLE'}},'usage':{'cost':0.0000009}})
        with self.assertRaises(BudgetDenied):
            await self.run_case(handler,configure)
        self.assertEqual(len(seen),1)

    async def test_malformed_choice_cannot_select_paid_while_free_exists(self):
        def handler(request):
            return httpx.Response(200,json={'answers':{'model':{'choice':'GENERAL_CAPABLE'}},'usage':{'cost':0}})
        result,diag,_=await self.run_case(handler)
        self.assertFalse(diag['ok'])
        self.assertEqual(result,'GENERAL_EFFICIENT')

    async def test_expired_classifier_contract_never_connects(self):
        def handler(request): self.fail('must never connect')
        with self.assertRaises(ValueError):
            await self.run_case(handler,lambda c:c['classifier'].update(expires_at='2020-01-02T00:00:00Z'))

    async def test_live_classifier_contract_never_connects(self):
        def handler(request): self.fail('must never connect')
        with self.assertRaises(ValueError):
            await self.run_case(handler,lambda c:c['classifier'].update(origin='https://openrouter.ai'))

    async def test_missing_jev_route_rejected_before_connection(self):
        def handler(request): self.fail('must never connect')
        with self.assertRaises(ValueError):
            await self.run_case(handler, lambda c:c['routes'].clear())

    async def test_classifier_contract_expiring_during_reservation_never_connects(self):
        import time
        from datetime import datetime, timezone, timedelta
        from router.cost_policy import policy_revision
        from router.cost_transport import register_request_context
        with tempfile.TemporaryDirectory() as folder:
            path, config = fixture(folder)
            seen = []
            def handler(request):
                seen.append(request)
                return httpx.Response(200, json={'answers':{'model':{'choice':'GENERAL_EFFICIENT'}},'usage':{'cost':0}})
            real = httpx.AsyncClient
            with patch.dict(os.environ, COST_ROUTER_CONFIG=str(path), OPENROUTER_API_KEY='fixture'), patch(
                    'router.jev_classifier.httpx.AsyncClient', side_effect=lambda **kw:real(transport=httpx.MockTransport(handler),**kw)):
                classifier = OpenRouterJevClassifier()
                payload = {'messages':[{'role':'user','content':'hello'}]}
                trusted = register_request_context('jev', payload, [], ['free','paid'], policy_revision(config))
                context = {'raw_messages':payload['messages'], 'metadata':{'_cost_request':trusted['id']}}
                reserve = classifier.accounting.ledger.reserve
                def delayed_reservation(*args, **kwargs):
                    result = reserve(*args, **kwargs)
                    time.sleep(0.6)
                    return result
                classifier.accounting.contract['expires_at'] = (datetime.now(timezone.utc) + timedelta(seconds=0.5)).isoformat()
                with patch.object(classifier.accounting.ledger, 'reserve', side_effect=delayed_reservation):
                    result = await classifier.classify(context)
                self.assertEqual(result, 'GENERAL_EFFICIENT')
                self.assertEqual(seen, [])
                report = classifier.accounting.ledger.report()
                self.assertEqual(len(report['attempts']), 1)
                self.assertEqual(report['attempts'][0]['state'], 'unknown')
                self.assertGreater(report['overall']['today']['exposure'], 0)

if __name__=='__main__': unittest.main()
