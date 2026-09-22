"""Final physical-attempt authority for bounded local HTTP fixtures.

The deployment hook selects a trusted id; this transport validates the actual
HTTP target and body before committing a reservation. No live billing contract
is currently supported.
"""
import contextvars
import json
import time
import uuid
from urllib.parse import urlsplit

import httpx

from router.spend_ledger import BudgetDenied, usd_nanos
from router.cost_policy import normalize_request, request_charge, validate_contract

dispatch_context = contextvars.ContextVar('cost_dispatch', default=None)
_REQUESTS = {}
_REQUEST_TTL = 3600
_MAX_REQUESTS = 10000


def register_request_context(entry_alias, payload, required_capabilities, allowed_deployments, policy_revision):
    """Bounded process-local authority; client metadata never creates an entry."""
    now = time.monotonic()
    for key in list(_REQUESTS):
        if _REQUESTS[key]['expires'] <= now:
            del _REQUESTS[key]
    if len(_REQUESTS) >= _MAX_REQUESTS:
        raise BudgetDenied('request_context_capacity_exhausted')
    identifier = str(uuid.uuid4())
    context = {'id': identifier, 'entry_alias': entry_alias, 'payload': payload,
               'required_capabilities': frozenset(required_capabilities),
               'allowed_deployments': frozenset(allowed_deployments),
               'policy_revision': policy_revision, 'failed_deployments': set(),
               'free_unavailable': False, 'expires': now + _REQUEST_TTL}
    _REQUESTS[identifier] = context
    return context


def get_request_context(metadata):
    identifier = (metadata or {}).get('_cost_request')
    context = _REQUESTS.get(identifier) if isinstance(identifier, str) else None
    if context is None or context['expires'] <= time.monotonic():
        raise BudgetDenied('request_context_missing_or_expired')
    return context


def release_request_context(metadata):
    identifier = (metadata or {}).get('_cost_request')
    if isinstance(identifier, str):
        _REQUESTS.pop(identifier, None)


def mark_quota_unavailable(metadata):
    """Called only by the server quota callback on verified quota exhaustion."""
    get_request_context(metadata)['free_unavailable'] = True


class AccountedStream(httpx.AsyncByteStream):
    def __init__(self, upstream, ledger, attempt, content_type, on_incomplete=None):
        self.upstream = upstream
        self.ledger = ledger
        self.attempt = attempt
        self.content_type = content_type
        self.buffer = bytearray()
        self.overflow = False
        self.complete = False
        self.on_incomplete = on_incomplete

    async def __aiter__(self):
        try:
            async for chunk in self.upstream:
                if len(self.buffer) + len(chunk) <= 2_000_000:
                    self.buffer.extend(chunk)
                else:
                    self.overflow = True
                yield chunk
            self.complete = True
        finally:
            self._settle()

    def _settle(self):
        costs = set()
        final = self.complete and not self.overflow
        bodies = [bytes(self.buffer)]
        if 'text/event-stream' in self.content_type:
            # A terminal sentinel is necessary, and must be the last event.
            # EOF alone or a usage-bearing partial chunk is not final evidence.
            bodies = [line[5:].strip() for line in bytes(self.buffer).splitlines() if line.startswith(b'data:')]
            final = final and bool(bodies) and bodies[-1] == b'[DONE]' and bodies.count(b'[DONE]') == 1
            bodies = [body for body in bodies if body != b'[DONE]']
        for body in bodies:
            try:
                data = json.loads(body)
                usage = data.get('usage') or {}
                parsed = usd_nanos(usage.get('cost'))
                if parsed is not None:
                    costs.add(parsed)
            except (ValueError, AttributeError, TypeError):
                final = False
        if len(costs) != 1:
            final = False
        cost = max(costs) if costs else None
        state = 'provider-reported' if final else 'unknown'
        self.ledger.settle(self.attempt, self.attempt + ':response:' + state + ':' + str(cost), cost, state)
        if not final and self.on_incomplete:
            self.on_incomplete()

    async def aclose(self):
        try:
            await self.upstream.aclose()
        finally:
            self._settle()


class CostTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger, contracts, inner=None, *, policy=None):
        self.ledger = ledger
        self.contracts = contracts
        self.policy = policy
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)
        for contract in contracts.values():
            validate_contract(contract)

    def _authorize(self, request, payload, dispatch):
        if self.policy is None:
            raise BudgetDenied('trusted_deployment_policy_required')
        context = get_request_context({'_cost_request': dispatch.get('request')})
        if context['policy_revision'] != dispatch.get('policy_revision'):
            raise BudgetDenied('policy_revision_mismatch')
        identifier = dispatch.get('deployment')
        deployment = self.policy['deployments'].get(identifier)
        if not deployment or identifier not in context['allowed_deployments']:
            raise BudgetDenied('deployment_not_allowed_for_original_route')
        required = context['required_capabilities']
        if not required <= frozenset(deployment['capabilities']):
            raise BudgetDenied('deployment_capability_mismatch')
        contract = self.contracts[deployment['contract']]
        validate_contract(contract)
        origin = f'{request.url.scheme}://{request.url.host}:{request.url.port}'
        if (request.method != 'POST' or request.url.query or request.url.username or request.url.password
                or origin != contract['origin'] or request.url.path != contract['path']
                or payload.get('model') != deployment['provider_model']):
            raise BudgetDenied('endpoint_or_provider_model_outside_contract')
        if not deployment['free'] and not context['free_unavailable']:
            for free_id in context['allowed_deployments'] - context['failed_deployments']:
                free = self.policy['deployments'][free_id]
                if free['free'] and required <= frozenset(free['capabilities']):
                    raise BudgetDenied('free_first_required')
        return context, identifier, deployment, contract

    async def handle_async_request(self, request):
        try:
            return await self._handle_authorized_request(request)
        except BudgetDenied as exc:
            dispatch = dispatch_context.get() or {}
            context = _REQUESTS.get(dispatch.get('request'))
            if context is not None:
                context['last_denial'] = str(exc)
            raise

    async def _handle_authorized_request(self, request):
        dispatch = dispatch_context.get()
        if not dispatch:
            raise BudgetDenied('No server-owned dispatch context')
        try:
            payload = json.loads(request.content)
        except (ValueError, UnicodeError) as exc:
            raise BudgetDenied('unsupported_request_body') from exc
        context, identifier, deployment, contract = self._authorize(request, payload, dispatch)
        payload = normalize_request(contract, payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        headers = request.headers.copy()
        headers['content-length'] = str(len(encoded))
        request = httpx.Request(request.method, request.url, headers=headers,
                                content=encoded, extensions=request.extensions)
        attempt = str(uuid.uuid4())
        estimate, bound = request_charge(contract, payload)
        self.ledger.reserve(attempt, context['id'], contract['canonical'], deployment['alias'],
                            identifier, bound, estimate, entry_alias=context['entry_alias'],
                            provider_model=deployment['provider_model'], deployment_id=identifier,
                            contract_revision=contract['revision'], kind='solver')
        context.pop('last_denial', None)
        def failed():
            context['failed_deployments'].add(identifier)
        try:
            # SQLite admission can wait behind another worker. A quote that
            # expired while waiting must never authorize the outgoing attempt.
            validate_contract(contract)
            response = await self.inner.handle_async_request(request)
        except BaseException:
            failed()
            self.ledger.settle(attempt, attempt + ':network', None, 'unknown')
            raise
        if response.status_code >= 400:
            failed()
        response.stream = AccountedStream(response.stream, self.ledger, attempt,
                                          response.headers.get('content-type', ''), failed)
        return response

    async def aclose(self):
        await self.inner.aclose()
