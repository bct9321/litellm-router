# Project wiki

Status: implementation resumed, 2026-09-21. The immutable bootstrap sources remain
preserved; current behavior is defined by working code and named verification.

Start with the [review and delivery plan](router-delivery-plan.md) and latest
[log](log.md). The [execution authorization](../raw/notes/2026-09-21-router-plan-execution.md)
resumes bounded subagent implementation. Strict loopback dispatch, accounting and
classifier controls passed 53 focused tests, 19 real-proxy routing scenarios and
10 budget/recovery scenarios, plus two consecutive clean independent reviews.
See the [immutable receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). Live billing bounds and deployment
remain unverified. Host goal status is controlled by the app.

## Understand the router

- [Architecture](architecture.md): components, request paths, and trust boundaries.
- [Routing policy](routing.md): eight tiers, aliases, fallbacks, and targets.
- [Jev classifier](classifier.md): transcript selection and failure behavior.
- [Quota guard](quota-guard.md): quota lookup, paid rewrites, and response headers.
- [Cost awareness](cost-awareness.md): researched proposal for estimates, spend visibility, budgets, and router comparisons.
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
