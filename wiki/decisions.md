# Decision register

Date: 2026-09-20. This register separates adopted workspace conventions from
observed imported behavior. Original router rationale is unknown unless a source
states it. Change rules through a new raw note and explicit supersession.

## W001 — Wiki-first shared context

Status: adopted for this workspace. Evidence: [user direction](../raw/notes/2026-09-20-workspace-bootstrap.md).

The repository wiki is the maintained knowledge layer; agents enter through
`AGENTS.md` and the index. Preserve raw sources, synthesize before implementation,
and reconcile after checks. Reason: decisions and context should survive agent and
chat changes. Consequence: every meaningful project change includes wiki impact.
Process details live in [workflow](workflow.md).

## W002 — Preserve imports; edit working copies

Status: adopted bootstrap organization. Evidence: [bootstrap choices](../raw/notes/2026-09-20-workspace-bootstrap.md).

The six originals stay immutable. `router/` holds deployment inputs and `tools/`
holds operator scripts. Reason: preserve provenance while allowing ordinary code
maintenance. Consequence: future working files may diverge; the manifest locks
raw evidence rather than forcing perpetual equality with live code.

## W003 — Explicit ingestion with offline structural checks

Status: adopted bootstrap organization. Evidence: [bootstrap choices](../raw/notes/2026-09-20-workspace-bootstrap.md).

Use source-backed LLM edits, a source register, hashes, index, and append-only log.
Use a standard-library check in CI. Reason: a small repo needs a clear workflow,
without installing an automated semantic pipeline. Consequence: checks detect
structural breakage; agents must still review truth, contradictions, and stale claims.

## W004 — Evidence before model promotion

Status: adopted maintenance rule. Evidence: [bootstrap choices](../raw/notes/2026-09-20-workspace-bootstrap.md)
and [discovery source](../raw/discover-free-models.py).

Retain rankings as candidate evidence, then deliberately update and verify config.
Reason: point-in-time probes are not production guarantees. Consequence: record
selection reasons, costs, rollback mapping, and config/health-table consistency.

## R001 — Classify capability and strength separately

Status: observed imported design. Evidence: [classifier](../raw/jev_classifier.py), [config](../raw/config.yaml).

Four capabilities × two strengths create eight tiers; specialized aliases bypass
classification. The classifier chooses a tier while solvers answer the request.
Consequence: classifier failure, solver failure, and specialized routing need distinct checks.

## R002 — Free-first with explicit paid continuity

Status: observed imported behavior. Evidence: [config fallbacks](../raw/config.yaml),
[quota route map](../raw/openrouter_quota_guard.py).

Free aliases have paid fallback paths; quota exhaustion can rewrite aliases before
routing. `jev` exhaustion selects `paid-general-capable` rather than a second
classifier. The source comment attributes this to a community auto-router limit;
that external product constraint is unverified. Consequence: free-first requests
can spend money and quota rewrite may lose capability-specific classification.

## R003 — Distinct discovery, health, and classifier evaluation

Status: observed imported design. Evidence: [discovery](../raw/discover-free-models.py),
[health](../raw/test-models.py), [benchmark](../raw/benchmark-classifiers.py).

These tools answer different questions and must not be substituted for each other.
Consequence: successful discovery does not prove deployed alias health, and a
classifier benchmark does not certify the runtime plugin's transcript handling.

Related: [architecture](architecture.md), [evaluation](evaluation.md), [open questions](open-questions.md).

## R004 — Twenty semantic classes, no failure escalation

Superseded for failure policy by R006 below; retained as history.

Accepted 2026-09-22, implementation proposed. [Source](../raw/notes/2026-09-22-twenty-tier-scope.md). Supersedes the two-strength taxonomy in R001. Preserve semantic tier -> family alias -> deployment separation and existing lower-tier routing. Keep strict cost controls on their separate branch. Use YAML for ChatGPT deployments; availability and authentication require operational evidence.

## R005 — Five capability tiers with family narrowing

Built-in Auto Router integration superseded as a proposal by the callback design in R006; semantic dimensions retained.

Accepted, implementation pending. [Revised contract](../raw/notes/2026-09-22-five-tier-routing-request.md) supersedes R004's twenty Auto Router tiers. Keep twenty JEV semantic classes; one structured decision supplies family and capability. A supported classifier-to-RoutingPlugin signal is a prerequisite. Do not patch the tier cap.

## R006 — Free-first callback routing with subscription escalation

Status: user-directed free-first/escalation preference; callback implementation
proposed and documented, 2026-09-22. [Source](../raw/notes/2026-09-22-free-first-escalation-design.md),
[current architecture](semantic-routing-alternative.md).

Keep all eight existing EFFICIENT/CAPABLE primary solver routes free. Permit
subscription escalation after compatible free failures or known exhausted free
capacity, and direct subscription selection for exceptional task complexity.
Keep family/capability semantic judgment separate from availability/provider/cost
policy. Proposed higher-level assignments remain Luna/Terra/Sol; model quality
and availability are unverified. Paid API fallback is last, with exact limits and
chains still unresolved. Specialist routes require their own compatibility checks.

This supersedes R004's no-failure-escalation rule and R005's built-in Auto Router
integration proposal. It discards the intervening suggestion to use ChatGPT as
CAPABLE primary. Exact fallback behavior is intentionally changing; future work
must record baseline-versus-target traces. No runtime change or live deployment
is established by this documentation decision.

## R007 — Execute the callback design

[User authorization and bounded choices](../raw/notes/2026-09-22-callback-implementation-authorization.md). Implement one semantic choice parsed into family/capability, free-primary/free-backup then Luna then paid continuity; direct higher tiers retain selected subscription strength. Remove virtual-entrypoint fallback; fail closed if callback absent. Exact supported surfaces and guardrail/access limits are verified before publishing.

R007 implementation status: verified offline by 21 tests and two clean independent
reviews; [durable receipt](../raw/notes/2026-09-22-callback-acceptance.md). Live boundaries remain unresolved as documented. Publication is authorized; deployment is not part of this task.
