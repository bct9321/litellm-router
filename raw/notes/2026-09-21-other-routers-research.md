# Other routers: cost selection and spend governance

Observed: 2026-09-21. Scope: primary GitHub README/code and official documentation,
read through web browsing. No installation, inference, performance benchmark,
account access, or deployment verification. Branch URLs are mutable; attempts to
resolve current GitHub commit IDs were unsuccessful. Do not treat these findings
as release-pinned integration guarantees.

## RouteLLM: useful quality/cost benchmark, not an accounting replacement

- Observed in the [README](https://github.com/lm-sys/RouteLLM): a learned selector
  routes between a stronger and weaker model. A calibrated threshold controls the
  fraction of strong-model calls. This is a quality/cost tradeoff parameter, not a
  dollar ceiling or remaining balance. Calibration should use representative
  requests; published savings are the authors' benchmark claims, not predictions
  for Jev. The project uses LiteLLM for provider calls.
- Observed in [controller.py](https://raw.githubusercontent.com/lm-sys/RouteLLM/main/routellm/controller.py):
  the controller stores in-memory `model_counts`, routes using the last message,
  and invokes LiteLLM completion. This inspected controller contains no persistent
  dollar-spend ledger or budget admission check. Its comment notes that current
  routers were trained on first-turn data and multi-turn use needs more research.
- Proposed fit: benchmark Jev against a calibrated cheap/strong selector on our
  real workload. Keep gateway accounting separately. Replacing eight capability
  tiers with this two-model architecture is not justified by the research alone.

## vLLM Semantic Router: strong design reference for eligible cost selection

- Observed documentation in the [recipe README](https://raw.githubusercontent.com/vllm-project/semantic-router/main/config/recipes/built-in/latest/mom-v1/README.md):
  the Cost recipe keeps a request on one model and chooses the lowest estimated
  request cost within its decision's quality band. Reasoning/tool pools and
  correctness-recovery escalation preserve capability. Known-insufficient context
  windows are filtered; unknown context metadata remains eligible. The README
  explicitly requires deployment-specific end-to-end evaluation and warns that
  classifier errors affect selection. This is documented behavior, not verified
  runtime behavior in this workspace.
- Observed source in [static.go](https://raw.githubusercontent.com/vllm-project/semantic-router/main/src/semantic-router/pkg/selection/static.go):
  a baseline selector uses configured category scores or the first candidate.
  Thus not every selector is cost-aware merely because the framework supports
  cost recipes. This source was web-cached; no current-main code audit was completed.
- Unresolved/proposed upstream: [issue 3412](https://github.com/vllm-project/semantic-router/issues/3412)
  was open when read. It proposes calibrated success-constrained selection by
  expected lifecycle cost, including retries, escalation, switching and cache
  losses. It requires observation before production application. Do not represent
  that proposed quality guarantee as already shipped.
- Proposed fit: borrow the separation of capability eligibility, quality band,
  estimated request cost and evidence-backed promotion. A provider-bill-grade
  per-model ledger or dollar reservation guarantee was not established by the
  inspected sources; the recipe is not evidence of either.

## Bifrost: closest alternative combining governance and routing

- Official [complexity-router documentation](https://docs.getbifrost.ai/features/governance/complexity-router)
  describes embedding-based Simple/Medium/Complex classification exposed to CEL
  rules, optional LLM fallback, and abstention on weak matches. Classification
  runs when rules reference it. This is task classification plus configured
  routing, not evidence of an optimizer consuming remaining dollar balances.
  Proposed lesson: count classifier cost and test follow-up turns explicitly.
- Official [model-limits documentation](https://docs.getbifrost.ai/features/governance/model-limits)
  describes global or virtual-key model/provider limits, multiple reset windows,
  and a UI table/API showing `current_usage`. This directly addresses model-level
  budget visibility. Scope availability varies; some scopes are enterprise-only.
- Important boundary in official [budget documentation](https://docs.getbifrost.ai/features/governance/budget-and-limits):
  budgets are checked before requests and usage charged afterward. Its example
  explicitly permits a request to cross a cap and blocks the next request.
  Therefore these native budgets must not be described as exact no-overspend
  reservations. The same page states multiple OSS nodes sharing Postgres are
  unsupported because critical state remains in memory; synchronized clustering
  is an enterprise feature. These are documented limits, not independently
  reproduced bugs.
- Observed [usage tracker implementation](https://raw.githubusercontent.com/maximhq/bifrost/main/plugins/governance/tracker.go):
  accounting identifies physical attempts with request ID plus attempt number,
  handles failed requests that consumed tokens, distinguishes streaming terminal
  settlement, and uses process-local deduplication. Comments explicitly describe
  restart/cross-node limitations. Proposed lesson: spend belongs to actual
  attempts, not only successful logical requests, and deduplication needs a
  clearly stated durability boundary.
- Proposed fit: credible alternative if changing the gateway becomes necessary;
  no evidence here makes migration preferable to using LiteLLM's existing
  facilities. Compare pinned releases and concurrency behavior first. Vendor
  speed claims were not evaluated and are not a reason to migrate this project.

## Portkey: useful governance/product comparison, check edition boundaries

- Observed [gateway README](https://raw.githubusercontent.com/Portkey-AI/gateway/main/README.md):
  weighted balancing, retries/fallbacks, cost analytics, and an open pricing
  database are advertised. Automatic provider optimization is explicitly marked
  hosted/enterprise. The open gateway repository must not be equated with every
  capability of the commercial service.
- [Conditional-routing docs](https://docs1.portkey.ai/docs/product/ai-gateway/conditional-routing)
  describe metadata conditions selecting targets. The returned page is old and
  lists cheapest-target routing as future work; it is historical evidence, not
  a reliable statement of today's full feature set.
- Proposed fit: useful reference for routing metadata and observable decisions.
  A current open-source model-spend database schema or reservation mechanism was
  not verified. Do not switch gateways based on a broad marketing feature list.

## Proposed conclusions for LiteLLM plus Jev

1. Separate estimated choice cost, recorded actual spend, and admission control.
   A cheaper-model selector does not automatically supply the other two.
2. Prefer the cheapest eligible model inside a measured capability/quality band;
   account for classifier calls, failed billable attempts, retries and cache
   behavior when evaluating savings.
3. Give Jev a compact, timestamped snapshot only if that improves selection in a
   replay benchmark. Let deterministic code exclude ineligible or over-budget
   choices; prompts alone cannot enforce spending limits.
4. Reuse existing LiteLLM accounting before writing another ledger. This note
   compares alternatives; the separate LiteLLM investigation must establish the
   exact APIs, persistence requirements and cap semantics for the chosen version.
5. Test restarts, duplicate callbacks, cancellations, fallback attribution and
   concurrent in-flight requests before claiming accurate accounting or a hard cap.

These are design recommendations, not changes to router behavior. No current
model price or live historical account spend was retrieved.
