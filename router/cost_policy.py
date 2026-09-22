"""Pure server-side candidate selection for cost-aware routes."""
from dataclasses import dataclass
from pathlib import Path

from router.spend_ledger import BudgetDenied

JEV_TIER_ALIASES = frozenset({
    'GENERAL_EFFICIENT', 'GENERAL_CAPABLE', 'REASONING_EFFICIENT', 'REASONING_CAPABLE',
    'AGENTIC_EFFICIENT', 'AGENTIC_CAPABLE', 'CODING_EFFICIENT', 'CODING_CAPABLE',
})


@dataclass(frozen=True)
class Candidate:
    alias: str
    canonical: str
    capabilities: frozenset[str]
    free: bool
    estimate: int | None
    bound: int | None


def validate_policy(config):
    """Execute the checked-in JSON schema before creating any strict guard."""
    try:
        from jsonschema import Draft202012Validator
        schema = __import__('json').loads((Path(__file__).with_name('cost-router.schema.json')).read_text(encoding='utf-8'))
        errors = sorted(Draft202012Validator(schema).iter_errors(config), key=lambda error: list(error.path))
    except ImportError as exc:
        raise ValueError('jsonschema is required for strict cost-aware mode') from exc
    if errors:
        first = errors[0]
        raise ValueError(f'Invalid cost-aware policy at {list(first.path)}: {first.message}')
    """Retain semantic cross-reference checks beyond JSON Schema."""
    if not isinstance(config, dict) or set(('ledger', 'limits', 'contracts', 'routes')) - set(config):
        raise ValueError('Cost-aware policy requires ledger, limits, contracts and routes')
    if not isinstance(config['ledger'], str) or not config['ledger']:
        raise ValueError('Cost-aware ledger path is required')
    limits = config['limits']
    if not isinstance(limits, dict) or not isinstance(limits.get('models'), dict):
        raise ValueError('Cost-aware limits require model limits')
    for name in ('daily', 'monthly', 'request'):
        if type(limits.get(name)) is not int or limits[name] < 0:
            raise ValueError(f'Cost-aware {name} limit must be a nonnegative integer')
    for canonical, cap in limits['models'].items():
        if not isinstance(canonical, str) or not isinstance(cap, dict) or any(type(cap.get(key)) is not int or cap[key] < 0 for key in ('daily', 'monthly')):
            raise ValueError('Every canonical model needs finite integer daily/monthly limits')
    for model, contract in config['contracts'].items():
        if not isinstance(model, str) or not isinstance(contract, dict):
            raise ValueError('Invalid billing contract')
        if set(('kind', 'canonical', 'origin', 'input_nanos_per_token', 'output_nanos_per_token', 'max_output_tokens')) - set(contract):
            raise ValueError(f'Incomplete billing contract for {model}')
        if contract['canonical'] not in limits['models']:
            raise ValueError(f'Billing contract {model} lacks canonical budget')
    routes = config.get('routes')
    if not isinstance(routes, dict) or 'jev' not in routes:
        raise ValueError('Strict cost-aware policy requires routes.jev')
    jev_route = routes.get('jev')
    if jev_route is not None:
        if not isinstance(jev_route, dict) or not isinstance(jev_route.get('candidates'), list):
            raise ValueError('The Jev route requires a candidate list')
        for candidate in jev_route['candidates']:
            if not isinstance(candidate, dict) or candidate.get('alias') not in JEV_TIER_ALIASES:
                raise ValueError('Jev candidates must use configured LiteLLM tier names')

    deployments = config['deployments']
    for identifier, deployment in deployments.items():
        contract = config['contracts'].get(deployment['contract'])
        if contract is None:
            raise ValueError(f'Deployment {identifier} has no billing contract')
        validate_contract(contract)
        if deployment['free'] and any(contract.get(k, 0) != 0 for k in ('input_nanos_per_token', 'output_nanos_per_token', 'fixed_overhead_nanos')):
            raise ValueError('Free deployments must have a verified zero-charge bound')
    for route in routes.values():
        for candidate in route['candidates']:
            for identifier in candidate['deployment_ids']:
                deployment = deployments.get(identifier)
                if deployment is None:
                    raise ValueError(f'Candidate references unknown deployment {identifier}')
                contract = config['contracts'][deployment['contract']]
                if candidate['canonical'] != contract['canonical'] or candidate['free'] != deployment['free']:
                    raise ValueError('Candidate accounting disagrees with deployment')
                if not set(candidate['capabilities']) <= set(deployment['capabilities']):
                    raise ValueError('Candidate advertises unsupported deployment capability')
                if candidate.get('contract', deployment['contract']) != deployment['contract']:
                    raise ValueError('Candidate billing contract disagrees with deployment')


def validate_contract(contract, surface='text-chat', now=None):
    """Only dated, complete loopback fixture bounds are currently supported."""
    from datetime import datetime, timezone
    from urllib.parse import urlsplit
    from router.spend_ledger import amount
    try:
        origin = urlsplit(contract['origin'])
        if (contract['kind'] != 'loopback-fixed-bound' or origin.scheme != 'http'
                or origin.hostname != '127.0.0.1' or not origin.port
                or origin.username or origin.password or origin.path or origin.query or origin.fragment):
            raise ValueError('unsupported endpoint')
        if (not isinstance(contract['path'], str) or not contract['path'].startswith('/')
                or '?' in contract['path'] or '#' in contract['path']):
            raise ValueError('invalid contract path')
        if not contract['revision'] or not contract['evidence_ref']:
            raise ValueError('missing evidence')
        if contract['final_usage_rule'] != 'complete-response-cost':
            raise ValueError('unsupported settlement contract')
        if surface not in contract['supported_surfaces']:
            raise ValueError('unsupported request surface')
        since = datetime.fromisoformat(contract['valid_from'].replace('Z', '+00:00'))
        until = datetime.fromisoformat(contract['expires_at'].replace('Z', '+00:00'))
        if since.tzinfo is None or until.tzinfo is None or not since <= (now or datetime.now(timezone.utc)) < until:
            raise ValueError('stale or future price')
        for key in ('input_nanos_per_token', 'output_nanos_per_token', 'max_output_tokens'):
            amount(contract[key])
        amount(contract.get('fixed_overhead_nanos', 0))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise BudgetDenied('billing_contract_invalid: missing, stale, or unsupported billing bound') from exc


# These are the complete request fields accepted by the local bounded adapter.
# Fields outside this list cannot silently add unbounded billable behavior.
CHAT_KEYS = frozenset({'model', 'messages', 'tools', 'tool_choice', 'parallel_tool_calls',
    'response_format', 'temperature', 'top_p', 'stop', 'n', 'logprobs', 'top_logprobs',
    'presence_penalty', 'frequency_penalty', 'seed', 'max_tokens', 'max_completion_tokens',
    'stream', 'stream_options', 'user'})


def normalize_request(contract, request):
    """Produce the exact supported body used for both reservation and dispatch."""
    import copy
    validate_contract(contract)
    if not isinstance(request, dict) or set(request) - CHAT_KEYS:
        raise BudgetDenied('unsupported_request_surface: only bounded text chat is supported')
    body = copy.deepcopy(request)
    if type(body.get('n', 1)) is not int or body.get('n', 1) != 1:
        raise BudgetDenied('unsupported_completion_count: exactly one completion is required')
    tools = body.get('tools', [])
    if not isinstance(tools, list) or any(not isinstance(tool, dict)
            or tool.get('type') != 'function' or not isinstance(tool.get('function'), dict)
            or set(tool) - {'type', 'function'} for tool in tools):
        raise BudgetDenied('unsupported_request_surface: provider-executed tools are not bounded')
    messages = body.get('messages', [])
    if not isinstance(messages, list):
        raise BudgetDenied('unsupported_request_surface: messages must be a list')
    for message in messages:
        if not isinstance(message, dict):
            raise BudgetDenied('unsupported_request_surface: malformed message')
        content = message.get('content')
        if content is not None and not isinstance(content, str):
            if not isinstance(content, list) or any(not isinstance(part, dict)
                    or set(part) - {'type', 'text'} or part.get('type') != 'text'
                    or not isinstance(part.get('text'), str) for part in content):
                raise BudgetDenied('unsupported_request_surface: image/audio/remote content is not bounded')
        if set(message) - {'role', 'content', 'name', 'tool_calls', 'tool_call_id', 'function_call'}:
            raise BudgetDenied('unsupported_request_surface: unsupported message fields')
    first, second = body.get('max_tokens'), body.get('max_completion_tokens')
    if first is not None and second is not None and first != second:
        raise BudgetDenied('conflicting_output_limits')
    cap = first if first is not None else second if second is not None else contract['max_output_tokens']
    if type(cap) is not int or cap < 0 or cap > contract['max_output_tokens']:
        raise BudgetDenied('output_limit_exceeds_contract')
    body.pop('max_completion_tokens', None)
    body['max_tokens'] = cap
    return body


def _charge_bytes(contract, body):
    import json
    from router.spend_ledger import amount
    encoded = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    estimate = max(1, len(encoded)) * amount(contract['input_nanos_per_token']) + body['max_tokens'] * amount(contract['output_nanos_per_token'])
    return estimate, estimate + amount(contract.get('fixed_overhead_nanos', 0))


def request_charge(contract, request):
    return _charge_bytes(contract, normalize_request(contract, request))


def decisions_charge(contract, payload):
    """Account the actual bounded Decisions document, including its output cap."""
    validate_contract(contract, 'decisions')
    cap = payload.get('max_tokens')
    if type(cap) is not int or cap < 0 or cap > contract['max_output_tokens']:
        raise BudgetDenied('output_limit_exceeds_contract')
    return _charge_bytes(contract, payload)


def candidate_is_eligible(candidate, required_capabilities, report):
    """Apply the shared capability, pricing and remaining-budget rule."""
    if not frozenset(required_capabilities) <= candidate.capabilities:
        return False
    if candidate.free:
        return True
    if (candidate.estimate is None or candidate.bound is None
            or candidate.estimate < 0 or candidate.bound < candidate.estimate):
        return False
    model = report['models'].get(candidate.canonical)
    overall = report['overall']
    if not model or any(bucket.get('remaining') is None for bucket in (model['today'], model['month'], overall['today'], overall['month'])):
        return False
    return bool(model and candidate.bound <= model['today']['remaining']
                and candidate.bound <= model['month']['remaining']
                and candidate.bound <= overall['today']['remaining']
                and candidate.bound <= overall['month']['remaining'])


def eligible_candidates(candidates, required_capabilities, report):
    eligible = [candidate for candidate in candidates
                if candidate_is_eligible(candidate, required_capabilities, report)]
    return [candidate for candidate in eligible if candidate.free] or eligible


def choose(candidates, required_capabilities, report):
    """Choose the cheapest eligible candidate; free candidates always win.

    Price/bound absence is never treated as zero. Paid candidates must have a
    finite conservative bound and enough reported remaining capacity.
    """
    eligible = eligible_candidates(candidates, required_capabilities, report)
    free = [candidate for candidate in eligible if candidate.free]
    if free:
        return sorted(free, key=lambda candidate: candidate.alias)[0]
    affordable = list(eligible)
    if not affordable:
        raise BudgetDenied('No priced, capability-compatible candidate has remaining budget')
    return min(affordable, key=lambda candidate: (candidate.estimate, candidate.alias))


def policy_revision(config):
    """Content identity shared by workers; a database location is not policy."""
    import hashlib
    import json
    return hashlib.sha256(json.dumps({k: v for k, v in config.items() if k != 'ledger'},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()
