# Cost-aware router research evidence

Date: 2026-09-21. Origin: user asked for Jev to know model-choice cost and
existing spend per model, then explicitly requested LiteLLM documentation,
web research, and other people's GitHub routers. Scope: research and retained
recommendation; no routing changes, deployment, purchases, or live inference.

Status: observed documentation/source, not runtime certification. Upstream pages
and GitHub main branches can change; no exact deployed LiteLLM version exists
in the imported workspace. Summaries below are original paraphrases.

## Local observations

- `router/jev_classifier.py`, `OpenRouterJevClassifier.classify`: direct httpx
  request to OpenRouter alpha Decisions; parses a tier, without retaining spend.
- `router/config.yaml`: database URL and model storage configured; no evidence
  that database-backed spend tracking is running. Tier aliases and fallback
  aliases often resolve to the same underlying model.
- `router/openrouter_quota_guard.py`: free quota exhaustion rewrites `jev` to
  `paid-general-capable`. This bypasses the classifier's capability choice.
- `tools/discover-free-models.py`, `normalized_pricing`: existing catalog-price
  extraction can inform estimates; it is not a persistent runtime spend ledger.

## Upstream evidence read

1. [LiteLLM spend tracking](https://docs.litellm.ai/docs/proxy/cost_tracking):
   database-backed request spend logs, Usage UI, cost response header, and
   reporting interfaces. Calculated spend needs reconciliation when it differs
   from a provider charge; pricing updates matter.
2. [Budget routing](https://docs.litellm.ai/docs/proxy/provider_budget_routing):
   provider and deployment budgets; model config uses `max_budget` and
   `budget_duration`. Redis is documented for multiple instances. Examples
   allow one request to cross a cap and reject the following request.
3. [Budgets and rate limits](https://docs.litellm.ai/docs/proxy/users): ordinary
   virtual-key budgets; per-key/per-model `model_max_budget` and internal-user
   model budgets explicitly marked Enterprise. Budget usage is exposed through
   key/user information. These are different scopes from deployment budgets.
4. [Budget fallbacks](https://docs.litellm.ai/docs/proxy/budget_fallbacks):
   `budget_fallbacks` applies at key authentication to per-model budgets;
   downstream provider-error fallbacks are separate. A fallback without its own
   model budget is treated as unlimited by that check. Page names v1.92.x+.
5. [Routing](https://docs.litellm.ai/docs/routing) documents async
   `cost-based-routing` and custom input/output rates.
   [Implementation](https://github.com/BerriAI/litellm/blob/main/litellm/router_strategy/lowest_cost.py),
   `async_get_available_deployments`, computes `item_cost` as input rate plus
   output rate; input token count participates in capacity checks. This is a
   rate ranking, not an input/output-length-weighted request estimate.
6. [Budget limiter source](https://github.com/BerriAI/litellm/blob/main/litellm/router_strategy/budget_limiter.py):
   deployment counters use model IDs; candidates are filtered on recorded
   spend and response cost updates counters afterward. This inspection does
   not establish an atomic pre-request reservation guarantee.
7. [Auto routing](https://docs.litellm.ai/docs/proxy/auto_routing): beta native
   Jev integration uses TypeSafe System One, with separate classifier usage
   logging and unknown cost when unpriceable. Custom plugins are documented
   from v1.99.x. These facts do not validate our alpha Decisions adapter.
8. [Jev setup](https://docs.litellm.ai/docs/auto_router/setup): built-in Jev
   credentials use `TYPESAFE_API_KEY`; replacing instructions/custom tier
   definitions has an Enterprise customization boundary.
9. [Routing plugins](https://docs.litellm.ai/docs/routing_plugins): candidate
   narrowing can compose with classification. Empty candidate sets raise;
   classifier failures instead degrade to a fallback. Include/exclude only,
   not a weighted scoring API. Async and configuration-scope constraints apply.
10. [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting):
    response usage contains account charge, token/cache information; streaming
    usage arrives at the final SSE message. Do not assume the separate alpha
    Decisions endpoint has this same accounting contract.
11. [OpenRouter activity](https://openrouter.ai/docs/api/api-reference/analytics/get-user-activity):
    `/api/v1/activity` returns model/provider/endpoint daily usage for the last
    30 completed UTC days and requires a management key. Supports key-hash
    filtering. It is historical aggregation, not today's live per-model feed.
12. [Current key](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key):
    ordinary key lookup includes aggregate usage and remaining key limit; it
    is not a per-model ledger. Documented response does not contain the free
    request quota structure assumed by our guard; API behavior remains unverified.
13. [Models](https://openrouter.ai/docs/api/api-reference/models/get-models) and
    [generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-generation):
    catalog rates support estimates; generation records support later charge
    reconciliation when an ID is retained. No account data was accessed.

## Research implications, not adopted behavior

Reuse LiteLLM accounting and available budget controls first. Supply Jev with
server-computed prices, estimates and spend snapshots; enforce eligibility in
code. Audit classifier, quota rewrite, direct alias, streaming and fallback
paths. Keep provider historical aggregates separate from overlapping local
transaction totals. Existing model IDs/prices were not validated or promoted.

Comparison evidence is in the separate dated other-routers research note.
