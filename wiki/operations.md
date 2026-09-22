# Operations and GitHub workflow

Status: current local operating guide, 2026-09-21. Implementation has resumed;
final local integration and two clean independent reviews passed. See the
[receipt](../raw/notes/2026-09-21-local-delivery-receipt.md) for exact commands, exits and proof.
Sources: [execution authorization](../raw/notes/2026-09-21-router-plan-execution.md),
[delivery plan](router-delivery-plan.md), [requirements](../requirements.txt),
[working config](../router/config.yaml), and [report CLI](../tools/cost_report.py).
Imported 2026-09-20 sources remain provenance, not current runtime instructions.

## Runtime setup and local checks

LiteLLM 1.99.0 and jsonschema 4.26.0 are pinned. Use Python 3.12 for the local
runtime; the verified environment is `.venv312`. These are setup instructions,
not a claim of a fresh clean-machine installation:

```powershell
py -3.12 -m venv .venv312
.venv312\Scripts\python.exe -m pip install -r requirements.txt
.venv312\Scripts\python.exe tools\prepare_tokenizer_cache.py
```

The tokenizer helper's default mode checks public artifact checksums without
network access. If those files are missing, its explicit `--download` option
fetches the known public artifacts and verifies their hashes. No provider key is
needed. A new download/clean-machine setup has not been verified in this execution.

```powershell
$env:CUSTOM_TIKTOKEN_CACHE_DIR = Join-Path $PWD 'outputs/token-cache'
.venv312\Scripts\python.exe tools\local_proxy_probe.py
.venv312\Scripts\python.exe tools\proxy_budget_matrix.py
.venv312\Scripts\python.exe -m unittest discover -s tools -p 'test_*.py'
py -3 tools\check_workspace.py
```

The two harnesses start temporary real LiteLLM proxies and deterministic fake
loopback services, then stop them. The matrix separately targets overall/model
UTC day/month and request caps plus synchronized multi-process admission.
Inspect the unique output directories and [log](log.md) for actual run results.
These commands are not a persistent production service start recipe.

`py -3 tools/check_workspace.py` is the standard-library-only structural check
(Python 3.10+); it does not certify runtime routing or budgets. All dependency-backed
runtime checks above use `.venv312\Scripts\python.exe`.

## Activation and live boundary

The supplied config loads the cost callback before quota rewriting. Without
`COST_ROUTER_CONFIG`, strict controls are inactive. A local policy must conform to
[cost-router.schema.json](../router/cost-router.schema.json): explicit finite
integer USD-nanodollar limits; trusted deployment IDs and route membership; dated
origin/path/model billing contracts; supported request surfaces and output caps.
Workers share the same local SQLite ledger and full policy fingerprint. Changing
policy against an existing ledger is deliberately refused rather than silently
reinterpreting prior accounting.

Strict mode currently supports bounded loopback text-chat and Decisions fixtures.
Unsupported modalities, missing/stale bounds and live provider contracts are
rejected. Real OpenRouter/alpha Decisions billing bounds and deployment remain
unverified. No live limits are supplied here. A live service recipe requires those
contracts and separately authorized operational verification.

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
.venv312\Scripts\python.exe tools/discover-free-models.py --no-paid --max-models 1

# Exercise configured free AND paid proxy routes.
.venv312\Scripts\python.exe tools/test-models.py

# Requires classifier models to be available through the proxy first.
.venv312\Scripts\python.exe tools/benchmark-classifiers.py
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

## Spend reports and historical files

The report requires the same policy path, ledger scope and configured limits. It
reads no credentials and makes no provider call:

```powershell
.venv312\Scripts\python.exe tools\cost_report.py --config <policy.json>
.venv312\Scripts\python.exe tools\cost_report.py --config <policy.json> --openrouter-activity <sanitized-activity.json> --history-scope <scope> --history-disposition comparison-only
```

Reports expose canonical-model and overall UTC today/month spend, estimates,
remaining limits, reset times, separate pending/unknown counts and exposure,
identity-attributed attempts, imported history and coverage. Unknown coverage
makes remaining capacity null; it is never reported as zero spend.

`coverage_mode: router-only` covers this ledger's local traffic only. It does not
claim complete provider/account spend. `coverage_mode: provider-period` requires
explicit matching `billing_scope`, complete history coverage and nonoverlapping
opening balances before admitting traffic. The CLI supports:

- `--history-disposition opening-balance` only for proven nonoverlapping history;
  overlapping rows are rejected instead of counted twice.
- `--history-disposition unresolved` for history that cannot establish a balance.
- `--history-revision <integer>` for explicit newer corrections; repeat equivalent
  imports remain idempotent even when `--source` changes.
- `--coverage-attestation <file.json>` with reviewed `scope`, `start` and `end`
  timestamps. This is an assertion of external evidence, not evidence itself;
  absent rows do not establish zero historical usage.

`history_model_map` maps provider IDs to canonical model budgets. Default history
imports are comparison-only and do not expand coverage. Available downloaded
OpenRouter activity can be developed/tested locally without account access;
missing old history or ambiguous overlap remains explicitly unresolved. See
[cost awareness](cost-awareness.md) and the [ledger](../router/spend_ledger.py).
