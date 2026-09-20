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

All sources are registered by path and SHA-256 in
[source-manifest.json](source-manifest.json). Initial working copies were checked
byte-for-byte against originals. New raw records are additive; working copies may
subsequently evolve with documented evidence and verification.

External design reference: [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
accessed 2026-09-20; its short paraphrase and provenance are retained in the bootstrap
note. It informs workspace organization, not LiteLLM runtime claims.

Related: [index](index.md), [workflow](workflow.md), [log](log.md).
