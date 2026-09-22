# Cost-aware routing and spend visibility

Status: strict local implementation verified, 2026-09-21. Execution resumed
under [user authorization](../raw/notes/2026-09-21-router-plan-execution.md).
The dispatch, ledger/history and Jev repairs described below are implemented;
final real-proxy verification and two consecutive clean independent reviews
passed; see the [receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). No live billing contract, budget amount or deployment is claimed.

The [delivery plan](router-delivery-plan.md) records the reviewed defects and
acceptance gates. Its proposed implementation sections are reconciled by current
code and [checkpoint log](log.md), not by assuming that prior fixture passes
prove new changes. Sources include [research](../raw/notes/2026-09-21-cost-aware-router-research.md),
[router comparison](../raw/notes/2026-09-21-other-routers-research.md), and
[review evidence](../raw/notes/2026-09-21-router-review-plan-evidence.md).

## Current implementation and limits

- [Cost guard](../router/cost_guard.py) records the original alias, capabilities,
  full request and allowed deployments before quota rewriting. Private request
  context and a policy fingerprint prevent client metadata from becoming authority.
- [Final transport](../router/cost_transport.py) checks the actual deployment,
  endpoint, model, capability and body for every supported dispatch, including
  direct aliases and fallbacks. Output limits are normalized into the actual
  outgoing JSON before pricing and reservation.
- [Cost policy](../router/cost_policy.py) requires dated, finite loopback contracts
  and rejects unsupported request surfaces. Free-first selection is deterministic;
  paid fallback remains possible only when compatible and within all limits.
- [Jev](../router/jev_classifier.py) receives current server estimates and remaining
  budgets, is itself reserved under the same logical request, binds its actual
  endpoint/model/output cap, and rechecks eligibility after its own charge.
- [Ledger](../router/spend_ledger.py) records each physical attempt in integer USD
  nanodollars with canonical and alias/deployment attribution. SQLite transactions
  atomically enforce overall/model UTC daily/monthly caps and a request ceiling.
  Only authoritative final settlement releases capacity; incomplete streams,
  cancellation and unknown charges retain conservative exposure. Conflicting
  charge evidence or a breached bound cannot silently free capacity.
- [Report/import CLI](../tools/cost_report.py) exposes spend, estimates, remaining
  limits, reset times, pending/unknown amounts and scoped historical coverage.
  Repeat aggregates are deduplicated; explicit nonoverlapping opening balances
  affect provider-period caps. Overlap or unknown history is not treated as zero.

`router-only` coverage describes traffic recorded here. `provider-period` coverage
requires matching scope, explicit coverage evidence and known nonoverlapping
history before admission. Local reports do not reconstruct missing account history.
See [operations](operations.md) for import and coverage-attestation arguments.

Only loopback text-chat and bounded Decisions fixtures are supported in strict
mode. These contracts do not establish bounds for live image/audio/reasoning,
provider-added fees or alpha Decisions. Live endpoints remain refused until a
verified billing contract can support the guarantee.

The real [proxy harness](../tools/local_proxy_probe.py) and
[budget/concurrency matrix](../tools/proxy_budget_matrix.py) are the required
integration seams. Their final results and review outcomes are retained in the receipt; focused
checks alone do not fulfill the delivery contract.

## Historical research recommendation (superseded where noted)

The sections through "Proposed delivery order" below preserve the initial research
recommendation. They describe upstream options and earlier proposals, not the
current implementation. The accepted contract and current-code section above
supersede staged shadow-only/model-choice proposals and pre-pin uncertainty.

Keep LiteLLM as the gateway and accounting foundation. Add a small server-owned
cost-context adapter for Jev, and use deterministic eligibility checks around
paid dispatch. Do not start with a second accounting system or a gateway migration.
This is a recommendation, not an adopted spending policy or implementation.

Three distinct outputs are needed: estimated price of a choice, recorded spend,
and permission to incur the next charge. Jev can use the first two; code must
enforce the third. Preserve free-first routing and paid continuity within the
eventually selected budgets and capability requirements.

## What to reuse, and what needs verification

| Need | Existing upstream facility | Project implication |
|---|---|---|
| Spend visibility | LiteLLM database logs and Usage UI | Establish the database and reconcile actual model identity before building a custom dashboard. |
| Overall budget | Virtual-key and provider budgets | Use a dedicated application key; keep unrelated account activity outside router totals. |
| Model budget | Deployment `max_budget` / `budget_duration` | Counters are keyed by deployment ID; shared-model aliases must not fragment the intended cap. |
| Per-key model cap | `model_max_budget` | Enterprise in current docs; do not confuse this with deployment-level configuration. |
| Cheapest candidate | Async `cost-based-routing` | Inspected source ranks input plus output rates; request-specific token mix needs an estimate adapter. |
| Jev accounting | New native TypeSafe Jev integration | Different transport from our direct OpenRouter alpha call; migration requires explicit compatibility work. |
| Eligibility filter | Routing plugins | Candidate narrowing is distinct from tier classification; verify all actual dispatch paths. |

Sources: [spend](https://docs.litellm.ai/docs/proxy/cost_tracking),
[budget routing](https://docs.litellm.ai/docs/proxy/provider_budget_routing),
[key budgets](https://docs.litellm.ai/docs/proxy/users),
[rate-selection source](https://github.com/BerriAI/litellm/blob/main/litellm/router_strategy/lowest_cost.py),
[budget-counter source](https://github.com/BerriAI/litellm/blob/main/litellm/router_strategy/budget_limiter.py),
[Jev setup](https://docs.litellm.ai/docs/auto_router/setup),
[routing plugins](https://docs.litellm.ai/docs/routing_plugins).

Our plugin's `classify` returns a tier. It cannot select arbitrary candidate
model IDs without changing the adapter contract. For the first slice, retain
capability classification and choose an eligible model within that capability.
Giving Jev direct model choice is a later benchmarkable option. Current behavior
and bypass paths are documented in [classifier](classifier.md),
[quota guard](quota-guard.md), and [routing](routing.md).

## Proposed cost snapshot

Compute this on the server, not from user-supplied prompt fields:

- Snapshot time, pricing source/version, currency, and accounting coverage.
- Candidate alias, canonical upstream model, deployment ID, capability and health.
- Expected input/output cost and a conservative estimate using the output cap;
  incorporate cache, reasoning, request and modality charges where applicable.
- Spent today/month, outstanding reservations if supported, configured limit,
  budget period/reset, and eligible/ineligible reason.

Estimate the full solver request, including tool results and history; Jev's
shortened classification transcript is not the solver token count. Unknown cost
stays unknown. Give Jev compact summaries; keep the transaction history outside
its prompt. Prices and budgets are distinct from measured quality.

## Existing spend and reconciliation

Use [OpenRouter activity](https://openrouter.ai/docs/api/api-reference/analytics/get-user-activity)
for available historical backfill: 30 completed UTC days, management key required.
Today's per-model spend needs local request accounting; the
[ordinary key endpoint](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)
provides aggregate key usage. These are different scopes.

Keep provider daily aggregates as reconciliation data rather than adding them
to overlapping local charges. Import any opening balance with explicit coverage,
account/key scope and provenance. Older missing history cannot be reconstructed
from model prices. Use UTC accounting windows and display the timezone.

Store both calculated and provider-reported amounts when available. Count each
physical billable attempt exactly once, linked to its logical request. Include
classification, failures with usage, fallbacks and canceled streams. Missing final
usage is pending/unknown until resolved. The
[OpenRouter response accounting contract](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
does not prove alpha Decisions exposes the same fields.

## Budget boundaries

Recorded-spend caps are not proof of a strict no-overspend guarantee. Native
examples let a crossing request complete. If strict ceilings are required,
test atomic reservation, bounded output, settlement, cancellation and concurrency
against a pinned version before adding only the missing mechanism.

Recheck paid eligibility for direct aliases, free-quota rewrites, classifier
failure/defaults, and every fallback. Auth-layer
[budget fallbacks](https://docs.litellm.ai/docs/proxy/budget_fallbacks)
are separate from provider-error fallbacks. An uncapped fallback is not a budget
guarantee. Avoid blindly using `paid-emergency` when its eventual model/cost cannot
be bounded. Any policy change requires a separately accepted contract.

## Other routers: what is useful here

| Project | Lesson to borrow | Fit assessment |
|---|---|---|
| [RouteLLM](https://github.com/lm-sys/RouteLLM) | Calibrate cheap/strong routing on representative work. | Benchmark reference, not a replacement for accounting. |
| [vLLM Semantic Router](https://github.com/vllm-project/semantic-router) | Cost selection within an eligible quality band. | Design reference; no reason established to migrate. |
| [Bifrost](https://github.com/maximhq/bifrost) | Model usage visibility and per-attempt settlement. | Credible alternative; cap and multi-node limits still need attention. |
| [Portkey](https://github.com/Portkey-AI/gateway) | Observable routing decisions and metadata. | Check hosted/Enterprise boundaries before assuming OSS availability. |

The [comparison evidence](../raw/notes/2026-09-21-other-routers-research.md)
links inspected files, documentation, limitations and proposed upstream work.
No vendor savings or performance claim has been reproduced for this workload.

## Proposed delivery order and acceptance

1. Pin the deployment version; establish database-backed logs and actual-model
   attribution. Verify native Jev suitability versus preserving the current adapter.
2. Deliver per-model today/month totals with unknown/pending counts, classifier
   overhead and historical coverage. Deduplicate overlapping import/replay data.
3. Add dated request estimates and shadow cost-context decisions; compare with
   current routing on representative coding/reasoning/agentic/general requests.
4. Apply agreed budgets and cheapest-eligible selection after capability and
   quality checks. Measure total task cost including rework, not just token rate.

Focused checks must cover shared aliases, free-to-paid transitions, direct paid
calls, classifier accounting, emergency paths, missing/stale prices, final stream
usage, duplicate attempts, budget resets, restarts and concurrent requests.
Live billing validation is a separate authorized step. Research-only structural
checks do not certify these behaviors.

Related: [architecture](architecture.md), [operations](operations.md),
[evaluation](evaluation.md), [open questions](open-questions.md).

## Accepted implementation contract, 2026-09-21

The [user contract](../raw/notes/2026-09-21-cost-aware-router-contract.md) supersedes
the historical staged recommendation: Jev selects among eligible models using a
server snapshot, while deterministic reservations cover every physical attempt.
Unknown or unbounded charges are ineligible; unresolved reservations retain
capacity. Pinned real-proxy proof and two consecutive clean independent reviews
are required before local completion. Those local gates passed; the live billing
bound remains unresolved. No live budget values have been chosen.

LiteLLM remains the gateway, deployment resolver, complexity-router host and
fallback executor. The custom strict ledger/transport addresses verified native
reservation gaps described in the [delivery plan](router-delivery-plan.md).
Native spend logs and this ledger must not be added together as independent
charges. Historical run statements remain in the append-only [log](log.md),
alongside corrections to their evidence scope.
