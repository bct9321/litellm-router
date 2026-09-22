"""Request-local semantic routing via LiteLLM's proxy callback extension."""
from dataclasses import dataclass
from pathlib import Path
import yaml
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_llm import CustomLLM, CustomLLMError

from litellm.types.router import RoutingContext
from router.jev_classifier import FAMILIES, CAPABILITIES, OpenRouterJevClassifier
from router.openrouter_quota_guard import OpenRouterQuotaGuard


@dataclass(frozen=True)
class SemanticDecision:
    family: str
    capability: str

    def __post_init__(self):
        if self.family not in FAMILIES or self.capability not in CAPABILITIES:
            raise ValueError('Unknown JEV family or capability')

    @property
    def semantic_class(self):
        return f'{self.family}_{self.capability}'

    @property
    def alias(self):
        family, capability = self.family.lower(), self.capability.lower()
        return f'free-{family}-{capability}' if self.capability in ('EFFICIENT', 'CAPABLE') else f'{capability}-{family}'

    def as_dict(self):
        return {'family': self.family, 'capability': self.capability, 'semantic_class': self.semantic_class}


class FamilyFilter:
    async def run(self, context: RoutingContext) -> RoutingContext:
        signal = context.signals.get('jev') or {}
        decision = SemanticDecision(signal.get('family'), signal.get('capability'))
        remaining = [alias for alias in context.candidate_models if alias == decision.alias]
        if len(remaining) != 1:
            raise ValueError('JEV family filter requires exactly one matching candidate')
        return context.model_copy(update={'candidate_models': remaining})


class JevRouter(CustomLogger):
    def __init__(self):
        super().__init__()
        self.config = yaml.safe_load(Path(__file__).with_name('config.yaml').read_text(encoding='utf-8'))
        self.quota = OpenRouterQuotaGuard()
        self.family_aliases = {SemanticDecision(f, c).alias for f in FAMILIES for c in CAPABILITIES}
        self.family_aliases.update(alias + '-backup' for alias in tuple(self.family_aliases) if alias.startswith('free-'))

    async def _authorize(self, user, aliases):
        from litellm.proxy import proxy_server
        from litellm.proxy.auth.auth_checks import can_key_call_resolved_model
        active_router = proxy_server.llm_router
        models = active_router.model_list if active_router is not None else self.config['model_list']
        for alias in aliases:
            rows = [row for row in models if row['model_name'] == alias]
            if not rows or any(row['litellm_params'].get('guardrails') for row in rows):
                raise HTTPException(503, 'Semantic routing requires registered targets without model-level guardrails')
            await can_key_call_resolved_model(alias, models, user, active_router)

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type, **kwargs):
        if data.get('model') != 'jev':
            quota_data = {k: v for k, v in data.items() if k not in ('custom_llm_provider', 'litellm_params')}
            result = await self.quota.async_pre_call_hook(user_api_key_dict, cache, quota_data, call_type)
            if result['model'] != data.get('model') or result['model'] in self.family_aliases:
                chain = self._chain(result['model'])
                await self._authorize(user_api_key_dict, [result['model'], *chain])
                result['fallbacks'] = [{result['model']: chain}]
                return result
            return data
        forbidden = {'api_base', 'base_url', 'api_key', 'custom_llm_provider', 'litellm_params',
                     'fallbacks', 'context_window_fallbacks', 'content_policy_fallbacks',
                     'model_list', 'deployment_id', 'specific_deployment', 'mock_response',
                     'user_config', 'router_settings_override', 'model_group_alias',
                     'num_retries', 'max_retries', 'max_fallbacks', 'fallback_depth',
                     'disable_fallbacks', 'retry_policy', 'model_group_retry_policy', 'client', 'acompletion',
                     'mock_testing_fallbacks', 'mock_testing_context_fallbacks',
                     'mock_testing_content_policy_fallbacks', '_target_order', '_excluded_deployment_ids'}
        messages = data.get('messages')
        if (call_type not in ('completion', 'acompletion') or forbidden.intersection(data) or not isinstance(messages, list)
                or not messages or any(not isinstance(m, dict) or not isinstance(m.get('content'), str)
                                       for m in messages)):
            raise HTTPException(400, 'jev accepts text chat completions without deployment overrides')
        choice = await OpenRouterJevClassifier().classify({'raw_messages': data.get('messages', [])})
        family, capability = choice.split('_', 1)
        decision = SemanticDecision(family, capability)
        pool = [SemanticDecision(f, capability).alias for f in FAMILIES]
        context = RoutingContext(raw_messages=[], structured_messages=[], candidate_models=pool,
                                 signals={'jev': decision.as_dict()})
        selected = await FamilyFilter().run(context)
        result = {**data, 'model': selected.candidate_models[0],
                'metadata': {**(data.get('metadata') or {}), 'jev': {
                    **decision.as_dict(), 'candidates_before': pool,
                    'candidates_after': selected.candidate_models}}}
        result = await self.quota.async_pre_call_hook(user_api_key_dict, cache, result, call_type)
        chain = self._chain(result['model'])
        await self._authorize(user_api_key_dict, [result['model'], *chain])
        # A root-only list prevents nested alias fallbacks from changing this order.
        result['fallbacks'] = [{result['model']: chain}]
        result['metadata']['jev']['execution_alias'] = result['model']
        return result

    def _chain(self, alias):
        return next((item[alias] for item in self.config['router_settings']['fallbacks'] if alias in item), [])

    async def async_post_call_response_headers_hook(self, data, user_api_key_dict, response, **kwargs):
        return await self.quota.async_post_call_response_headers_hook(data, user_api_key_dict, response, **kwargs)


class EntrypointGuard(CustomLLM):
    def completion(self, *args, **kwargs):
        raise CustomLLMError(503, 'jev routing callback is required')

    async def acompletion(self, *args, **kwargs):
        return self.completion()

    def streaming(self, *args, **kwargs):
        return self.completion()

    async def astreaming(self, *args, **kwargs):
        self.completion()
        yield  # pragma: no cover - defines the async iterator protocol


entrypoint_guard = EntrypointGuard()
proxy_handler_instance = JevRouter()
