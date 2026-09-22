# Project wiki

Status: free-first callback implementation passes offline routing tests, 2026-09-22;
two independent clean reviews are recorded in the [acceptance receipt](../raw/notes/2026-09-22-callback-acceptance.md). Start with the [current design](semantic-routing-alternative.md).
The eight lower primary aliases stay free; Luna follows exhausted free attempts,
then existing paid API fallbacks. Twenty semantic classes remain first-class.
No deployment or live model verification is claimed.

## Understand the router

- [Architecture](architecture.md): components, request paths, and trust boundaries.
- [Routing policy](routing.md): baseline and proposed free-first escalation policy.
- [Jev classifier](classifier.md): transcript selection and failure behavior.
- [Quota guard](quota-guard.md): quota lookup, paid rewrites, and response headers.
- [Evaluation](evaluation.md): discovery, route health, and classifier benchmarking.
- [Vocabulary](../CONTEXT.md): shared domain terms.

- [Free-first callback architecture](semantic-routing-alternative.md): current proposed flow, twenty semantic classes, model roster, escalation policy and verification gate.

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
