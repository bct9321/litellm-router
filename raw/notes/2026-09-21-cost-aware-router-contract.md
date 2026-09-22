# Cost-aware router implementation contract

Date: 2026-09-21. Origin: user's explicit goal in this task.
Status: accepted requirements; implementation and local integration pending.

Deliver a locally verified LiteLLM plus Jev router. Jev chooses eligible models
using server-calculated full-request estimates, capabilities and current spend.
Deterministic code must enforce finite configured overall and canonical-model
daily/monthly budgets and a per-request ceiling at every physical dispatch,
including classification, direct aliases, quota rewrites and all fallbacks.
Preserve free-first and capability-compatible paid fallback. No live budget
amounts are supplied; do not invent them. Reject unpriceable paid candidates.

Reserve conservative bounded charges atomically before dispatch. Persist attempts
across concurrent workers/restarts, preserve alias/deployment attribution, include
failed billable attempts and Jev overhead, deduplicate events, and distinguish
estimated, provider-reported, pending and unknown amounts. Unresolved charges do
not release capacity prematurely. Reconcile historical imports without counting
overlapping local activity twice. Expose today/month spend, estimates, remaining
budgets, reset times and coverage through an operator report/API. Accept available
OpenRouter historical backfill offline; account access is not a development gate.

Repair stale quota, refresh backoff, transcript filtering, benchmark accounting,
unknown prices, missing diagnostics and answer-leaking vision tests. Evaluate the
production classifier seam, not a separately implemented approximation.

Public verification seams authorized by the goal: production classifier call,
quota callback, operator report/accounting interface, benchmark/health tools,
and actual pinned LiteLLM proxy HTTP requests to deterministic fake upstreams.
Prove streaming, persistence, routing, alias sharing, concurrency, restart,
duplicate events, cancellation, stale/missing prices, classifier failure and
emergency fallback. Focused RED checks precede behavior changes. Require two
consecutive independent adversarial reviews with no medium-or-higher finding;
any fix restarts that count. Run py -3 tools/check_workspace.py and leave exact
commands, exit codes, scenario results, proof and configuration instructions.

Preserve dirty work and existing raw bytes; use a reviewable branch. Pin a
compatible LiteLLM and reuse verified accounting/control facilities, implementing
only gaps in router/, tools/, focused tests and necessary configuration. No
secrets, provider charges, live service/billing changes, publish, merge, deploy or
gateway migration. If real integration or bounded billing cannot be supported,
finish independent work, identify the precise blocker and do not claim completion.

## Additive correction to quota research

Supersedes item 12's schema-absence claim in
[prior research](2026-09-21-cost-aware-router-research.md); original preserved.
On 2026-09-21 the official
[current API key reference](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key)
shows data.free_model_daily_requests with limit, remaining and used. Therefore
the imported field name is documented. This establishes schema evidence only,
not account-specific availability, freshness, reservation or runtime behavior.
Missing/malformed data must still be handled as unknown.

## Initial local evidence

Python 3.10.2 is available; LiteLLM is not installed in that interpreter.
Created an isolated .venv. Initial package-index access failed with Windows socket
permission error 10013; this is a network restriction, not evidence that the
package/version does not exist. The requested review branch is
codex/cost-aware-router; pre-existing research/wiki changes are preserved.
