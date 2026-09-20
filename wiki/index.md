# Project wiki

Status: source-ingested baseline, 2026-09-20; runtime integration remains unverified.

## Understand the router

- [Architecture](architecture.md): components, request paths, and trust boundaries.
- [Routing policy](routing.md): eight tiers, aliases, fallbacks, and targets.
- [Jev classifier](classifier.md): transcript selection and failure behavior.
- [Quota guard](quota-guard.md): quota lookup, paid rewrites, and response headers.
- [Evaluation](evaluation.md): discovery, route health, and classifier benchmarking.
- [Vocabulary](../CONTEXT.md): shared domain terms.

## Work consistently

- [Wiki workflow](workflow.md): ingestion, queries, maintenance, and completion gates.
- [Decisions](decisions.md): workspace rules and observed router choices.
- [Operations](operations.md): prerequisites, environment, live tools, and GitHub practice.
- [Open questions](open-questions.md): contradictions and missing proof.
- [Source register](sources.md): every ingested source and where it is explained.
- [Source manifest](source-manifest.json): immutable raw checksums and initial working copies.
- [Activity log](log.md): append-only changes and handoffs.

## Read this status correctly

`Observed` means supported by the supplied code/config or a direct local inspection.
`Verified` means a named check was run with its scope recorded. `Proposed` means a
future change, not current behavior. `Unresolved` means conflicting or missing
evidence. All initial technical pages describe source behavior, not a certified deployment.

Sources: [bootstrap request and choices](../raw/notes/2026-09-20-workspace-bootstrap.md),
[source register](sources.md).
