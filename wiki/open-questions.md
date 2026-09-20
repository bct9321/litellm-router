# Open questions and verification gaps

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
