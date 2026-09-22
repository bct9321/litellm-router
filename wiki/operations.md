# Operations and GitHub workflow

Current scope (2026-09-22): [free-first callback implementation](semantic-routing-alternative.md) passes offline tests; two independent clean reviews are recorded in the [acceptance receipt](../raw/notes/2026-09-22-callback-acceptance.md). Historical source descriptions below retain their dates and are superseded where that page differs. OAuth/login, deployment and live subscription compatibility remain unverified.

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

## ChatGPT OAuth persistence — prepared setup, 2026-09-22

[Scope and version evidence](../raw/notes/2026-09-22-twenty-tier-scope.md).
No container definition or accessible deployment host is provided. Apply these
settings to the existing LiteLLM service on its actual host; this is a fragment,
not a standalone deployment:

```yaml
services:
  litellm:
    environment:
      CHATGPT_TOKEN_DIR: /app/chatgpt-auth
    volumes:
      - /mnt/user/appdata/litellm/chatgpt-auth:/app/chatgpt-auth
```

Create the host directory with access for the container user. Keep it writable
for token refresh, private, outside Git, and separate from the config mount.
Keep the twelve new deployments in YAML with `model_info.mode: responses`.
The repository ignores `chatgpt-auth/` for an equivalent local directory.

After recreating the intended service with the persistent mount, authenticate
interactively inside that container (replace `LiteLLM` with its actual name):

```sh
docker exec -it LiteLLM python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().get_access_token(); print('ChatGPT authentication complete')"
```

Complete the displayed device flow yourself. This command deliberately does not
print or retain the returned token. Do not paste auth.json or tokens into chat.
Authentication is separate from inference: no model call is needed to save tokens.
Verify that the private file persists across a container recreation before using
live routes. Authentication, restart persistence, model availability and streaming
have not been verified in this task.

Historical [issue 28044](https://github.com/BerriAI/litellm/issues/28044) reports a
DB-registration/streaming difference in older releases. It supports keeping these
entries in YAML; it is not proof of an active defect in 1.99.0.

The twenty-tier config currently hits LiteLLM's eight-tier validation cap. Resolve
that recorded compatibility blocker before loading it into a service. This branch
excludes the separate strict-cost implementation.

## Callback offline verification (2026-09-22)

Use Python 3.12 with [requirements](../requirements.txt). From the repository root:

```powershell
.venv312\Scripts\python.exe -m unittest tools.test_callback_routing tools.test_twenty_tiers tools.test_routing_signal_api
py -3 tools/check_workspace.py
```

Tests substitute classifier/quota HTTP and solver transports; no provider keys or
live model calls are needed. A local tiktoken cache may be required on first import;
`outputs/token-cache` is used by the suites. Never treat offline success as model
availability proof. Keep the repository root on PYTHONPATH when launching the proxy
with `router/config.yaml`, so the `router.jev_router` callback and provider load.
No proxy launch, database migration or OAuth login is part of this verification.
