# LiteLLM Router

A wiki-first workspace for a Hermes-facing LiteLLM router using Jev classification,
OpenRouter solvers, free-first routing, and explicit paid fallback paths.

**Start with the [project wiki](wiki/index.md).** It explains the design, source
provenance, operating rules, and known gaps. Agents follow [AGENTS.md](AGENTS.md).

## Workspace

| Path | Purpose |
|---|---|
| [wiki/](wiki/index.md) | Maintained architecture, behavior, decisions, and operating knowledge |
| [raw/](raw/) | Immutable imported sources and dated requirement/evidence notes |
| [router/](router/) | Editable LiteLLM config and classifier/quota plugins |
| [tools/](tools/) | Discovery, health checking, classifier benchmarking, offline checks |
| [CONTEXT.md](CONTEXT.md) | Shared project vocabulary |

The workflow is **raw evidence → wiki synthesis → implementation → verification →
wiki reconciliation**. It follows the three-layer pattern in
[Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
The wiki lives in this repository, alongside code and its review history.

## Current status

Implementation resumed on 2026-09-21 under the [execution authorization](raw/notes/2026-09-21-router-plan-execution.md).
LiteLLM 1.99.0 is pinned. The strict adapter, durable spend ledger, classifier
controls and local fake-upstream harnesses passed final local verification and
two consecutive clean independent reviews. See the [receipt](raw/notes/2026-09-21-local-delivery-receipt.md),
[delivery plan](wiki/router-delivery-plan.md) and [checkpoint log](wiki/log.md).
This is not a live billing or deployment certification.

The original eight tiers and direct aliases remain available in legacy mode.
Strict mode adds deterministic authorization before each supported physical
attempt. Free-first permits compatible paid fallback only within explicit limits.

## Local verification

The pinned proxy requires Python 3.11 or later (the local proof used 3.12).
The structural workspace check still runs with Python 3.10 or later:

```powershell
py -3 tools/check_workspace.py
```

On other platforms use `python tools/check_workspace.py`. This check uses only the
standard library and makes no API calls. CI runs the same check.

For deployment prerequisites and deliberate live checks, read
[operations](wiki/operations.md). For the remaining integration work, read
[open questions](wiki/open-questions.md).

## Strict cost-aware local mode

Use the Python 3.12 environment installed from [requirements.txt](requirements.txt)
for runtime checks:

```powershell
$env:CUSTOM_TIKTOKEN_CACHE_DIR = Join-Path $PWD 'outputs/token-cache'
.venv312\Scripts\python.exe tools\local_proxy_probe.py
.venv312\Scripts\python.exe tools\proxy_budget_matrix.py
```

These harnesses start temporary real LiteLLM proxies and deterministic loopback
HTTP services, then stop them. Their presence is not a claim that the final tree
has passed; the [log](wiki/log.md) records actual runs and limitations.

The cost callback is loaded by [router/config.yaml](router/config.yaml) but
activates only when `COST_ROUTER_CONFIG` names a local JSON policy conforming to
[cost-router.schema.json](router/cost-router.schema.json). It requires explicit
finite nanodollar limits, trusted deployment identities, current dated billing
contracts and enforced output caps. Only bounded loopback text-chat and Decisions
fixtures are supported. Live provider contracts are rejected; no live limits
have been invented.

[Operations](wiki/operations.md) documents runtime setup, focused checks and the
local spend/history report. The report accepts sanitized historical files without
account access. Overlap is not silently added to local charges; provider-period
coverage must be explicitly established before admission.

Repository: [bct9321/litellm-router](https://github.com/bct9321/litellm-router).
