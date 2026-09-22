# Open questions and verification gaps

Current amendment, 2026-09-21: see the [review and delivery plan](router-delivery-plan.md) for current implementation findings and acceptance tests. The original imported-source rows below remain historical evidence. Current strict-mode gaps include final fallback capability enforcement, exact outgoing bounds and classifier endpoint binding, partial-stream finality, shared-alias attribution, scoped historical opening balances, and price freshness. Both independent reviews are not clean; the delivery goal remains paused.

Status: unresolved source findings, 2026-09-20. No router behavior was changed during ingestion.

| ID | Finding and evidence | Next verification or decision |
|---|---|---|
| Q001 | No version lock, deployment files, database setup, or live results were imported. [Bootstrap](../raw/notes/2026-09-20-workspace-bootstrap.md) | Establish deployment environment and validate plugin/callback integration before claiming readiness. |
| Q002 | Classifier header says solvers remain free; config and quota map include paid routes. [Classifier](../raw/jev_classifier.py), [config](../raw/config.yaml) | Wiki describes actual free-first behavior. Correct the working-copy comment in a future code change. |
| Q003 | Config descriptions target 97.5–98% availability; health contracts use 95% for ordinary tiers. Discovery eligibility needs only a current success. [Config](../raw/config.yaml), [health](../raw/test-models.py), [discovery](../raw/discover-free-models.py) | Decide the intended measurement window and acceptance contract before enforcing one number. |
| Q004 | Benchmark Jev payload uses `state.record` / `routing_tier`; runtime uses `state.records` / `tier`, with different prompts and parsing. [Benchmark](../raw/benchmark-classifiers.py), [classifier](../raw/jev_classifier.py) | Verify current API shapes and determine whether to benchmark the real plugin or keep a separate experiment. |
| Q005 | Benchmark chat model names are absent from imported config. `OPENROUTER_LUNA_MODEL` does not replace the hardcoded list entry; header key requirements are stale. [Benchmark](../raw/benchmark-classifiers.py), [config](../raw/config.yaml) | Establish valid benchmark routes and align supported overrides/documentation. |
| Q006 | Stale quota snapshots are reused even with fail-open disabled. Cached state is process-local, not reserved or coordinated. [Quota guard](../raw/openrouter_quota_guard.py) | Decide stale-data policy; test unknown, stale, exhausted, concurrent, and multi-worker paths. |
| Q007 | Generated routing recommendations specify emergency `cost_tier: low`; imported `paid-emergency` config has no such parameter. [Discovery](../raw/discover-free-models.py), [config](../raw/config.yaml) | Validate supported cost controls before claiming emergency spend is constrained. |
| Q008 | Specialized fallback compatibility is unproven; vision ends at generic auto, while compression omits emergency. [Config](../raw/config.yaml) | Verify image and context preservation throughout each allowed fallback chain. |
| Q009 | Small capability probes sometimes provide the answer and do not establish deep or long-context competence. [Discovery](../raw/discover-free-models.py), [health](../raw/test-models.py) | Use representative workload evidence before claims of model quality or production SLA. |
| Q010 | Model slugs, prices, free quota API fields, and the comment about a community auto-router limit are not live-verified. [Config](../raw/config.yaml), [quota guard](../raw/openrouter_quota_guard.py) | Check upstream primary documentation/catalog against the chosen deployed version. |
| Q011 | Health aliases/upstreams duplicate config, and missing fallback headers default to zero. [Health](../raw/test-models.py) | Check table drift and actual diagnostic headers; a zero fallback count alone is insufficient proof. |
| Q012 | Classifier metadata filtering can discard real user text; environment integer parsing happens outside the API exception handler. [Classifier](../raw/jev_classifier.py) | Add focused boundary tests when classifier behavior is next changed. |
| Q013 | Cost research identifies native accounting, deployment budgets, and a newer TypeSafe Jev integration; installed version/edition and compatibility with eight custom tiers remain unknown. [Research](cost-awareness.md) | Pin a release and verify accounting, licensing, plugin contract and transport before choosing integration. |
| Q014 | Shared-model aliases can split deployment budget counters; recorded-spend checks do not establish atomic reservation. [Research](cost-awareness.md) | Decide budget scope and acceptable overshoot; test all paid dispatch paths and concurrency. |
| Q015 | Available historical provider activity covers 30 completed UTC days; local/current-day coverage and alpha Decisions usage are unverified. [Evidence](../raw/notes/2026-09-21-cost-aware-router-research.md) | Reconcile scoped history without double counting; expose pending/unknown charges and coverage. |

These findings are documentation of the current import, not authorization for a
broader rewrite. Next implementation work should select a concrete gap and record
its intended behavior through the [wiki workflow](workflow.md).

Related: [decisions](decisions.md), [operations](operations.md), [evaluation](evaluation.md).

## Implementation contract update, 2026-09-21

[Accepted contract and correction](../raw/notes/2026-09-21-cost-aware-router-contract.md) resolves Q014 policy: strict reservations with no premature capacity release, not acceptable overshoot. Q010 schema evidence now confirms the documented free quota object, while runtime availability remains unverified. Q013 still requires a pinned hook/accounting audit. Alpha Decisions bounded billing/token contract remains unresolved; do not enable unbounded paid dispatch to satisfy a test.

## Current strict-mode boundary, 2026-09-21

Local fake endpoints have a declared bounded charge contract and are verified.
OpenRouter alpha Decisions exposes post-call usage but no documented request-level
maximum charge. This prevents a strict live reservation for Jev. Live provider
activation, actual provider billing, and deployment remain unresolved; the router
must reject such a classifier/endpoint in strict cost-aware mode rather than infer
a limit from prices or use zero.

## Resumed local implementation checkpoint

The 2026-09-21 execution addresses Q012 transcript filtering and validates the pinned 1.99.0 plugin/hook seam locally (Q013). Q014 has canonical atomic reservations and real concurrent-worker proof. Q015 has scoped idempotent imports, explicit opening balances and coverage; daily provider aggregates cannot establish the partial activation day, so provider-period admission remains closed when that coverage is absent. Earlier table entries describe the imported snapshot, not current code. Final proof and review outcomes belong in the delivery receipt. Live bounds, real provider billing, real model quality and deployment remain unresolved.
