# Operations and GitHub workflow

Status: source-derived operating guide, 2026-09-20; deployment steps are pending validation.
Sources: [config](../raw/config.yaml), [classifier](../raw/jev_classifier.py),
[quota guard](../raw/openrouter_quota_guard.py), [discovery](../raw/discover-free-models.py),
[health](../raw/test-models.py), [benchmark](../raw/benchmark-classifiers.py),
[bootstrap note](../raw/notes/2026-09-20-workspace-bootstrap.md).

## Offline workspace checks

From the repository root, run `py -3 tools/check_workspace.py` on Windows or
`python tools/check_workspace.py` elsewhere. Python 3.10+ is required by the
imported source syntax. The check uses no third-party packages or provider keys.
GitHub Actions runs it on pushes and pull requests.

## Deployment prerequisites

No working dependency lock, container definition, service manager, database setup,
or known-compatible LiteLLM version was supplied. A one-command deployment recipe
would therefore be speculative. Before the first deployment:

1. Identify and record the intended Python/LiteLLM versions and deployment host.
2. Provide the dependencies referenced by imports: `httpx`; for the callback,
   `fastapi` and `litellm`, plus the proxy's own installation requirements.
3. Make `router/jev_classifier.py` and `router/openrouter_quota_guard.py` importable
   under the module names used by `router/config.yaml`.
4. Provide the configured environment and a compatible database; validate config,
   custom classifier loading, callback loading, and database connectivity.
5. Verify a direct alias, `jev`, fallbacks, quota rewrites, error responses, and
   diagnostic headers. Include streaming if the intended client uses it.
6. Record exact commands, versions, sanitized evidence, and rollback procedure
   here once validated. Do not substitute a syntax check for these checks.

## Environment reference

| Scope | Variables |
|---|---|
| Proxy config | `LITELLM_MASTER_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY` |
| Classifier | `OPENROUTER_API_KEY`; optional `JEV_*` values in [classifier](classifier.md) |
| Quota callback | Provider key and `OPENROUTER_QUOTA_*` controls in [quota guard](quota-guard.md) |
| Health checker | `LITELLM_API_KEY`; `LITELLM_URL` defaults to `http://127.0.0.1:4000` |
| Discovery | `OPENROUTER_API_KEY`; `DISCOVERY_OUTPUT_DIR` defaults to `/tmp/openrouter-free-discovery` |
| Classifier benchmark | `OPENROUTER_API_KEY`, `LITELLM_API_KEY`; same default `LITELLM_URL` |

Health defaults: `ROUTER_HEALTH_RUNS=3`, `ROUTER_HEALTH_RPM=10`,
`ROUTER_PAID_HEALTH_RPM=60`, `ROUTER_HEALTH_DELAY=0`,
`MODEL_HEALTH_TIMEOUT=30`, `JEV_HEALTH_TIMEOUT=60`, `ROUTER_TEST_BACKUPS=1`.

Discovery defaults: `DISCOVERY_RUNS=3`, `DISCOVERY_RPM=18`,
`DISCOVERY_PAID_RPM=60`, `DISCOVERY_TIMEOUT=30`, `DISCOVERY_PROBE_DELAY=0`,
`DISCOVERY_MAX_MODELS=0` (all), `DISCOVERY_VERBOSE=0`,
`DISCOVERY_INCLUDE_SPECIALIZED=0`. Paid eligibility price ceilings default to zero
(disabled); see [evaluation](evaluation.md) before treating them as cost controls.

Benchmark defaults: `CLASSIFIER_BENCH_RUNS=3`, `CLASSIFIER_BENCH_TIMEOUT=30`,
`CLASSIFIER_FREE_RPM=18`, and `JEV_MODEL=typesafe/jev-1.13`.
Additional model-name overrides have the limitations recorded in [open questions](open-questions.md).
Provider keys for chat classifiers stay in the proxy environment; the benchmark
code itself does not read `OPENAI_API_KEY`, despite its older header comment.

## Deliberate live checks

These commands require a configured environment and a compatible `httpx` install.
They are reference commands, not proof they were run. The first consumes free
quota; the latter two can generate paid calls. Ordinary documentation ingestion
does not authorize running a live benchmark or changing deployed routing.

```powershell
# Explicit free-only discovery, bounded to one selected catalog candidate.
$env:DISCOVERY_OUTPUT_DIR = Join-Path $PWD 'outputs/discovery'
py -3 tools/discover-free-models.py --no-paid --max-models 1

# Exercise configured free AND paid proxy routes.
py -3 tools/test-models.py

# Requires classifier models to be available through the proxy first.
py -3 tools/benchmark-classifiers.py
```

Set credentials locally using your chosen secret mechanism. An ignored `.env` can
store local settings, but these scripts do not automatically load it. Never paste
real key values into examples, commits, wiki pages, or raw notes. Logs and raw
provider errors require review before publication.

## GitHub conventions

Use the [designated repository](https://github.com/bct9321/litellm-router).
The in-repository `wiki/` is canonical, so source, code, and docs share review and
history. Use short descriptive branches for subsequent changes; document the
problem, behavior, verification, and wiki impact in review descriptions.
Keep `.env`, virtual environments, caches, and transient `outputs/` untracked.
Commit useful sanitized evidence as a new dated raw artifact.

Git preserves raw bytes through `.gitattributes`; the manifest checks them.
Working copies can evolve after bootstrap. Before publishing, inspect the diff,
run the offline check, review sensitive content, and record remaining runtime gaps.
Publishing the repository does not deploy the proxy. No license has been selected;
do not invent the owner's licensing terms.

Related: [workflow](workflow.md), [decisions](decisions.md), [log](log.md).
