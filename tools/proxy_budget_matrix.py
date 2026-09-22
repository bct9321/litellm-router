"""Independent real-proxy budget scopes and synchronized two-worker admission proof."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def main():
    import httpx
    import yaml
    from router.spend_ledger import Ledger
    from router.cost_policy import policy_revision
    out=ROOT/'outputs'/'budget-matrix'/uuid.uuid4().hex
    out.mkdir(parents=True)
    attempts=[]
    classifier_attempts=[]
    arrived=threading.Event()
    release=threading.Event()
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path=='/decisions':
                classifier_attempts.append(body)
                encoded=json.dumps({'answers':{'model':{'choice':'GENERAL_EFFICIENT'}},'usage':{'cost':0.00000001}}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(encoded)))
                self.end_headers();self.wfile.write(encoded)
                return
            attempts.append(body)
            if body['model']=='free-fixture':
                encoded=json.dumps({'error':{'message':'free fixture unavailable'},'usage':{'cost':0}}).encode()
                self.send_response(503)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(encoded)))
                self.end_headers();self.wfile.write(encoded)
                return
            if body['messages'][0]['content']=='held':
                arrived.set()
                if not release.wait(30): raise RuntimeError('Test release barrier timed out')
            answer={'id':'fixture','object':'chat.completion','created':1,'model':body['model'],
                'choices':[{'index':0,'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2,'cost':0.00000002}}
            encoded=json.dumps(answer).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    server=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    children=[]
    logs=[]
    def setup(name,scope=None):
        folder=out/name; folder.mkdir()
        limits={'daily':1000,'monthly':1000,'request':1000,'models':{'m':{'daily':1000,'monthly':1000},'other':{'daily':1000,'monthly':1000}}}
        if scope=='request': limits['request']=50
        elif scope in ('overall-daily','overall-monthly'): limits[scope.split('-')[1]]=100
        elif scope in ('model-daily','model-monthly'): limits['models']['m'][scope.split('-')[1]]=100
        now=datetime.now(timezone.utc)
        contract={'kind':'loopback-fixed-bound','canonical':'m','origin':f'http://127.0.0.1:{server.server_port}',
            'path':'/v1/chat/completions','input_nanos_per_token':0,'output_nanos_per_token':0,
            'fixed_overhead_nanos':60,'max_output_tokens':8,'valid_from':(now-timedelta(days=1)).isoformat(),
            'expires_at':(now+timedelta(days=1)).isoformat(),'revision':'fixture-v1','evidence_ref':'tools/proxy_budget_matrix.py',
            'supported_surfaces':['text-chat'],'final_usage_rule':'complete-response-cost'}
        candidate={'alias':'GENERAL_CAPABLE','canonical':'m','capabilities':['general'],'free':False,'contract':'c','deployment_ids':['d']}
        policy={'ledger':str(folder/'spend.sqlite'),'limits':limits,'contracts':{'c':contract},
            'deployments':{'d':{'alias':'direct','provider_model':'fixture','contract':'c','capabilities':['general'],'free':False}},
            'routes':{'jev':{'required_capabilities':['general'],'candidates':[candidate]},
                      'direct':{'required_capabilities':['general'],'candidates':[dict(candidate,alias='direct')]}}}
        config={'model_list':[{'model_name':'direct','model_info':{'id':'d'},'litellm_params':{'model':'openai/fixture',
            'api_base':contract['origin']+'/v1','api_key':'fake','max_retries':0}}],
            'litellm_settings':{'telemetry':False,'num_retries':0,'callbacks':['router.cost_guard.proxy_handler_instance']},
            'router_settings':{'num_retries':0},'general_settings':{'disable_spend_logs':True}}
        (folder/'proxy.yaml').write_text(yaml.safe_dump(config),encoding='utf-8')
        (folder/'policy.json').write_text(json.dumps(policy),encoding='utf-8')
        ledger=Ledger(policy['ledger'],limits,policy_revision=policy_revision(policy))
        if scope and scope!='request':
            model='other' if scope.startswith('overall') else 'm'
            ledger.reserve('seed','prior','%s'%model,'seed','seed',50,50)
            ledger.settle('seed','seed-final',50,'provider-reported')
        return folder,policy,ledger
    def start(folder, expected_failure=None):
        port=free_port()
        env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','TEMP','TMP','PATH') if k in os.environ}
        env.update(PYTHONPATH=os.pathsep.join((str(ROOT),str(ROOT/'router'))),PYTHONIOENCODING='utf-8',COST_ROUTER_CONFIG=str(folder/'policy.json'),OPENROUTER_API_KEY='fake-fixture',JEV_DECISIONS_URL=f'http://127.0.0.1:{server.server_port}/decisions',JEV_FAIL_TIER='GENERAL_EFFICIENT')
        log=(folder/f'proxy-{port}.log').open('w',encoding='utf-8'); logs.append(log)
        child=subprocess.Popen([sys.executable,str(ROOT/'tools/local_proxy_probe.py'),'--proxy',str(folder/'proxy.yaml'),'--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        children.append(child)
        endpoint=f'http://127.0.0.1:{port}'
        for _ in range(300):
            if child.poll() is not None:
                log.flush()
                if expected_failure:
                    diagnostic=Path(log.name).read_text(encoding='utf-8')
                    assert child.returncode!=0 and expected_failure in diagnostic,diagnostic[-4000:]
                    return child,None
                raise AssertionError(f'Proxy exited {child.returncode}: {log.name}')
            try:
                if httpx.get(endpoint+'/health/liveliness',timeout=1,trust_env=False).status_code==200:
                    assert expected_failure is None,'Invalid contract unexpectedly started'
                    return child,endpoint
            except httpx.HTTPError: pass
            time.sleep(.1)
        raise AssertionError('Proxy startup timed out')
    def post(url,text='normal',model='direct',max_tokens=8):
        return httpx.post(url+'/v1/chat/completions',json={'model':model,'messages':[{'role':'user','content':text}],'max_tokens':max_tokens},timeout=40,trust_env=False)
    def assert_denied(response):
        assert response.status_code==429,response.text
        detail=response.json()['error']['provider_specific_fields']
        assert detail['code']=='cost_budget_denied' and detail['reason'],response.text

    def stop(child):
        child.terminate()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill();child.wait(timeout=10)
    results=[]
    try:
        for scope in ('overall-daily','overall-monthly','model-daily','model-monthly','request'):
            folder,policy,ledger=setup(scope,scope)
            child,url=start(folder)
            before=len(attempts); response=post(url)
            assert_denied(response)
            assert len(attempts)==before,scope
            if scope=='request': assert 'Per-request ceiling' in response.text,response.text
            report=ledger.report()
            assert len(report['attempts'])==(0 if scope=='request' else 1)
            results.append({'scenario':scope,'status':response.status_code,'upstream_delta':0,'error':response.json()})
            stop(child)
        folder,policy,ledger=setup('workers','overall-daily')
        # No prior spend: 60 bound leaves 40, so exactly one overlapping attempt fits.
        # Setup seeded 50 for isolated scope cases; replace this scenario with a fresh ledger.
        policy['ledger']=str(folder/'workers.sqlite')
        (folder/'policy.json').write_text(json.dumps(policy),encoding='utf-8')
        ledger=Ledger(policy['ledger'],policy['limits'],policy_revision=policy_revision(policy))
        one,url1=start(folder); two,url2=start(folder)
        before=len(attempts)
        with ThreadPoolExecutor(max_workers=1) as pool:
            first=pool.submit(post,url1,'held')
            assert arrived.wait(15),'No first upstream dispatch'
            in_flight=ledger.report()
            assert in_flight['overall']['today']['exposure']==60,in_flight
            second=post(url2)
            assert_denied(second)
            assert len(attempts)==before+1
            release.set()
            accepted=first.result(timeout=15)
            assert accepted.status_code==200,accepted.text
        assert ledger.report()['overall']['today']['exposure']==20
        stop(one);stop(two)
        restarted,url3=start(folder)
        assert Ledger(policy['ledger'],policy['limits']).report()['overall']['today']['exposure']==20
        result=post(url3)
        assert result.status_code==200,result.text
        assert ledger.report()['overall']['today']['exposure']==40
        results.append({'scenario':'two-workers-and-restart','accepted':1,'denied':1,'inflight_exposure':60,'final_exposure_after_restart_request':40})
        stop(restarted)
        folder,policy,ledger=setup('classifier-and-solver-request')
        policy['ledger']=str(folder/'combined.sqlite')
        policy['limits']['request']=125
        policy['limits']['models'].update({'free':{'daily':0,'monthly':0},'classifier':{'daily':1000,'monthly':1000}})
        policy['contracts']['c'].update(output_nanos_per_token=30,fixed_overhead_nanos=0)
        free=dict(policy['contracts']['c'],canonical='free',output_nanos_per_token=0)
        policy['contracts']['free']=free
        policy['classifier']=dict(free,canonical='classifier',path='/decisions',supported_surfaces=['decisions'],provider_model='typesafe/jev-1.13',max_output_tokens=16,fixed_overhead_nanos=10)
        policy['deployments']['f']={'alias':'free','provider_model':'free-fixture','contract':'free','capabilities':['general'],'free':True}
        free_candidate={'alias':'GENERAL_EFFICIENT','canonical':'free','capabilities':['general'],'free':True,'contract':'free','deployment_ids':['f']}
        paid_candidate=policy['routes']['jev']['candidates'][0]
        policy['routes']['jev']['candidates']=[free_candidate,paid_candidate]
        policy['routes']['free']={'required_capabilities':['general'],'candidates':[dict(free_candidate,alias='free'),dict(paid_candidate,alias='direct')]}
        config=yaml.safe_load((folder/'proxy.yaml').read_text(encoding='utf-8'))
        config['model_list'].extend([
            {'model_name':'free','model_info':{'id':'f'},'litellm_params':{'model':'openai/free-fixture','api_base':free['origin']+'/v1','api_key':'fake','max_retries':0}},
            {'model_name':'jev','model_info':{'id':'jev-id'},'litellm_params':{'model':'auto_router/complexity_router','complexity_router_config':{
                'classifier_type':'custom','classifier_plugin':'jev_classifier.jev_classifier',
                'tier_definitions':[{'name':'GENERAL_EFFICIENT','description':'free'},{'name':'GENERAL_CAPABLE','description':'paid'}],
                'tiers':{'GENERAL_EFFICIENT':'free','GENERAL_CAPABLE':'direct'},'fallback_tier':'GENERAL_EFFICIENT'}}}])
        config['router_settings']['fallbacks']=[{'jev':['direct']},{'free':['direct']}]
        (folder/'proxy.yaml').write_text(yaml.safe_dump(config),encoding='utf-8')
        (folder/'policy.json').write_text(json.dumps(policy),encoding='utf-8')
        ledger=Ledger(policy['ledger'],policy['limits'],policy_revision=policy_revision(policy))
        child,url=start(folder)
        before=len(attempts);before_classifier=len(classifier_attempts)
        combined=post(url,'combined','jev',4)
        assert_denied(combined)
        assert 'Per-request ceiling exceeded' in combined.text,combined.text
        assert len(classifier_attempts)==before_classifier+1
        assert [r['model'] for r in attempts[before:]]==['free-fixture'],attempts[before:]
        rows=ledger.report()['attempts']
        assert {row['model'] for row in rows}=={'free','classifier'},rows
        assert len({row['request_id'] for row in rows})==1,rows
        assert next(row for row in rows if row['kind']=='classifier')['reported']==10,rows
        assert all(row['free'] for row in classifier_attempts[-1]['state']['eligible_models'])
        results.append({'scenario':'classifier-plus-solver-request-ceiling','request_limit':125,'classifier_final':10,'paid_bound':120,'paid_upstream_delta':0,'status':combined.status_code})
        stop(child)
        for invalid in ('missing-price','stale-price'):
            folder,policy,ledger=setup(invalid)
            if invalid=='missing-price':
                del policy['contracts']['c']['output_nanos_per_token']
                diagnostic="'output_nanos_per_token' is a required property"
            else:
                policy['contracts']['c']['expires_at']='2000-01-01T00:00:00+00:00'
                diagnostic='billing_contract_invalid'
            (folder/'policy.json').write_text(json.dumps(policy),encoding='utf-8')
            before=len(attempts)
            child,_=start(folder,expected_failure=diagnostic)
            assert len(attempts)==before
            results.append({'scenario':invalid,'startup_exit':child.returncode,'diagnostic':diagnostic,'upstream_delta':0})
        folder,policy,ledger=setup('crash-recovery')
        policy['limits']['daily']=100
        policy['ledger']=str(folder/'crash.sqlite')
        (folder/'policy.json').write_text(json.dumps(policy),encoding='utf-8')
        ledger=Ledger(policy['ledger'],policy['limits'],policy_revision=policy_revision(policy))
        arrived.clear();release.clear()
        child,url=start(folder)
        before=len(attempts)
        with ThreadPoolExecutor(max_workers=1) as pool:
            flight=pool.submit(post,url,'held')
            assert arrived.wait(15),'Crash fixture did not dispatch'
            assert ledger.report()['overall']['today']['exposure']==60
            child.kill();child.wait(timeout=10)
            release.set()
            try: flight.result(timeout=10)
            except httpx.HTTPError: pass
        recovered,url=start(folder)
        report=ledger.report()
        assert report['overall']['today']['exposure']==60,report
        denied=post(url)
        assert_denied(denied)
        assert len(attempts)==before+1
        results.append({'scenario':'crash-midflight-restart','retained_exposure':60,'upstream_delta_after_restart':0})
        stop(recovered)
        proof={'result':'PASS','python':sys.version,'litellm':importlib.metadata.version('litellm'),'scenarios':results,
            'upstream_attempts':len(attempts),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'router/cost_guard.py',ROOT/'router/cost_transport.py',ROOT/'router/spend_ledger.py',ROOT/'router/cost_policy.py',ROOT/'router/jev_classifier.py',ROOT/'tools/local_proxy_probe.py']}}
        proof['configuration_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*out.rglob('policy.json'),*out.rglob('proxy.yaml')]}
        (out/'proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
        print(json.dumps({'result':'PASS','proof':str(out/'proof.json'),'scenarios':len(results)}))
    finally:
        release.set()
        for child in children:
            if child.poll() is None: stop(child)
        for log in logs: log.close()
        server.shutdown();server.server_close()

if __name__=='__main__': main()
