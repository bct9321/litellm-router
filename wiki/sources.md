# Source register

Ingested: 2026-09-20. Original authorship, creation dates, runtime versions, and
deployment history of the six supplied files were not provided. Their source is
the user's initial `raw/` folder, not the upstream LiteLLM repository.

| Source | Summary and status | Working copy | Synthesis |
|---|---|---|---|
| [config.yaml](../raw/config.yaml) | Observed proxy configuration, aliases, eight-tier classifier wiring and fallbacks | [config](../router/config.yaml) | [Architecture](architecture.md), [routing](routing.md) |
| [jev_classifier.py](../raw/jev_classifier.py) | Observed transcript normalization, tier policy, Decisions call and fallback | [plugin](../router/jev_classifier.py) | [Classifier](classifier.md) |
| [openrouter_quota_guard.py](../raw/openrouter_quota_guard.py) | Observed quota cache, paid rewrite map, blocking and headers | [callback](../router/openrouter_quota_guard.py) | [Quota guard](quota-guard.md) |
| [discover-free-models.py](../raw/discover-free-models.py) | Observed direct catalog qualification and recommendation outputs; no results imported | [discovery](../tools/discover-free-models.py) | [Evaluation](evaluation.md), [operations](operations.md) |
| [test-models.py](../raw/test-models.py) | Observed proxy health checks with duplicated alias expectations; no results imported | [health](../tools/test-models.py) | [Evaluation](evaluation.md), [routing](routing.md) |
| [benchmark-classifiers.py](../raw/benchmark-classifiers.py) | Observed labeled classification experiment; no results imported | [benchmark](../tools/benchmark-classifiers.py) | [Evaluation](evaluation.md), [open questions](open-questions.md) |
| [Bootstrap note](../raw/notes/2026-09-20-workspace-bootstrap.md) | User direction, repository destination, and explicit organizational choices | Not executable | [Workflow](workflow.md), [decisions](decisions.md) |
| [Cost-aware router research](../raw/notes/2026-09-21-cost-aware-router-research.md) | 2026-09-21 user research request; observed official LiteLLM/OpenRouter docs and source, runtime unverified | Not executable | [Cost awareness](cost-awareness.md), [open questions](open-questions.md) |
| [Other routers research](../raw/notes/2026-09-21-other-routers-research.md) | 2026-09-21 primary-source RouteLLM, vLLM Semantic Router, Bifrost and Portkey comparison; proposals distinguished from observations | Not executable | [Cost awareness](cost-awareness.md) |

All sources are registered by path and SHA-256 in
[source-manifest.json](source-manifest.json). Initial working copies were checked
byte-for-byte against originals. New raw records are additive; working copies may
subsequently evolve with documented evidence and verification.

External design reference: [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
accessed 2026-09-20; its short paraphrase and provenance are retained in the bootstrap
note. It informs workspace organization, not LiteLLM runtime claims.

Related: [index](index.md), [workflow](workflow.md), [log](log.md).

## Cost-aware implementation contract (2026-09-21)

[Accepted user contract and additive quota correction](../raw/notes/2026-09-21-cost-aware-router-contract.md). Origin: explicit user goal and official OpenRouter key reference. Status: accepted requirements, runtime pending. Affects cost awareness, quota guard, classifier, evaluation, operations, decisions and open questions.

## Review and delivery plan (2026-09-21)

[Execution authorization](../raw/notes/2026-09-21-router-plan-execution.md): user requests all reviewed work with appropriately scoped subagents. Affects delivery plan, log, operations and the implementation contract; original no-live-access constraints remain.

[Review evidence and user planning request](../raw/notes/2026-09-21-router-review-plan-evidence.md). Origin: explicit request to review everything and provide a plan with pseudocode, call flows and object shapes. Observed: 23 focused tests pass, but both independent reviews are not clean; concrete partial-stream and missing-output-cap reproductions expose remaining strict-budget gaps. Synthesis: [delivery plan](router-delivery-plan.md), [cost awareness](cost-awareness.md), [open questions](open-questions.md), and [log](log.md). Proposed behavior is not implemented by this planning turn.

## Local delivery receipt (2026-09-21)

[Immutable local receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). Origin: actual coordinator commands, scoped subagent work and two independent final adversarial reviews. Verified: 53 focused tests, 19 real-proxy routing/streaming scenarios and 10 budget/recovery scenarios; source/config hashes and measured environment retained. Both final reviews are clean with no medium-or-higher findings. Full goal remains incomplete because live bounded billing is unsupported. Affects index, delivery plan, operations, cost awareness, open questions and log.


## Pull request authorization (2026-09-21)

[User authorization](../raw/notes/2026-09-21-pull-request-authorization.md) permits publishing the reviewed branch and opening a PR in the configured repository. No merge, deployment or live billing activity is authorized. Affects operations and log.
