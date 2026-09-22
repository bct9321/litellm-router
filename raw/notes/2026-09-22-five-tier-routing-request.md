# Revised five-tier routing contract — 2026-09-22

Origin: user's explicit resume instruction on expanded-tiers. Supersedes the
proposal to expose twenty Auto Router tiers. Never patch the eight-tier limit.

JEV must make one structured decision containing family (GENERAL, REASONING,
AGENTIC, CODING) and capability (EFFICIENT, CAPABLE, ADVANCED, EXPERT, FRONTIER).
Keep all twenty FAMILY_CAPABILITY semantic names in logs, tests and documentation.
LiteLLM sees exactly five capability tiers with four family alias candidates each.
A RoutingPlugin must narrow the chosen tier to exactly the classified family alias
before deployment selection; no random cross-family choice or candidate widening.
Reuse existing lower-tier aliases/deployments/fallbacks where possible. Restore
accidental changes to existing CAPABLE wording. Semantic decisions must not depend
on vendor/provider, authentication, subscription or cost information.

Before modifying YAML, inspect installed classifier and RoutingPlugin APIs and
verify that one classification can return capability and propagate family through
a supported request-scoped field. If no such field propagates, STOP and document
the missing interface. A possible compatibility change is limited to structured
classifier-result signal propagation; none is authorized for implementation here.

Required eventual tests: all twenty outcomes with structured decision, semantic
name, tier, signal, pre/post candidate pools, exact alias and no cross-family
survivors; missing/unknown family, unknown capability, no widening, eight original
class equivalence, unchanged fallbacks and provider-independent semantics.
Two independent clean reviews and durable evidence are required for completion.
No OAuth deployment/login work until clean architectural review.

Current investigation uses local LiteLLM 1.99.0 source and its real public
async_pre_routing_hook. No installed upstream test suite has been located.
Plan: retain a reproducible no-network compatibility probe, distinguish proof of
missing propagation from completed routing, and independently audit the result.
Existing main baseline remains 9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc.
