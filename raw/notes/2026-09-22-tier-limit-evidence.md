# Tier-limit verification — 2026-09-22

Observed using the existing local LiteLLM 1.99.0 installation: constructing
ComplexityRouterConfig with the proposed twenty definitions and actual classifier
instance raises ValueError: tier_definitions must define between 2 and 8 tiers,
got 20. Installed config.py defines MAX_TIER_DEFINITIONS = 8.

Upstream main also defines MAX_TIER_DEFINITIONS = 8 and enforces it, accessed
2026-09-22:
https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/router_strategy/complexity_router/config.py

This contradicts the original pasted plan's assumption that twenty names work
without a LiteLLM compatibility change. Asked user to choose a version-pinned
compatibility patch or retain the expansion as a proposal. No compatibility
workaround applied while this decision is pending.

User additionally requested branch name expanded-tiers; renamed accordingly.
The branch still starts at origin/main 9f8d97b, without strict cost controls.

Focused classifier test accepts all twenty choices via fake Decisions HTTP.
Quota audit found the header hook fetched OpenRouter quota for ChatGPT routes.
Regression failed with sixteen cases, then passed after adding provider/alias
bypass to both hooks. Existing OpenRouter route-map semantics are preserved.
