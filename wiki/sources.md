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

## Twenty-tier request (2026-09-22)

[Original pasted request](../raw/notes/2026-09-22-twenty-tier-request.txt) and [scope, branch correction and evidence](../raw/notes/2026-09-22-twenty-tier-scope.md). User-authorized taxonomy and YAML policy expansion; runtime availability unresolved. Affects routing, classifier, quota guard, operations, evaluation and decisions.

[Tier-limit verification and branch rename](../raw/notes/2026-09-22-tier-limit-evidence.md): local validation and upstream source contradict the unrestricted-tier assumption. Affects routing, operations, open questions and log.

[Failed-state audit](../raw/notes/2026-09-22-expanded-tiers-blocked-audit.md): active goal stop condition, exact validation results, independent reviews, preserved YAML regression and remaining behavior/coverage defects. This is not completion evidence.

[Revised five-tier routing contract](../raw/notes/2026-09-22-five-tier-routing-request.md): user replaces twenty LiteLLM tiers with twenty semantic classes/five capability tiers plus supported request-scoped family narrowing. API investigation must precede YAML changes.

[Installed five-tier API audit](../raw/notes/2026-09-22-five-tier-api-audit.md): real public-hook probes and two independent reviews confirm missing signal propagation AND rejection of custom tiers with plugins. Source/test hashes retained; incomplete implementation, not acceptance.

[Continue/publish authorization and current source check](../raw/notes/2026-09-22-publish-after-verification.md): user authorizes pushing expanded-tiers after verification. Upstream compatibility research and concrete callback alternative are recorded; no architecture change accepted yet.

[Pinned upstream release research](../raw/notes/2026-09-22-upstream-five-tier-research.md): direct GitHub API/source confirms latest v1.102.0 and pinned main retain both compatibility blockers, with upstream tests explicitly expecting rejection. Supported pre-call callback alternative requires an integration choice.

[Free-first subscription escalation design](../raw/notes/2026-09-22-free-first-escalation-design.md): latest user preference and documentation request. Supersedes no-failure-escalation and ChatGPT-as-CAPABLE-primary proposals. Records the proposed callback architecture, roster policy, unresolved choices and documentation-only scope.

[Implementation/publication authorization](../raw/notes/2026-09-22-callback-implementation-authorization.md): implements documented callback design with explicit default fallback policy and verification gates.

- [Callback acceptance receipt](../raw/notes/2026-09-22-callback-acceptance.md): observed offline tests, RED/GREEN review fixes, two independent clean verdicts and reviewed file fingerprints; informs current design, index, operations, decisions and log.
