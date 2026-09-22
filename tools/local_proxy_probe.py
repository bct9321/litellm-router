"""Run the pinned, real proxy against loopback-only deterministic HTTP upstreams."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


def proxy_child(config, port):
    # Defense in depth: no inherited credentials, dotenv loading, telemetry or
    # external socket connections. This changes network access, not proxy hooks.
    def local_only(event, args):
        if event == 'socket.connect':
            address = args[1]
            if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
                raise OSError('Local integration forbids external sockets')
    sys.addaudithook(local_only)
    with socket.socket() as check:
        try:
            check.connect(('192.0.2.1', 1))
        except OSError as exc:
            if 'forbids external sockets' not in str(exc):
                raise
        else:
            raise AssertionError('External network guard did not reject the socket')
    os.environ.update(LITELLM_MODE='PRODUCTION', LITELLM_LOCAL_MODEL_COST_MAP='True',
                      CUSTOM_TIKTOKEN_CACHE_DIR=str(ROOT / 'outputs/token-cache'),
                      DO_NOT_TRACK='1')
    from litellm.proxy.proxy_cli import run_server
    sys.argv = ['litellm', '--config', str(config), '--host', '127.0.0.1', '--port', str(port)]
    run_server()


def main():
    import httpx
    import yaml
    sys.path.insert(0, str(ROOT))
    from router.spend_ledger import Ledger
    out = ROOT / 'outputs/local-proxy' / ('run-' + uuid.uuid4().hex)
    out.mkdir(parents=True, exist_ok=True)
    attempts = []
    classifier_attempts = []
    quota_fetches = []
    quota_exhausted = [True]
    quota_available = [True]
    ledger_path = out / ('spend-' + uuid.uuid4().hex + '.sqlite')
    limits = {'daily': 10000, 'monthly': 12000, 'request': 10000,
              'models': {'canonical-fake': {'daily': 10000, 'monthly': 12000}}}
    ledger = Ledger(str(ledger_path), limits)
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path.endswith('/key'):
                quota_fetches.append(time.time())
                if not quota_available[0]:
                    self.send_response(503)
                    self.end_headers()
                    return
                body = json.dumps({'data': {'free_model_daily_requests': {
                    'used': 10 if quota_exhausted[0] else 0, 'limit': 10,
                    'remaining': 0 if quota_exhausted[0] else 10}}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path.endswith('/decisions'):
                classifier_attempts.append(request)
                if len(classifier_attempts) >= 2:
                    body = json.dumps({'error': {'message': 'fixture classifier failure'}}).encode()
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                body = json.dumps({'answers': {'model': {'choice': 'GENERAL_EFFICIENT'}},
                                   'usage': {'cost': 0.00000001}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            attempts.append(request)
            if request['model'] == 'fake-free':
                body = json.dumps({'error': {'message': 'fixture fallback'}, 'usage': {'cost': 0}}).encode()
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if request['model'] == 'fake-paid-fail':
                body = json.dumps({'error': {'message': 'fixture emergency fallback'}, 'usage': {'cost': 0.00000001}}).encode()
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if request.get('messages', [{}])[0].get('content', '').startswith('multi-worker'):
                time.sleep(0.4)
            result = {'id': 'fake-' + str(len(attempts)), 'object': 'chat.completion',
                      'created': 1, 'model': request['model'],
                      'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'local proof'},
                                   'finish_reason': 'stop'}],
                      'usage': {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6, 'cost': 0.00000002}}
            body = json.dumps(result).encode()
            self.send_response(200)
            if request.get('stream'):
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                chunk = {'id': result['id'], 'object': 'chat.completion.chunk', 'created': 1,
                         'model': request['model'], 'choices': [{'index':0, 'delta':{'content':'local proof'}, 'finish_reason':None}]}
                if request['messages'][0]['content'] == 'partial-usage':
                    chunk['usage'] = dict(result['usage'], cost=0.00000001)
                try:
                    self.wfile.write(b'data: ' + json.dumps(chunk).encode() + b'\n\n')
                    self.wfile.flush()
                    if request['messages'][0]['content'] in ('cancel', 'partial-usage'):
                        time.sleep(0.5)
                        return
                    chunk['choices'] = []
                    chunk['usage'] = result['usage']
                    self.wfile.write(b'data: ' + json.dumps(chunk).encode() + b'\n\ndata: [DONE]\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    config = out / 'proxy.yaml'
    budget_config = out / 'budget.json'
    limits['models']['canonical-free'] = {'daily': 0, 'monthly': 0}
    limits['models']['canonical-first'] = {'daily': 10000, 'monthly': 12000}
    limits['models']['canonical-emergency'] = {'daily': 10000, 'monthly': 12000}
    limits['models']['canonical-jev'] = {'daily': 10000, 'monthly': 12000}
    # Both parent and proxy use the same policy; recreate before any attempts.
    ledger_path = out / ('spend-' + uuid.uuid4().hex + '.sqlite')
    ledger = Ledger(str(ledger_path), limits)
    budget_config.write_text(json.dumps({'ledger': str(ledger_path), 'limits': limits,
        'contracts': {'fake-model': {'alias':'local-paid', 'kind': 'loopback-fixed-bound', 'canonical': 'canonical-fake',
            'origin': f'http://127.0.0.1:{upstream.server_port}', 'input_nanos_per_token': 1, 'output_nanos_per_token': 2, 'fixed_overhead_nanos': 1, 'max_output_tokens': 32},
            'fake-free': {'alias':'local-free', 'kind':'loopback-fixed-bound', 'canonical':'canonical-free',
             'origin':f'http://127.0.0.1:{upstream.server_port}', 'input_nanos_per_token':0, 'output_nanos_per_token':0, 'max_output_tokens':32},
            'fake-paid-fail': {'alias':'local-first', 'kind':'loopback-fixed-bound','canonical':'canonical-first',
             'origin':f'http://127.0.0.1:{upstream.server_port}', 'input_nanos_per_token':1, 'output_nanos_per_token':2, 'fixed_overhead_nanos':1, 'max_output_tokens':32},
            'fake-emergency': {'alias':'local-emergency', 'kind':'loopback-fixed-bound','canonical':'canonical-emergency',
             'origin':f'http://127.0.0.1:{upstream.server_port}', 'input_nanos_per_token':1, 'output_nanos_per_token':2, 'fixed_overhead_nanos':1, 'max_output_tokens':32}},
        'classifier': {'alias':'jev', 'kind':'loopback-fixed-bound','canonical':'canonical-jev',
            'origin':f'http://127.0.0.1:{upstream.server_port}', 'input_nanos_per_token':1,
            'output_nanos_per_token':1, 'fixed_overhead_nanos':1, 'max_output_tokens':16},
        'routes': {'cost-aware': {'required_capabilities':['general'], 'candidates':[
            {'alias':'local-free','canonical':'canonical-free','capabilities':['general'],'free':True},
            {'alias':'local-paid','contract':'fake-model','canonical':'canonical-fake','capabilities':['general'],'free':False}]},
            'emergency-route': {'required_capabilities':['general'], 'candidates':[
            {'alias':'local-first','contract':'fake-paid-fail','canonical':'canonical-first','capabilities':['general'],'free':False}]},
            'jev': {'required_capabilities':['general'], 'candidates':[
            {'alias':'GENERAL_EFFICIENT','canonical':'canonical-free','capabilities':['general'],'free':True},
            {'alias':'GENERAL_CAPABLE','contract':'fake-model','canonical':'canonical-fake','capabilities':['general'],'free':False},
            {'alias':'REASONING_CAPABLE','contract':'fake-model','canonical':'canonical-fake','capabilities':['vision'],'free':False}]},
            'unpriced-route': {'required_capabilities':['general'], 'candidates':[
            {'alias':'unpriced-paid','canonical':'canonical-fake','capabilities':['general'],'free':False}]}}}), encoding='utf-8')
    config.write_text(yaml.safe_dump({
        'model_list': [{'model_name': 'jev', 'litellm_params': {
            'model': 'auto_router/complexity_router',
            'complexity_router_config': {'classifier_type': 'custom', 'classifier_plugin': 'router.jev_classifier.jev_classifier',
                'tier_definitions': [{'name':'GENERAL_EFFICIENT','description':'local free'},
                                     {'name':'GENERAL_CAPABLE','description':'local paid'}],
                'tiers': {'GENERAL_EFFICIENT':'local-free', 'GENERAL_CAPABLE':'local-paid'},
                'fallback_tier':'GENERAL_EFFICIENT'}}},
            {'model_name': 'local-paid', 'litellm_params': {
            'model': 'openai/fake-model', 'api_base': f'http://127.0.0.1:{upstream.server_port}/v1',
            'api_key': 'fake-local-key', 'max_retries': 0}},
            {'model_name':'local-free', 'litellm_params':{'model':'openai/fake-free',
                'api_base':f'http://127.0.0.1:{upstream.server_port}/v1', 'api_key':'fake-local-key', 'max_retries':0}},
            {'model_name':'quota-free', 'litellm_params':{'model':'openai/fake-free',
                'api_base':f'http://127.0.0.1:{upstream.server_port}/v1', 'api_key':'fake-local-key', 'max_retries':0}},
            {'model_name':'local-first', 'litellm_params':{'model':'openai/fake-paid-fail',
                'api_base':f'http://127.0.0.1:{upstream.server_port}/v1', 'api_key':'fake-local-key', 'max_retries':0}},
            {'model_name':'local-emergency', 'litellm_params':{'model':'openai/fake-emergency',
                'api_base':f'http://127.0.0.1:{upstream.server_port}/v1', 'api_key':'fake-local-key', 'max_retries':0}}],
        'litellm_settings': {'telemetry': False, 'num_retries': 0, 'callbacks': [
            'router.openrouter_quota_guard.proxy_handler_instance',
            'router.cost_guard.proxy_handler_instance']},
        'router_settings': {'num_retries': 0, 'fallbacks': [{'jev':['local-free']}, {'local-free':['local-paid']}, {'local-first':['local-emergency']}, {'quota-vision':['local-paid']}]},
        'general_settings': {'disable_spend_logs': True},
    }), encoding='utf-8')
    # Bind fixtures to the same complete policy and callback entry points used
    # by the working router. Every model gets a stable deployment identity.
    policy = json.loads(budget_config.read_text(encoding='utf-8'))
    proxy_yaml = yaml.safe_load(config.read_text(encoding='utf-8'))
    now = datetime.now(timezone.utc)
    for row in [*policy['contracts'].values(), policy['classifier']]:
        row.update(path='/v1/chat/completions', revision='local-fixture-v1',
                   valid_from=(now-timedelta(days=1)).isoformat(),
                   expires_at=(now+timedelta(days=1)).isoformat(),
                   evidence_ref='tools/local_proxy_probe.py', supported_surfaces=['text-chat'],
                   final_usage_rule='complete-response-cost')
    policy['classifier'].update(path='/decisions', supported_surfaces=['decisions'], provider_model='typesafe/jev-1.13')
    policy['deployments'] = {}
    import copy
    shared = copy.deepcopy(proxy_yaml['model_list'][1])
    shared['model_name'] = 'local-shared'
    proxy_yaml['model_list'].append(shared)
    for row in proxy_yaml['model_list']:
        alias = row['model_name']
        row['model_info'] = {'id': alias+'-id'}
        if alias == 'jev':
            continue
        provider = row['litellm_params']['model'].removeprefix('openai/')
        policy['deployments'][alias+'-id'] = {'alias': alias, 'provider_model': provider,
            'contract': provider, 'capabilities': ['general'], 'free': provider == 'fake-free'}
    # vision is a capability requirement on text here; unsupported image billing
    # is checked separately, rather than pretending pixel billing is bounded.
    vision = copy.deepcopy(proxy_yaml['model_list'][2])
    vision['model_name'] = 'quota-vision'
    vision['model_info'] = {'id': 'quota-vision-id'}
    proxy_yaml['model_list'].append(vision)
    policy['deployments']['quota-vision-id'] = {'alias': 'quota-vision', 'provider_model': 'fake-free',
        'contract': 'fake-free', 'capabilities': ['vision'], 'free': True}
    def candidate(alias, tier=None):
        dep = policy['deployments'][alias+'-id']
        return {'alias': tier or alias, 'canonical': policy['contracts'][dep['contract']]['canonical'],
                'capabilities': dep['capabilities'], 'free': dep['free'],
                'contract': dep['contract'], 'deployment_ids': [alias+'-id']}
    policy['routes'] = {alias: {'required_capabilities': dep['capabilities'], 'candidates': [candidate(alias)]}
                        for dep in policy['deployments'].values() for alias in [dep['alias']]}
    policy['routes']['cost-aware'] = {'required_capabilities': ['general'],
                                    'candidates': [candidate('local-free'), candidate('local-paid')]}
    policy['routes']['local-free']['candidates'].append(candidate('local-paid'))
    policy['routes']['quota-free']['candidates'].append(candidate('local-paid'))
    policy['routes']['local-first']['candidates'].append(candidate('local-emergency'))
    policy['routes']['quota-vision']['candidates'].append(candidate('local-paid'))
    policy['routes']['jev'] = {'required_capabilities': ['general'], 'candidates': [
        candidate('local-free', 'GENERAL_EFFICIENT'), candidate('local-paid', 'GENERAL_CAPABLE')]}
    proxy_yaml['litellm_settings']['callbacks'] = ['cost_guard.proxy_handler_instance',
                                                  'openrouter_quota_guard.proxy_handler_instance']
    proxy_yaml['model_list'][0]['litellm_params']['complexity_router_config']['classifier_plugin'] = 'jev_classifier.jev_classifier'
    budget_config.write_text(json.dumps(policy, indent=2), encoding='utf-8')
    config.write_text(yaml.safe_dump(proxy_yaml), encoding='utf-8')
    env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH') if k in os.environ}
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ROOT/'router')))
    env['PYTHONIOENCODING'] = 'utf-8'
    env['COST_ROUTER_CONFIG'] = str(budget_config)
    env['OPENROUTER_API_KEY'] = 'fixture-key'
    env['OPENROUTER_KEY_URL'] = f'http://127.0.0.1:{upstream.server_port}/key'
    env['OPENROUTER_QUOTA_ROUTE_MAP'] = json.dumps({'quota-free': 'local-paid', 'quota-vision': 'local-paid', 'jev': 'jev'})
    env['OPENROUTER_QUOTA_CACHE_SECONDS'] = '1'
    env['OPENROUTER_QUOTA_FAIL_OPEN'] = 'false'
    env['JEV_DECISIONS_URL'] = f'http://127.0.0.1:{upstream.server_port}/decisions'
    env['JEV_FAIL_TIER'] = 'GENERAL_EFFICIENT'
    with (out / 'proxy.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--proxy', str(config), '--port', str(port)],
                                   cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=10) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Proxy exited; inspect outputs/local-proxy/proxy.log')
                    try:
                        if client.get('/health/liveliness').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError('Proxy startup timed out')
                response = client.post('/v1/chat/completions', json={
                    'model': 'cost-aware', 'messages': [{'role': 'user', 'content': 'local fixture'}], 'max_tokens': 8})
                response.raise_for_status()
                assert response.json()['choices'][0]['message']['content'] == 'local proof'
                assert [r['model'] for r in attempts] == ['fake-free', 'fake-model']
                first_attempts = ledger.report()['attempts'][:2]
                assert [row['alias'] for row in first_attempts] == ['local-free', 'local-paid']
                assert ledger.report()['overall']['today']['exposure'] == 20, 'Real dispatch was not accounted'
                shared_response = client.post('/v1/chat/completions', json={
                    'model':'local-shared', 'messages':[{'role':'user','content':'shared alias'}], 'max_tokens':4})
                shared_response.raise_for_status()
                last = ledger.report()['attempts'][-1]
                assert last['alias'] == 'local-shared' and last['model'] == 'canonical-fake'
                assert last['provider_model'] == 'fake-model' and last['deployment_id'] == 'local-shared-id'
                missing_cap = client.post('/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'missing output cap'}]})
                missing_cap.raise_for_status()
                assert attempts[-1]['max_tokens'] == 32
                quota_response = client.post('/v1/chat/completions', json={
                    'model':'quota-free', 'messages':[{'role':'user','content':'quota rewrite'}], 'max_tokens':4})
                quota_response.raise_for_status()
                assert attempts[-1]['model'] == 'fake-model', 'Exhausted quota did not rewrite the free alias'
                assert ledger.report()['attempts'][-1]['entry_alias'] == 'quota-free'
                before_incompatible = len(attempts)
                incompatible = client.post('/v1/chat/completions', json={
                    'model':'quota-vision', 'messages':[{'role':'user','content':'requires vision'}], 'max_tokens':4})
                assert incompatible.status_code >= 400 and 'capabil' in incompatible.text.lower(), incompatible.text
                assert len(attempts) == before_incompatible
                quota_exhausted[0] = False
                time.sleep(5.1)  # The production quota cache has a five-second minimum.
                before_fallback = len(attempts)
                incompatible_fallback = client.post('/v1/chat/completions', json={
                    'model':'quota-vision', 'messages':[{'role':'user','content':'requires vision fallback'}], 'max_tokens':4})
                assert incompatible_fallback.status_code >= 400 and 'capabil' in incompatible_fallback.text.lower(), incompatible_fallback.text
                assert [item['model'] for item in attempts[before_fallback:]] == ['fake-free']
                jev_response = client.post('/v1/chat/completions', json={
                    'model':'jev', 'messages':[{'role':'user','content':'strict Jev local proof'}], 'max_tokens':4})
                jev_response.raise_for_status()
                assert classifier_attempts and classifier_attempts[-1]['state']['eligible_models']
                assert all('vision' not in row['capabilities'] for row in classifier_attempts[-1]['state']['eligible_models'])
                assert all(row['free'] for row in classifier_attempts[-1]['state']['eligible_models'])
                assert classifier_attempts[-1]['max_tokens'] == 16
                assert [item['model'] for item in attempts[-2:]] == ['fake-free', 'fake-model']
                classifier_row = [row for row in ledger.report()['attempts'] if row['model']=='canonical-jev'][-1]
                assert classifier_row['state'] == 'provider-reported'
                assert any(row['request_id']==classifier_row['request_id'] and row['model']=='canonical-fake' for row in ledger.report()['attempts'])
                jev_failure = client.post('/v1/chat/completions', json={
                    'model':'jev', 'messages':[{'role':'user','content':'classifier failure'}], 'max_tokens':4})
                jev_failure.raise_for_status()
                assert [item['model'] for item in attempts[-2:]] == ['fake-free', 'fake-model'], 'Classifier failure did not use the configured safe fallback'
                assert ledger.report()['overall']['today']['pending_or_unknown'] >= 1
                after_jev = ledger.report()['overall']['today']['exposure']
                with client.stream('POST', '/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'stream'}],
                    'stream':True, 'stream_options':{'include_usage':True}, 'max_tokens':8}) as stream:
                    stream.raise_for_status()
                    streamed = ''.join(stream.iter_text())
                assert 'local proof' in streamed
                assert ledger.report()['overall']['today']['exposure'] > after_jev
                with client.stream('POST', '/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'cancel'}],
                    'stream':True, 'max_tokens':8}) as stream:
                    stream.raise_for_status()
                    next(stream.iter_text())
                cancelled = ledger.report()['overall']['today']
                assert cancelled['pending_or_unknown'] >= 1 and cancelled['exposure'] > after_jev
                with client.stream('POST', '/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'partial-usage'}],
                    'stream':True, 'max_tokens':8}) as stream:
                    stream.raise_for_status()
                    partial = ''.join(stream.iter_text())
                assert 'local proof' in partial
                partial_row = ledger.report()['attempts'][-1]
                assert partial_row['state'] == 'unknown' and partial_row['reserved'] > 10
                emergency = client.post('/v1/chat/completions', json={
                    'model':'local-first', 'messages':[{'role':'user','content':'emergency'}], 'max_tokens':8})
                emergency.raise_for_status()
                assert [item['model'] for item in attempts[-2:]] == ['fake-paid-fail', 'fake-emergency']
                assert [row for row in ledger.report()['attempts'] if row['model']=='canonical-first'][-1]['reported'] == 10
                before_unpriced = len(attempts)
                unpriced = client.post('/v1/chat/completions', json={
                    'model':'unpriced-route', 'messages':[{'role':'user','content':'unknown price'}], 'max_tokens':4})
                assert unpriced.status_code >= 400 and len(attempts) == before_unpriced
                def concurrent_call(index):
                    with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=10) as worker:
                        result = worker.post('/v1/chat/completions', json={
                            'model':'local-paid', 'messages':[{'role':'user','content':f'concurrent-{index}'}], 'max_tokens':4})
                        return result.status_code
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert sorted(pool.map(concurrent_call, (1, 2))) == [200, 200]
                attempts_after_concurrency = len(attempts)
                assert attempts_after_concurrency >= 8
                # Stop and restart the pinned proxy against the same SQLite
                # ledger. Existing reservations and deduplication must survive.
                process.terminate()
                process.wait(timeout=10)
                quota_available[0] = False
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--proxy', str(config), '--port', str(port)],
                                           cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Restarted proxy exited; inspect outputs/local-proxy/proxy.log')
                    try:
                        if client.get('/health/liveliness').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                else:
                    raise RuntimeError('Restarted proxy startup timed out')
                before_quota_unknown = len(attempts)
                quota_unknown = client.post('/v1/chat/completions', json={
                    'model':'quota-free', 'messages':[{'role':'user','content':'stale quota'}], 'max_tokens':4})
                assert quota_unknown.status_code >= 400 and len(attempts) == before_quota_unknown
                restarted = client.post('/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'restart recovery'}], 'max_tokens':4})
                restarted.raise_for_status()
                before = len(attempts)
                denied = client.post('/v1/chat/completions', json={
                    'model':'local-paid', 'messages':[{'role':'user','content':'must be blocked'}], 'max_tokens':64})
                assert denied.status_code >= 400
                assert len(attempts) == before, 'Budget-denied request reached upstream'
                proof = {'litellm': importlib.metadata.version('litellm'), 'python': sys.version.split()[0], 'scenario': 'real-proxy-http-smoke',
                         'status': response.status_code, 'upstream_attempts': len(attempts),
                         'classifier_attempts': len(classifier_attempts), 'result': 'PASS',
                         'scenarios':['free-to-paid fallback', 'per-attempt settlement', 'stream final usage',
                                      'cancel retains bound', 'quota exhaustion rewrite', 'stale quota fails closed',
                                      'unconfigured alias refuses dispatch', 'emergency fallback', 'concurrent clients',
                                      'shared aliases and provider deployment attribution',
                                      'restart recovery', 'duplicate stream settlement', 'strict Jev selection',
                                      'classifier failure retains unknown reservation',
                                      'output cap enforced on wire', 'partial usage retains reservation',
                                      'incompatible quota target rejected', 'incompatible fallback rejected', 'output ceiling prevents dispatch'], 'ledger':str(ledger_path),
                         'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for directory in ('router','tools') for p in (ROOT/directory).glob('*.py')},
                         'policy_sha256': hashlib.sha256(budget_config.read_bytes()).hexdigest()}
                (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
                print(json.dumps(proof))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            upstream.shutdown()
            upstream.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proxy', type=Path)
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.proxy:
        proxy_child(args.proxy, args.port)
    else:
        main()
