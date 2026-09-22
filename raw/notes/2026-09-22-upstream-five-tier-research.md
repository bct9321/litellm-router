# Upstream five-tier compatibility investigation

Observed 2026-09-22. Read-only upstream investigation; no installation, provider call, core patch, or runtime/config change.

## Versions and freshness

Live GitHub API returned latest release **v1.102.0**, published **2026-09-22T17:56:26Z**, tag commit **95293834e833b2d2979f87d1bd2a5be45db6728a**. Main resolved to **5035c458fbd25720118386dfb21bbfade4f8ff3c**, committed **2026-09-22T19:05:23Z**. The web tool initially served older cached release/commit results; version conclusions below use direct public GitHub API and raw source requests, whose commands exited 0 after a sandbox-denied network attempt was retried with approved read-only access.

- [Latest release](https://github.com/BerriAI/litellm/releases/tag/v1.102.0)
- [Tag identity API](https://api.github.com/repos/BerriAI/litellm/git/ref/tags/v1.102.0)
- [Pinned main commit](https://github.com/BerriAI/litellm/commit/5035c458fbd25720118386dfb21bbfade4f8ff3c)

## Both blockers persist

1. **Five custom tiers plus RoutingPlugins remain rejected.** Release `config.py` lines 1600–1620 includes `plugins` among conflicts with `tier_definitions`. The error is assembled dynamically; searching only for the literal complete error can miss it. The limit remains 2–8, so five tiers alone are supported. [Release source](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/litellm/router_strategy/complexity_router/config.py#L1600). Pinned main retains the same rejection at lines 1886–1906. [Main source](https://github.com/BerriAI/litellm/blob/5035c458fbd25720118386dfb21bbfade4f8ff3c/litellm/router_strategy/complexity_router/config.py#L1886).
2. **The classifier interface still returns only a tier string or None.** [Release protocol, lines 1055–1066](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/litellm/types/router.py#L1055).
3. **No supported classifier-result signal handoff appears in the inspected implementation.** `_classify_with_plugin` constructs its context, rejects non-string verdicts, and returns an outcome containing only its own tier signal. `_pick_model_for_tier` creates another context from request metadata; it does not consume the classifier context's signals or newly assigned metadata entries. Nested mutable-object side effects are not a documented result interface and are not recommended. [Release classification, lines 1901–1958](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/litellm/router_strategy/complexity_router/complexity_router.py#L1901), [selection, lines 2262–2304](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/litellm/router_strategy/complexity_router/complexity_router.py#L2262). Pinned main has equivalent paths at 2261 and 2835.

Upstream release tests explicitly expect custom-tier/plugin rejection at line 10978. Tests at 6709 establish custom classifier *alone* can return a defined custom tier; that is not evidence for the requested combined pipeline. [Release tests](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/tests/test_litellm/router_strategy/test_complexity_router.py#L10978).

## Supported extension points and architecture choices

**No supported upgrade satisfying the exact requested architecture was found** in the current latest release or pinned main. No claim is made to exhaustively audit every historical release.

- **Concrete alternative requiring user approval:** a proxy `CustomLogger.async_pre_call_hook` performs one JEV semantic decision, validates family/capability, stores sanitized request-scoped decision metadata, and sets `data['model']` to the registry's family-specific alias. LiteLLM then performs ordinary deployment/fallback routing. Official documentation explicitly demonstrates model rewriting through this hook. This avoids core changes and the tier cap, but replaces the requested Auto Router plus RoutingPlugin architecture; it must not be silently substituted. [Official hook documentation](https://docs.litellm.ai/docs/proxy/call_hooks).
- **Router-level RoutingPlugin is real but not a drop-in solution:** it shares one context between its own plugins and persists accumulated signals into request metadata. However, its candidate names are underlying `litellm_params.model` values, not the requested family aliases; multiple aliases sharing a ChatGPT model cannot be distinguished just by that filter. [Release implementation, lines 13269–13334](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/litellm/router.py#L13269), [pipeline tests](https://github.com/BerriAI/litellm/blob/95293834e833b2d2979f87d1bd2a5be45db6728a/tests/test_litellm/router_strategy/test_router_routing_plugins.py#L263).
- **Compatibility proposal requiring approval:** upstream would need both custom-tier/plugin coexistence and an explicit classifier-result metadata/signal handoff. Changing only signal propagation cannot remove the independent validation conflict. The eight-tier limit need not change.

Next safe action: retain this source evidence in the wiki, present the exact architectural choice, and obtain direction before substituting a hook or modifying upstream compatibility. OAuth/login/streaming/model quality remain outside this investigation.
