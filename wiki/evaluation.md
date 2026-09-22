# Evaluation and model promotion

Status: current tools and local verification seams, 2026-09-21. No live provider
benchmark results are established. Final real-proxy proof and two independent clean reviews
passed; see the [receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). Sources: working [discovery](../tools/discover-free-models.py),
[route health](../tools/test-models.py), [benchmark](../tools/benchmark-classifiers.py),
[repair contract](../raw/notes/2026-09-21-cost-aware-router-contract.md), and
[execution authorization](../raw/notes/2026-09-21-router-plan-execution.md).
Imported versions under `raw/` are historical evidence, not current tool behavior.

## Three different questions

| Tool | What it measures | Service contacted |
|---|---|---|
| `discover-free-models.py` | Candidate performance, capability, metadata, and tier eligibility | OpenRouter directly |
| `test-models.py` | Configured alias health, actual upstream, fallback frequency, capability | LiteLLM proxy |
| `benchmark-classifiers.py` | Accuracy and latency on labeled routing tasks | Jev directly; chat classifiers through LiteLLM |

These are live operator tools, not an offline unit-test suite. Run working copies
under [tools/](../tools/). Each can consume quota or money.

## Discovery

The script fetches the live text model catalog, selects concrete zero-cost `:free`
text-chat entries, excludes expired and obvious specialized non-chat models, and
looks up exact paid siblings in the same catalog. Default execution tests both
free and paid pools. `--no-paid` tests free only; `--no-free` tests paid siblings
only. Neither option changes the proxy configuration.

It runs three performance probes per candidate by default and capability probes
for formatting, JSON, simple reasoning, tool calls, and coding. Image and
compression probes depend on advertised input/context metadata. The tiny probes
are smoke tests; several prompts include the expected answer. They cannot establish
deep reasoning, long-horizon agent behavior, or full-million-token quality. The
repaired vision question asks for the dominant color without naming its expected
answer; image content, rather than prompt leakage, must supply the color.

Eligibility checks context, required tools/images, capability floors, p95 hard
latency, at least one current successful request, and optional paid price ceilings.
Paid eligibility also requires complete finite pricing; missing request/token
prices stay unknown and cannot become a zero-cost paid candidate. Eligible rows
rank first. Scores blend capability, reliability, speed, and cost
with tier-specific weights. Historical reliability uses the last ten runs, blended
25% with 75% current performance; up to 50 runs per model are retained.
There is no 98% minimum reliability eligibility gate.

Free requests default to 18 RPM, paid to 60, with independent in-process pacers.
Pacing occurs before timing. These pacers do not coordinate with another process
or reserve account-wide quota. If known free quota cannot cover an estimated full
run, the free pool is skipped unless `--force-partial-free` allows an incomplete
run; zero remaining always skips it. An unavailable quota lookup is not a hard stop.

Artifacts under `DISCOVERY_OUTPUT_DIR`:

- `openrouter-model-results.json` and compatibility name `openrouter-free-results.json`:
  metadata, tested models, and pool rankings.
- `openrouter-model-rankings.md` and `openrouter-free-rankings.md`: ranking tables.
- `recommended-models.yaml`: eligible candidates per tier and pool.
- `paid-siblings.yaml`: exact catalog pairing, including missing siblings.
- `model-capabilities.json`: evaluated summaries.
- `recommended-routing.yaml`: proposed free/paid/emergency selections.
- `openrouter-free-history.json`: retained rolling history (including paid summaries).

Outputs can replace prior files in the selected directory. Retain sanitized dated
snapshots in raw when they become project evidence. Recommendation price ceilings
are applied during eligibility scoring after probes; they are not a spending cap.

## Route health

The checker maintains its own alias/upstream table. It sends three performance
requests plus a capability check per selected alias by default, including paid
aliases and backups. `ROUTER_TEST_BACKUPS=0` excludes backup-marked aliases; it
does not exclude all paid routes.

It reads LiteLLM headers for actual model/group, timing, fallbacks, retries, and
quota status. It reports success, p50/p95/max, direct-primary rate, fallback rate,
and capability results. Missing fallback headers remain unknown, diagnostics
coverage is reported, and missing fallback diagnostics on successful requests
cause a health failure. A quota rewrite can change upstream without being counted
as a fallback. Direct-primary comparison is a separate diagnostic.

Most contracts require ≥95% success and ≤20% fallback. Jev permits ≤30% fallback;
emergency requires ≥90% success and allows 100% fallback. Failed capability,
hard latency violations, or failed rate thresholds yield `UNHEALTHY` and exit 1.
Target-latency/direct-primary warnings alone yield exit 0. Three probes do not
establish a production availability SLA.

## Classifier benchmark

Sixteen labeled cases cover the eight tiers, three runs each by default. It
benchmarks Jev and four chat classifier entries, for 240 requests if all complete.
It reports accuracy, errors, average/median/p95/min/max latency, and available cost.
Known usage charges from failed billable attempts are included alongside successful
attempts. `known_cost` sums available amounts; `total_cost` remains unknown if any
request lacks cost, with `unknown_cost_requests` exposed. Missing cost is never
zero. Main returns 0 after completing, even with
classification errors; network exceptions can interrupt the run.

The Jev branch now calls the production `OpenRouterJevClassifier.classify` seam,
including the same transcript builder, Decisions payload, answer parsing and
failure diagnostics. A fallback is reported as an error rather than a successful
classification prediction. The imported harness's separate `state.record` /
`routing_tier` payload mismatch is historical and repaired.

The benchmark is a direct legacy-classifier evaluation, not a full proxy budget
proof. Strict classifier calls additionally require trusted context created by
the cost guard; use the real proxy harness for that path. The chat-classifier
entries still require deliberately configured proxy models, and their independent
prompt/parsing behavior is not the production Jev adapter. Remaining model/config
limitations are tracked in [open questions](open-questions.md).

## Promotion rule

Keep findings as dated candidate evidence. Document the selected alias, reason,
alternatives, latency/capability/cost evidence, and rollback mapping before changing
the config. Update health expectations with the change, run appropriate offline
checks and authorized live checks, and reconcile the wiki. No automatic promotion.

Related: [operations](operations.md), [routing](routing.md), [decisions](decisions.md).

## Required local proof, 2026-09-21

The accepted contract requires the seven original repairs plus budget enforcement
through actual pinned LiteLLM hooks. [Focused repairs](../tools/test_router_repairs.py)
exercise stale quota/backoff, transcript preservation, benchmark accounting,
unknown prices, missing diagnostics and the vision prompt. Dedicated classifier,
policy, dispatch and ledger suites target the strict control boundaries.

[Local proxy probe](../tools/local_proxy_probe.py) and
[budget matrix](../tools/proxy_budget_matrix.py) use deterministic fake upstream
HTTP services with real LiteLLM processes. Together they target physical attempts,
streaming/cancellation, aliases, classifier paths, fallbacks, five budget scopes,
concurrent workers and persistence. Mock-only tests cannot substitute for these
integration gates. Run runtime checks with `.venv312\Scripts\python.exe` as
shown in [operations](operations.md); `py -3 tools/check_workspace.py` is structural
only.

Prior loopback results and their later corrections remain in [log](log.md).
Final results for the completed implementation and two clean independent reviews
are retained in the receipt. No live inference, provider billing or deployment is certified.
