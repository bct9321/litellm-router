"""Strict opt-in proxy controls for the verified bounded local adapter."""
import copy
import json
import os
from pathlib import Path

import httpx
import litellm
from litellm.integrations.custom_logger import CustomLogger

from router.cost_transport import (CostTransport, dispatch_context, register_request_context,
                                   get_request_context, release_request_context)
from router.cost_policy import (CHAT_KEYS, Candidate, choose, eligible_candidates, request_charge, validate_policy,
                                policy_revision)
from router.spend_ledger import Ledger, BudgetDenied


class CostGuard(CustomLogger):
    def __init__(self, config):
        super().__init__()
        self.config = copy.deepcopy(config)
        validate_policy(self.config)
        self.revision = policy_revision(self.config)
        self.ledger = Ledger(config['ledger'], config['limits'], policy_revision=self.revision,
                             billing_scope=config.get('billing_scope', 'router-only'),
                             coverage_mode=config.get('coverage_mode', 'router-only'))
        litellm.aclient_session = httpx.AsyncClient(
            transport=CostTransport(self.ledger, self.config['contracts'], policy=self.config),
            trust_env=False, follow_redirects=False,
        )

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type, **kwargs):
        if call_type not in (None, 'completion', 'acompletion'):
            raise BudgetDenied('unsupported_strict_adapter')
        dispatch_context.set(None)
        entry_alias = data.get('model')
        route = self.config['routes'].get(entry_alias)
        if route:
            allowed = {identifier for candidate in route['candidates'] for identifier in candidate['deployment_ids']}
            required = set(route.get('required_capabilities', []))
        else:
            allowed = {identifier for identifier, deployment in self.config['deployments'].items()
                       if deployment['alias'] == entry_alias}
            required = set()
        if not allowed:
            raise BudgetDenied('unknown_entry_route')
        # Include unsupported billable fields so the pricing boundary rejects,
        # rather than dropping them and estimating a cheaper different request.
        client_keys = CHAT_KEYS | {'reasoning_effort', 'modalities', 'audio', 'prediction',
                                   'web_search_options', 'functions', 'function_call'}
        payload = copy.deepcopy({key: data[key] for key in client_keys if key in data})
        if payload.get('tools'):
            required.add('tools')
        for message in payload.get('messages', []):
            content = message.get('content') if isinstance(message, dict) else None
            if isinstance(content, list) and any(isinstance(p, dict) and p.get('type') == 'image_url' for p in content):
                required.add('vision')
        context = register_request_context(entry_alias, payload, required, allowed, self.revision)
        metadata = data.setdefault('metadata', {})
        # Overwrite any client-supplied accounting metadata. The private registry
        # remains authoritative even if later callbacks mutate the copy.
        metadata['_cost_request'] = context['id']
        metadata['_cost_alias'] = entry_alias
        metadata['_cost_request_payload'] = copy.deepcopy(payload)
        metadata['_cost_required_capabilities'] = sorted(required)
        if route and entry_alias != 'jev':
            candidates = []
            for item in route['candidates']:
                priced = []
                for identifier in item['deployment_ids']:
                    deployment = self.config['deployments'][identifier]
                    contract = self.config['contracts'][deployment['contract']]
                    try:
                        priced.append(request_charge(contract, dict(payload, model=deployment['provider_model'])))
                    except BudgetDenied:
                        continue
                estimate, bound = max(priced, key=lambda value: value[1]) if priced else (None, None)
                # Even free requests need a valid, supported zero-charge contract.
                if not priced:
                    continue
                candidates.append(Candidate(item['alias'], item['canonical'],
                                  frozenset(item['capabilities']), item['free'], estimate, bound))
            eligible = eligible_candidates(candidates, required, self.ledger.report())
            selected = next((candidate for candidate in eligible if candidate.alias == entry_alias), None)
            if selected is None:
                selected = choose(eligible, required, self.ledger.report())
            data['model'] = selected.alias
        return data

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        metadata = kwargs.get('metadata') or kwargs.get('litellm_params', {}).get('metadata') or {}
        context = get_request_context(metadata)
        if context['policy_revision'] != self.revision:
            raise BudgetDenied('policy_revision_mismatch')
        provider = kwargs.get('custom_llm_provider')
        model = str(kwargs.get('model', ''))
        # LiteLLM's virtual complexity model resolves to a real solver; it is
        # never itself an authorized physical HTTP deployment.
        if provider == 'auto_router' or model.startswith('auto_router/'):
            if context['entry_alias'] != 'jev':
                raise BudgetDenied('virtual_router_not_allowed')
            dispatch_context.set(None)
            kwargs['max_retries'] = 0
            return kwargs
        identifier = str(kwargs.get('model_info', {}).get('id') or '')
        deployment = self.config['deployments'].get(identifier)
        if deployment is None or identifier not in context['allowed_deployments']:
            raise BudgetDenied('deployment_not_allowed_for_original_route')
        if provider not in (None, 'openai') or (provider is None and not model.startswith('openai/')):
            raise BudgetDenied('unsupported_strict_adapter')
        # Reject before adapter execution as well: other SDK adapters may not
        # use LiteLLM's shared async HTTP transport at all.
        if not context['required_capabilities'] <= frozenset(deployment['capabilities']):
            raise BudgetDenied('deployment_capability_mismatch')
        dispatch_context.set({'request': context['id'], 'deployment': identifier,
                              'policy_revision': self.revision})
        kwargs['max_retries'] = 0
        return kwargs

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict,
                                           traceback_str=None):
        # The OpenAI SDK wraps transport exceptions; retain the typed server
        # denial through LiteLLM's documented failure transformation callback.
        try:
            context = get_request_context((request_data or {}).get('metadata'))
            reason = context.get('last_denial')
        except BudgetDenied:
            reason = None
        if reason is None and isinstance(original_exception, BudgetDenied):
            reason = str(original_exception)
        release_request_context((request_data or {}).get('metadata'))
        if reason:
            from fastapi import HTTPException
            return HTTPException(status_code=429, detail={'code':'cost_budget_denied', 'reason':reason})
        return None

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        release_request_context((data or {}).get('metadata'))
        return response


class CostAwareGuard(CustomLogger):
    """Always-loadable callback; strict mode activates only with a full policy."""
    def __init__(self):
        super().__init__()
        config_path = os.environ.get('COST_ROUTER_CONFIG')
        self.active = CostGuard(json.loads(Path(config_path).read_text(encoding='utf-8'))) if config_path else None

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type, **kwargs):
        return data if self.active is None else await self.active.async_pre_call_hook(user_api_key_dict, cache, data, call_type, **kwargs)

    async def async_pre_call_deployment_hook(self, kwargs, call_type):
        return kwargs if self.active is None else await self.active.async_pre_call_deployment_hook(kwargs, call_type)

    async def async_post_call_failure_hook(self, request_data, original_exception, user_api_key_dict,
                                           traceback_str=None):
        if self.active is None:
            return None
        return await self.active.async_post_call_failure_hook(request_data, original_exception,
                                                              user_api_key_dict, traceback_str)

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        if self.active is None:
            return response
        return await self.active.async_post_call_success_hook(data, user_api_key_dict, response)


proxy_handler_instance = CostAwareGuard()
