# Wiki activity log

Append new entries below. Preserve prior entries; record corrections explicitly.

## [2026-09-20] ingest | Initial router workspace

- Sources: all six originals in [source register](sources.md), plus the
  [bootstrap direction](../raw/notes/2026-09-20-workspace-bootstrap.md).
- Read and synthesized the supplied configuration, classifier, quota guard,
  discovery script, route health script, and classifier benchmark.
- Created the wiki index, topic pages, source register, workflow, decisions,
  open questions, root README/AGENTS/vocabulary, and working copies.
- Adopted W001–W004; recorded R001–R003 as observed imported choices.
- Preserved originals. Added source manifest, offline integrity/link/syntax check,
  GitHub CI, ignore rules, and raw-byte-preserving Git attributes.
- Static and publication results are recorded in subsequent verification entries.
- Skipped live inference, dependency installation, and deployment; this task
  establishes the knowledge baseline. No model rankings or API costs were measured.
- Next implementation task: select a gap from [open questions](open-questions.md),
  starting with a known-compatible deployment environment if deployment is desired.

## [2026-09-20] verify | Offline bootstrap checks

- `py -3 tools/check_workspace.py` passed: 7 raw hashes/registrations,
  15 Markdown files with local file-link checks, wiki index coverage, and 11 Python
  syntax checks. No runtime modules were imported and no provider requests were made.
- All six initial working copies matched the raw originals byte-for-byte locally.
  Git normalizes working code to LF; raw byte preservation is explicitly configured.
- Exercised the checker against temporary fixtures: a clean copied workspace
  passed; changing raw bytes and introducing a broken link/orphan page failed.
  The first fixture omitted root documents and correctly failed; the corrected
  complete fixture passed. Real raw sources were unchanged throughout.
- Full Git whitespace review reports inherited whitespace in the imported
  classifier/benchmark; retained to preserve import evidence. Newly authored files
  are checked separately. YAML semantics, dependency compatibility, live API behavior,
  and GitHub CI execution are not established by the offline check.
- Connected the local repository to the user-supplied empty GitHub remote.
- Open implementation issues remain Q001–Q012; see [open questions](open-questions.md).

## [2026-09-20] publish | GitHub bootstrap verified

- Published bootstrap commit `ecf93825463df39ba9af266d5122e632ac3037f4` to `main`
  in [bct9321/litellm-router](https://github.com/bct9321/litellm-router).
- [GitHub Workspace integrity run](https://github.com/bct9321/litellm-router/actions/runs/35516656699)
  completed successfully on the published bootstrap. Local working tree was clean
  before this receipt was appended.
- This confirms the offline checks also pass on GitHub's Linux runner, including
  preserved raw hashes. Deployment and live inference remain outside this verification.

## [2026-09-21] research | Cost-aware Jev and model spend

- Sources: [LiteLLM/OpenRouter evidence](../raw/notes/2026-09-21-cost-aware-router-research.md)
  and [other-router comparison](../raw/notes/2026-09-21-other-routers-research.md).
- Read official spend, routing, budget, plugin, Jev and provider accounting docs;
  inspected LiteLLM cost-selection/budget code and primary sources for RouteLLM,
  vLLM Semantic Router, Bifrost and Portkey. External branch links are mutable;
  this is dated research, not a pinned integration audit.
- Added [cost-awareness proposal](cost-awareness.md), source registrations/hashes,
  index link, proposed P001 and unresolved Q013-Q015. Existing raw bytes and
  runtime code/config were preserved.
- Recommendation: reuse LiteLLM accounting and budget facilities; supply Jev a
  server-calculated cost snapshot and enforce eligibility separately. Distinguish
  per-deployment controls from Enterprise per-key model budgets, native TypeSafe
  Jev from the current alpha adapter, and recorded-spend caps from reservations.
- Verified offline structural check: 9 raw hashes/registrations, 16 Markdown
  documents, wiki indexing and 11 Python syntax checks passed. This does not
  establish billing accuracy, runtime compatibility, or deployment readiness.
- Skipped account access, credential inspection, installation, inference,
  benchmarking, deployment and publication. No live spend or prices measured.
- Work retained on `codex/cost-aware-router-research`. Next: choose and pin a
  deployment version, establish accounting coverage, then verify the narrow
  visibility slice before changing paid dispatch or defining budget amounts.

## [2026-09-21] ingest | Strict cost-aware delivery contract

- Preserved dirty research/wiki work and all original raw bytes; created codex/cost-aware-router using command-scoped Git trust after a workspace ownership mismatch.
- Ingested [user contract and quota correction](../raw/notes/2026-09-21-cost-aware-router-contract.md), registered its hash, and adopted W005. Prior research incorrectly claimed the documented key schema lacks the free quota object.
- Runtime changes have not started. Public seams are the classifier, quota callback, accounting report, evaluation tools and real proxy HTTP boundary specified by the user.
- Python 3.10.2 available; isolated .venv created. Initial package index failed due to sandbox socket permissions; escalated workspace-local pinned installation is in progress.
- Next: structural ingestion check, inspect installed hooks/billing contracts, then focused RED/repair and actual fake-upstream integration. No secrets inspected or provider calls made.

## [2026-09-21] checkpoint | Runtime setup and first RED/green repairs

- Installed litellm[proxy]==1.99.0 in .venv (exit 0), but import failed on Python 3.10: typing.NotRequired unavailable. Hypothesis revised to require newer Python; installed same pin into .venv312 using bundled Python 3.12.14 (exit 0). No upstream library was patched.
- Import first failed trying to fetch tokenizer data. Cached public cl100k_base/o200k_base data under outputs/token-cache (exit 0); source inspection identified CUSTOM_TIKTOKEN_CACHE_DIR as the required LiteLLM override, distinct from TIKTOKEN_CACHE_DIR. Import then succeeded on 3.12.
- Production classifier RED: genuine chat_id/message_id request returned fallback because substring filtering removed it. Removed that heuristic; public classify() test passed with fake HTTP.
- Benchmark summary RED: missing known_cost; summary omitted failed billable calls. Include all finite nonnegative known attempt costs, preserve unknown total and expose coverage. Focused check passed.
- Quota public callback RED: stale success accepted with fail_open=false. Expired/missing refresh now returns unknown with cached refresh backoff. Strict callback and header regression passed.
- `.venv312/Scripts/python.exe tools/test_router_repairs.py`: exit 0, three tests. These use HTTP transport fakes and are not the required real proxy integration proof.
- Preliminary independent audit found native LiteLLM reservations but gaps: reservation shrinking, missing-price bypass and cancellation output release. Alpha Decisions documents usage but no upper charge/token bound. Final clean-review count remains zero. Next: actual local proxy HTTP proof and durable budget gap.

## [2026-09-21] implement | Local strict cost-aware path

- Pinned `litellm[proxy]==1.99.0` in `requirements.txt`; verified runtime uses Python 3.12.14 because the pinned package did not import under the available Python 3.10.
- Added `spend_ledger`, `cost_transport`, `cost_guard` and `cost_policy`: canonical-model reservations are durable, atomic on the SQLite database, preserve unknown exposure, reject unpriceable/unbounded paid dispatches, and select free-first capability-compatible candidates from a server report.
- Added operator `cost_report.py`, cost-policy schema and idempotent OpenRouter activity import. Provider aggregates are stored separately from strict local counters to avoid overlap double counting.
- Repaired production-classifier accounting under a bounded local contract, including failed classifier reservations; live alpha Decisions remains prohibited in strict mode due to the missing documented bound.
- Added focused test suites and `local_proxy_probe.py`. The latest real LiteLLM proxy proof passed with six upstream attempts: cost-aware free-to-paid selection/fallback, direct paid dispatch, streaming final usage, canceled stream retaining exposure, emergency fallback, and budget denial before upstream dispatch. Logs/proof are under ignored `outputs/local-proxy/`.
- Checks pending final review: current focused suites and structural checker pass. No account access, secret read, provider call, publish, merge, deployment or live billing occurred.

## [2026-09-21] checkpoint | Adversarial review correction

- Two independent adversarial reviews found P1 gaps in the first local proof: static rather than request-derived charges, optional callback wiring, original-alias attribution, no Jev cost-context selection, and incomplete proxy-level scenarios. Neither review is clean; the required clean-review count is zero.
- Replaced fixture-static paid estimates with a deterministic server-side calculation over the submitted OpenAI request surface, including messages, tool definitions, multimodal fields and requested output ceiling. Contracts now require explicit per-token rates, fixed overhead and a finite maximum output. A request that exceeds its contractual output bound is refused before dispatch.
- Added the always-loadable cost callback to `router/config.yaml`; it has no effect without `COST_ROUTER_CONFIG`, and activates the strict local-only transport only after a complete policy is supplied. Deployment hooks now attribute each physical attempt to the selected deployment alias.
- The real proxy proof was rerun after that repair. Remaining review findings—Jev candidate context, historical reconciliation semantics, schema execution and the required proxy-level concurrent/quota/classifier scenarios—remain open and must be resolved before another adversarial review.
- Focused-suite retry failed before tests because a standard-library policy test imported the LiteLLM proxy module, which attempted an unavailable tokenizer network fetch outside the integration cache. Hypothesis: pure policy validation must not require the proxy runtime. Moved executable policy validation to `cost_policy.py`; its focused check now isolates the policy seam.

## [2026-09-21] checkpoint | Jev seam and proxy matrix repair

- Fresh review found that pinned LiteLLM passes a `RoutingContext` object, not a mapping, to custom classifiers; classifier overhead therefore used a separate logical request ID. The guard now stores the complete client request surface in server metadata, and Jev reads `context.metadata` for both the shared request ID and full request-derived charge calculation. Strict policy rejects `n != 1` so output bounds cannot be under-reserved.
- Strict Jev selection now leaves the `jev` model for LiteLLM's complexity-router, supplies a server-owned eligible snapshot, and returns configured tier names that the pinned resolver accepts. The checked-in policy schema is executed with `jsonschema` before strict guard construction and also enforces Jev tier aliases and cross-references.
- The real proxy fixture now includes a fake Decisions endpoint and actual `auto_router/complexity_router` model. It passed with 10 solver upstream attempts and 1 classifier attempt across free fallback, strict Jev selection, per-attempt settlement, streaming usage, cancellation retention, emergency fallback, concurrent workers, restart recovery, duplicate stream settlement, and budget refusal. The historical backfill report now exposes imported per-model/day/month aggregates separately with explicit overlap coverage rather than summing them into strict counters.
- Validation after this checkpoint: 23 focused tests, real proxy probe, `py -3 tools/check_workspace.py`, and `git diff --check` passed. The two clean independent adversarial reviews remain outstanding; no clean-review count is claimed yet.
- A follow-up policy/report run under the unprovisioned Python 3.10 interpreter failed at strict schema import (`jsonschema` is part of the pinned runtime requirements but is not installed in that interpreter); strict startup correctly fails closed. The history assertion also incorrectly expected a 2026-09-20 row in the 2026-09-21 today bucket. Hypotheses recorded: use the pinned Python 3.12 environment for runtime policy tests, and assert completed historical rows in their UTC month bucket. The corrected 3.12 suite is the authoritative runtime check.
- The first run after reserving the actual Decisions payload failed the classifier unit fixtures at the configured 500-nanodollar request ceiling; this was expected evidence that the fixture policy did not cover the larger classifier document. Raised only the test fixture ceilings to finite explicit values. A second failure rejected the same historical aggregate when `--source` changed; stable provider identity must dominate caller labels, so duplicate-equivalent rows now remain idempotent while conflicting values still fail.

## [2026-09-21] checkpoint | Strict fallback, attribution and worker proof repair

- Independent review found three remaining P1s: a schema-valid policy could omit
  `routes.jev`, classifier failures could return an unchecked environment tier,
  and a valid contract without `alias` could record the provider model instead of
  the configured logical alias. The schema and semantic validator now require
  `routes.jev` and contract aliases. Jev strict mode is active whenever the
  cost policy is loaded; missing, invalid or failed classifier paths recompute a
  currently eligible configured fallback and fail closed when none exists.
- Extracted shared capability/price/budget eligibility used by direct routes and
  Jev snapshots. Added a rejecting policy test for missing aliases/routes.
- Extended the real pinned proxy proof with two independent proxy processes on
  distinct ports sharing one SQLite ledger. Delayed overlapping requests prove
  accepted reservations stay within a 150-nanodollar daily/monthly/request cap;
  the single-process concurrency case remains covered.
- Updated classifier, decision and evaluation wiki claims to match local
  implementation and verification status. Focused tests and the real proxy
  probe pass after these repairs; fresh clean reviews are required next.

## [2026-09-21] review | Concrete plan after independent audit

- User requested a complete review and clear plan with pseudocode, call flows and object shapes. The host goal is paused; this turn changes documentation only and leaves runtime work untouched.
- Captured [additive review evidence](../raw/notes/2026-09-21-router-review-plan-evidence.md), registered its SHA-256, and wrote the [delivery plan](router-delivery-plan.md). Updated index, cost-awareness and open-question status pointers. Existing raw hashes remain fixed.
- Both independent reviewers report not clean. The plan records final-dispatch capability gaps, unenforced outgoing output caps, partial-stream usage releasing reservations, incomplete identity and history accounting, inconsistent free-first behavior, and the unsupported live classifier billing contract. Clean-review count is zero.
- Correction to the preceding worker-proof checkpoint: its run did admit one worker, but `successful <= 1` also permits zero successes, so the assertion is not a sufficient regression gate. Other prior broad verification wording is limited to named fixture scenarios, not the full strict contract.
- This review reran `.venv312\Scripts\python.exe -m unittest tools.test_cost_policy tools.test_router_repairs tools.test_budget_ledger`: exit 0, 23 tests. Inspected the prior real-proxy PASS artifact (15 solver attempts, 2 classifier attempts); did not rerun that proxy during this documentation-only turn.
- Temporary read-only reproductions confirmed partial SSE usage without final completion reduced a 90-nanodollar reservation to a 10-nanodollar final charge, and missing max_tokens was priced with an assumed cap without adding it to outbound JSON. These were recorded as findings, not repaired in this turn.
- Next implementation work, when resumed: establish trusted request/deployment identities and final dispatch authority, then enforced billing bounds, final settlement, scoped history, stronger real-proxy evidence, and two consecutive clean independent reviews. No provider calls, secret access, live amounts, merge, publishing or deployment occurred.
- Documentation verification: `py -3 tools/check_workspace.py` exit 0 (11 raw hashes/registrations, 17 Markdown files, 20 Python syntax checks); command-scoped `git diff --check` passed with line-ending notices only. Branch confirmed `codex/cost-aware-router`. No goal status change was made.

## [2026-09-21] ingest | Execute reviewed plan with bounded subagents

- Registered additive execution authorization and linked the reviewed plan before behavior changes. Original raw bytes and dirty changes remain preserved on codex/cost-aware-router.
- Ownership: dispatch/contract guard; ledger/history/report; classifier; coordinator owns real-proxy integration, config/docs and final verification. Interface changes are communicated before cross-file integration. Original authorized public test seams remain in force.
- Each failure records a hypothesis and a focused failing check before its smallest repair. Two independent clean completion reviews remain required; current count zero. Live billing bounds remain unresolved and no live activity is authorized.

## [2026-09-21] RED | Scoped ledger and history

- Ledger subagent ran `.venv312\Scripts\python.exe -m unittest tools.test_history_reconciliation`: exit 1, three errors for absent attribution API, unknown-history handling and provider-period scope.
- Hypothesis: preserve positional reservation API while adding attempt metadata; reconcile scoped nonoverlapping opening balances with explicit coverage, and block provider-period admission when coverage is unresolved. Unknown totals remain null. Implementing the narrow ledger/report repair next.

## [2026-09-21] RED | Dispatch and classifier boundaries

- Dispatch subagent: `.venv312\Scripts\python.exe -m unittest tools.test_dispatch_controls` exit 1, four failures: no actual output cap, accepted conflicting output fields, accepted expired contract, and partial stream reducing 90 exposure to 10. Hypothesis: enforce the exact wire payload and current supported contract, with complete-stream finality before releasing capacity.
- Classifier subagent: `.venv312\Scripts\python.exe -m unittest tools.test_classifier_controls` exit 1: strict URL can be redirected outside declared contract; cancellation remains pending. Hypothesis: bind actual endpoint/body to validated contract and settle cancellation explicitly unknown. Free-only candidate proof is also being separated into its own regression.

## [2026-09-21] checkpoint | Parallel implementation integration

- Ledger/history focused checks initially passed, then new regressions exposed conflicting final usage releasing prior capacity and opening balances overlapping migrated attempts. Hypotheses: quarantine conflicting finality with sticky breach/unknown exposure; reject historical openings overlapping any local attempt. A Windows test-fixture connection cleanup failure was corrected by explicitly closing its SQLite connection.
- Classifier first focused run passed 19 checks; stricter complete policy validation then correctly failed while shared schema fields were still being integrated. No schema validation was weakened. Classifier now binds actual endpoint/model/output fields, requires logical request identity and records cancellation unknown.
- Dispatch and classifier are coordinating trusted request context and explicit deployment identities. Integration harness will adopt that contract and preserve exact wire/ledger assertions; interim green checks are not completion evidence.

## [2026-09-21] RED | Real proxy budget diagnostics

- `.venv312\Scripts\python.exe tools/proxy_budget_matrix.py` exited 1 after independently proving the four overall/model day/month caps. Per-request denial was wrapped by the pinned OpenAI adapter as generic Connection error, so the typed-denial assertion correctly failed.
- Hypothesis: proxy deployment admission should expose deterministic request-budget refusal before adapter wrapping, while the transport retains atomic final reservation. Dispatch agent is applying a focused correction; assertions remain strict. Proof directory: outputs/budget-matrix/426f5e680aa04022a8abb6382e6d1e5d.

## [2026-09-21] RED | Quota rewrite needs trusted exhaustion evidence

- Updated real routing probe passed initial fallback, shared alias attribution and wire output-cap cases, then exited 1 at exhausted-quota paid rewrite. The final paid gate correctly refused because the quota callback had not marked trusted free capacity unavailable.
- Hypothesis: after the cost callback captures original identity, the quota callback must communicate only verified exhaustion into that trusted context before rewriting. Add the single exhaustion handoff; retain final capability and budget checks. No client metadata can authorize this handoff.

## [2026-09-21] checkpoint | Quota handoff green; fixture cache correction

- Real probe passed exhausted quota rewrite and incompatible quota-target rejection after trusted exhaustion handoff. Next failure was Jev free-only assertion: the fixture waited 1.1 seconds although the production quota callback clamps cache lifetime to at least 5 seconds.
- Hypothesis confirmed by proxy log still reporting EXHAUSTED for Jev: fix the fixture to respect the existing minimum and verify the next snapshot is healthy; do not weaken free-first assertion or alter production cache policy.
- Dispatch typed-error regression exited 1 (expected 429 vs no mapped exception). Pinned proxy supports async_post_call_failure_hook; use it to map stored server-owned denial reasons after SDK exception wrapping while retaining the final atomic gate.

## [2026-09-21] checkpoint | Dispatch and ledger edge cases

- Provider-executed tools were accepted by the text estimator. Focused dispatch RED failed on `tools: [{type: web_search}]`; the smallest fix accepts only bounded function definitions. Dispatch suite then passed 34 tests. A combined suite passed 49 tests (exit 0).
- Legacy history migration silently collapsed equal-usage rows with different request counts. Focused `test_conflicting_legacy_metadata_requires_reconciliation` exited 1. Hypothesis: compare all retained semantic fields before deduplicating legacy identities; ledger agent is repairing this boundary.
- Added real incompatible fallback scenario and corrected proof names: the original smoke probe covers concurrent clients, while the separate matrix covers synchronized independent workers; absent route is not a missing-price proof. Matrix now tests actual missing/stale contracts at startup.
- Verified existing public tokenizer cache through checksum-only setup helper; no download or provider access. The helper records fixed public artifact hashes and supports explicit setup download. Clean-machine installation remains unverified.

## [2026-09-21] checkpoint | Final proof strengthening

- Legacy migration semantic-conflict check is now GREEN: 12 ledger/history/CLI tests, exit 0.
- Main real proxy probe passed 19 named scenarios (20 solver HTTP attempts, two classifier attempts), including incompatible ordinary fallback and quota rewrite. Receipt `outputs/local-proxy/run-3b2c442367d74ed8ad54b77496a6959c/proof.json`. A final frozen-source rerun remains necessary after shared ledger changes.
- Combined classifier/solver ceiling integration initially failed its exact-attempt assertion: redundant fixture chains `jev -> free` and `free -> direct` retried free twice. The budget gate correctly denied paid dispatch. Hypothesis: remove redundant virtual fallback to free, retaining `jev -> direct` and `free -> direct`; keep exact attempt assertions and all production controls.

## [2026-09-21] RED | Discovery request-price omission

- Independent reviewer noted the free catalog predicate still defaulted absent request price to zero. Focused expanded `test_unknown_request_price_stays_unknown` reproduced it: `.venv312\Scripts\python.exe -m unittest tools.test_router_repairs` exit 1, one failure of 15 tests.
- Hypothesis: normalized price already preserves missing values, but the free predicate retained a legacy default. Remove that default and reject boolean pseudo-prices. This does not enable any additional candidate or weaken strict dispatch. Review clean count remains zero.

## [2026-09-21] checkpoint | Freeze audit

- Combined 49-test suite passed after discovery missing-price repair (exit 0). Static workspace check passed 12 raw records/17 Markdown/25 Python files.
- Git whitespace check exited 1: extra blank at classifier EOF. Remove only the extra ending newline; no behavior change. Final runtime receipts must use resulting hash.
- Ledger subagent identified a midnight lock edge: reservation period was calculated before SQLite write-lock acquisition. Hypothesis: a waiting worker can enter the next UTC period with an old period stamp. Add a deterministic lock-crossing regression before moving period calculation inside the transaction. Final proof/reviews remain pending; clean count zero.

## [2026-09-21] RED | Contract expiry during reservation wait

- Independent reviewer identified an adjacent lock boundary: validating a fresh price before a blocking reservation does not prove freshness when HTTP begins. A contract may expire while SQLite waits.
- Dispatch subagent is reproducing transport and classifier seams before the smallest repair: revalidate the exact contract after reservation and immediately before HTTP; retain capacity on uncertainty. Final harness runs wait for this fix. This review round is not clean; consecutive-clean count remains zero.

## [2026-09-21] checkpoint | Period boundary green; review not clean

- Deterministic SQLite lock-crossing reservation test failed before the repair: Sep30 was recorded after the test clock advanced to Oct1. Reserve now measures the period under `BEGIN IMMEDIATE`; report now measures its snapshot/reset time there too. Ledger/history focused command passed 14 tests, exit 0. Snapshot check was added immediately after the shared fix; no separate RED claimed for that check.
- Independent review confirmed P2 expiry race with a 0.1-second-lived contract and 0.2-second reservation delay: HTTP began after expiry. Review outcome NOT CLEAN. Dispatch/classifier after-reservation revalidation is in progress; final proof and two consecutive clean reviews restart after repair.

## [2026-09-21] RED | Expiry regression reproduced in both dispatch paths

- `.venv312\Scripts\python.exe -m unittest tools.test_dispatch_controls.DispatchTests.test_contract_expiring_while_reservation_waits_never_dispatches tools.test_classifier_controls.Controls.test_classifier_contract_expiring_during_reservation_never_connects` exited 1 with two failures. A 0.5-second contract expired during a 0.6-second reservation delay; both paths still connected.
- Fix in progress: post-reservation contract revalidation immediately before HTTP; keep unresolved reservation on refusal. This supplements validation at startup/selection/physical authorization, not a replacement for them.
- `.venv312\Scripts\python.exe -m pip check` exited 0, no broken requirements. Operator CLI ran offline against the real fixture ledger with exit 0; separate unknown counts/exposure, canonical totals and remaining capacity are present. This is router-only coverage, not account billing evidence.

## [2026-09-21] checkpoint | Frozen-source validation

- Both expiry regressions are GREEN. `.venv312\Scripts\python.exe -m unittest discover -s tools -p 'test_*.py'` exit 0, 53 tests. Independent reviewer separately reran 53 tests, exit 0.
- Frozen-source main proxy run passed 19 named scenarios, 20 solver and two classifier HTTP attempts. Proof: `outputs/local-proxy/run-76347cbb5e8148d6b0f52805108b6356/proof.json`; report generated from that run with `tools/cost_report.py`, exit 0. Main harness runtime sources match repaired UTC/expiry code; real proxy budget matrix is still running.
- Runtime and dependency versions: Python 3.12.14, LiteLLM 1.99.0, jsonschema 4.26.0. No broken installed dependencies. No live provider call or credential access occurred. Final independent clean-review count remains zero pending proof audit.

## [2026-09-21] review | First consecutive clean review

- Completion reviewer one's fresh review is CLEAN with no medium-or-higher findings after the expiry/UTC fixes. Independently reran 53 tests (exit 0), inspected all 19 main proxy and 10 matrix scenarios, compared every retained source hash with zero mismatches, and inspected the 22-attempt operator report.
- Final matrix `.venv312\Scripts\python.exe tools/proxy_budget_matrix.py` exited 0: `outputs/budget-matrix/38cf874ea4344300b6f85e1722157de6/proof.json`. All five caps reject forbidden HTTP with structured 429; synchronized workers admit exactly one and deny one; crash retains 60; classifier10 plus solver120 is denied under request125 before paid HTTP. Synthetic units are nanodollars, not live amounts.
- Root independently compared both source hash maps and every matrix config hash: exit 0, no mismatch. Second independent review has started against unchanged runtime. Consecutive clean count is one. Live billing bounds remain unresolved.

## [2026-09-21] review and receipt | Two consecutive clean reviews; live blocker retained

- Independent completion reviewer two is CLEAN, zero medium-or-higher findings. Independently ran all 53 tests and workspace checker (exit 0 each); matched 20 main source hashes, seven matrix source hashes and 20 configuration hashes. Reviewed real-proxy assertions/receipts without rerunning those harnesses. No files changed during the two final clean reviews. Standards and supported-local spec review have no material findings.
- Preserved the [immutable local receipt](../raw/notes/2026-09-21-local-delivery-receipt.md), registered its new SHA256, and linked it in the source register. It includes full changed-file list, exact commands/exits, scenario results, both review outcomes, proof copies/hashes, environment, configuration/start/report instructions and remaining risks.
- Local work is verified; full goal is NOT marked complete. Precise blocker: available live OpenRouter/alpha Decisions billing/token evidence does not establish a pre-dispatch maximum billable charge for all dimensions. Strict live paid/classifier paths remain rejected. Router-only scope does not claim complete account spend; partial activation-day historical coverage cannot be invented. No secrets, live calls/charges, publishing, merge or deployment.
- No user answer is required to use or rerun local proof. Future live work requires a verified enforceable bounded contract, sufficient scope/coverage and a separately authorized deployment; credentials alone cannot resolve the guarantee. Host goal status is left unchanged under its rules.

## [2026-09-21] verify | Final receipt ingestion

- `py -3 tools/check_workspace.py` exit 0: 13 immutable raw hashes/registrations, 17 Markdown files, wiki index coverage, 25 Python syntax checks. Original raw hashes unchanged.
- `git -c safe.directory=C:/Users/Brandon/workspaces/litellm diff --check` exit 0; informational line-ending notices only. Final receipt/status wiki edits do not change the frozen runtime reviewed twice.
- Local deliverable is ready for inspection on codex/cost-aware-router. Full goal remains incomplete for the explicit live billing-bound blocker; no goal completion/status mutation made.


## [2026-09-21] publish | Prepare requested GitHub pull request

- User explicitly authorized opening a PR; captured and ingested the additive authorization. Configured destination is bct9321/litellm-router, base main, branch codex/cost-aware-router; no existing open PR for this branch.
- Prior local proof and two clean reviews remain scoped to bounded loopback contracts. No runtime changes in this publishing turn; live billing blocker remains. Structural check passed before publication preparation.
- Publish the reviewed change and receipt for GitHub review; no merge or deployment. Final PR URL is reported in the task.
