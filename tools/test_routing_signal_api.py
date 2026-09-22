"""Installed LiteLLM API investigation, not acceptance of family routing.

These passing probes document missing propagation in 1.99.0. They do not replace
the eventual twenty-outcome acceptance suite. No provider HTTP is performed.
"""
import os
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(ROOT / 'outputs/token-cache')

from litellm import Router
from litellm.router_strategy.complexity_router.complexity_router import ComplexityRouter

LEVELS = ('EFFICIENT', 'CAPABLE', 'ADVANCED', 'EXPERT', 'FRONTIER')
FAMILIES = ('general', 'reasoning', 'agentic', 'coding')


class SignalApiTests(unittest.IsolatedAsyncioTestCase):
    async def probe(self, structured=False, seeded=False, custom=False):
        seen = {}

        class Classifier:
            async def classify(self, context):
                seen['classifier_calls'] = seen.get('classifier_calls', 0) + 1
                context.signals['jev_family'] = 'CODING'
                context.metadata['jev_family'] = 'CODING'
                seen['classifier_context'] = context
                return {'family': 'CODING', 'capability': 'EXPERT'} if structured else 'COMPLEX'

        class Filter:
            async def run(self, context):
                seen['filter_context'] = context
                seen['before'] = tuple(context.candidate_models)
                family = context.signals.get('jev_family') or context.metadata.get('jev_family')
                context.candidate_models = [alias for alias in context.candidate_models
                                            if family and alias.startswith(family.lower() + '-')]
                seen['after'] = tuple(context.candidate_models)
                return context

        config = {
            'classifier_type': 'custom', 'classifier_plugin': Classifier(),
            'tiers': {tier: [f'{family}-{level}' for family in FAMILIES]
                      for tier, level in [('SIMPLE', 'efficient'), ('MEDIUM', 'capable'),
                                          ('COMPLEX', 'expert'), ('REASONING', 'frontier')]},
            'classifier_fallback': 'default_model', 'default_model': 'general-capable',
            'plugins': [Filter()],
        }
        if custom:
            config.update(tier_definitions=[{'name': level, 'description': level} for level in LEVELS],
                          tiers={level: [f'{family}-{level.lower()}' for family in FAMILIES]
                                 for level in LEVELS}, fallback_tier='CAPABLE')
        kwargs = {'metadata': {'fixture': 'nonempty'}}
        if seeded:
            kwargs['metadata']['jev_family'] = 'CODING'
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
            router = ComplexityRouter('fixture', Router(model_list=[]), config, derive_savings_baseline=False)
            try:
                seen['result'] = await router.async_pre_routing_hook(
                    'fixture', kwargs, messages=[{'role': 'user', 'content': 'Implement the requested feature.'}])
            except ValueError as exc:
                seen['error'] = str(exc)
        seen['request_metadata'] = kwargs['metadata']
        return seen

    async def test_classifier_signal_and_metadata_are_not_propagated(self):
        seen = await self.probe()
        self.assertEqual(seen['classifier_calls'], 1)
        self.assertEqual(seen['before'], tuple(f'{family}-expert' for family in FAMILIES))
        self.assertNotIn('jev_family', seen['filter_context'].signals)
        self.assertNotIn('jev_family', seen['filter_context'].metadata)
        self.assertNotIn('jev_family', seen['request_metadata'])
        self.assertIsNot(seen['classifier_context'], seen['filter_context'])
        self.assertEqual(seen['after'], ())
        self.assertIn('No candidate models left for tier COMPLEX', seen['error'])
        print('OBSERVED on supported built-in COMPLEX tier: classifier family metadata/signals do not reach filter.')

    async def test_structured_verdict_is_rejected_and_uses_fallback_pool(self):
        seen = await self.probe(structured=True)
        self.assertEqual(seen['classifier_calls'], 1)
        self.assertEqual(seen['before'], tuple(f'{family}-capable' for family in FAMILIES))
        self.assertIn('No candidate models left for tier MEDIUM', seen['error'])
        print('OBSERVED: structured classifier verdict is rejected; built-in MEDIUM fallback pool is used.')

    async def test_preexisting_metadata_can_narrow_pool_positive_control(self):
        seen = await self.probe(seeded=True)
        self.assertEqual(seen['after'], ('coding-expert',))
        self.assertEqual(seen['result'].model, 'coding-expert')
        print('CONTROL: preexisting metadata narrows built-in COMPLEX to coding-expert; not classifier propagation.')

    async def test_five_custom_tiers_cannot_be_combined_with_plugins(self):
        with self.assertRaisesRegex(ValueError, 'plugins cannot be combined with tier_definitions'):
            await self.probe(custom=True)
        print('BLOCKER: five custom capability tiers + RoutingPlugin rejected by installed validator.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
