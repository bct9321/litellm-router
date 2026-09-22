# Open questions and verification gaps

Current design reference: [free-first callback design](semantic-routing-alternative.md). Exact failure-to-subscription mappings, error/retry policy, direct-subscription fallback chains, quota/classifier failures and paid API controls remain unresolved. Earlier Auto Router compatibility blockers below are historical rationale for the callback proposal, not a claim that it has been implemented.

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

These findings are documentation of the current import, not authorization for a
broader rewrite. Next implementation work should select a concrete gap and record
its intended behavior through the [wiki workflow](workflow.md).

Related: [decisions](decisions.md), [operations](operations.md), [evaluation](evaluation.md).

## Twenty-tier operational gaps — 2026-09-22

[Scope evidence](../raw/notes/2026-09-22-twenty-tier-scope.md): ChatGPT access to the requested Luna/Terra/Sol IDs, actual OAuth persistence/restart, Responses streaming and subscription limits remain unverified. No container definition/remote host is supplied. Issue #28044 is historical reported evidence, not a verified defect in the installed version. The existing sixteen-case benchmark covers only lower tiers and is not twenty-class quality evidence.

## Blocking LiteLLM tier cap

[Reproduction](../raw/notes/2026-09-22-tier-limit-evidence.md): installed 1.99.0 and upstream main cap custom definitions at eight. Twenty-tier configuration currently fails validation. Compatibility approach awaits user direction; model access is a separate unresolved issue.

## Required input and review defects

[Failed-state audit](../raw/notes/2026-09-22-expanded-tiers-blocked-audit.md): a supported twenty-tier LiteLLM approach or explicit revised compatibility authorization is needed. Both independent reviews are not clean. Draft CAPABLE semantics must be restored and failure tests added after the stop condition is resolved. Top-level jev quota behavior versus eventual ChatGPT-route isolation is a distinct scope question.

## Five-tier design: two installed API prerequisites missing

[Audit](../raw/notes/2026-09-22-five-tier-api-audit.md): LiteLLM 1.99.0 rejects plugins with custom tier definitions even for five tiers; its custom classifier accepts only a tier string and does not forward family signals/metadata to the filter. Router-level plugins run too early on provider model candidates. A signal-only compatibility change would not resolve custom-tier/plugin incompatibility. Stop pending supported interfaces or revised scope; never patch the tier cap.

## Upgrade investigation and alternative choice

[Fresh upstream research](../raw/notes/2026-09-22-upstream-five-tier-research.md) finds no supported upgrade in v1.102.0 or inspected main. [Concrete callback alternative](semantic-routing-alternative.md) awaits user choice because five capability levels would become application policy, not built-in Auto Router tiers. Independent proposal review also identified a fallback-root change that must be preserved explicitly and verified before any implementation is accepted.

## Current resolutions — 2026-09-22

The user authorized the callback alternative in [R007](decisions.md); earlier
awaiting-choice and blocked-draft statements above are historical. Current YAML
uses no complexity Auto Router. CAPABLE wording is restored and regression-tested.
Q001 now has a pinned offline dependency set and callback/Router tests, but database,
deployment and live compatibility remain open. Q006 stale snapshot handling is
fixed and tested as unknown; multi-worker quota reservation remains unresolved.
The current [implementation boundaries](semantic-routing-alternative.md) cover the
accepted fallback changes and narrow supported input surface. Live model quality,
model slug availability and OAuth remain open; no login was performed.
