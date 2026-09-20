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

The six supplied files have been preserved and copied into working locations.
Documentation describes their inspected behavior as of 2026-09-20. This bootstrap
does not establish a running proxy or validate model availability, latency, cost,
or compatibility with a particular LiteLLM release.

The router has eight classification tiers, direct `fast` / `vision` / `compression`
aliases, and paid safety paths. **Free-first does not mean free-only.**

## Local verification

With Python 3.10 or later, from the repository root:

```powershell
py -3 tools/check_workspace.py
```

On other platforms use `python tools/check_workspace.py`. This check uses only the
standard library and makes no API calls. CI runs the same check.

For deployment prerequisites and deliberate live checks, read
[operations](wiki/operations.md). For the remaining integration work, read
[open questions](wiki/open-questions.md).

Repository: [bct9321/litellm-router](https://github.com/bct9321/litellm-router).
