# Cost-aware router: review and plan forward

Date: 2026-09-21. Status: final local verification and two consecutive clean independent reviews passed; full goal remains incomplete due to the live billing-contract blocker. The historical assessment/findings and target sketches below retain the pre-repair review context. They are not a current defect list. Host goal status is controlled by the app.

Execution amendment: [user authorization](../raw/notes/2026-09-21-router-plan-execution.md) resumes implementation with bounded subagents. Proposed changes below become implemented only as individually verified and reconciled in the log. Host goal status is controlled by the app.

Sources: [review evidence](../raw/notes/2026-09-21-router-review-plan-evidence.md), [delivery contract](../raw/notes/2026-09-21-cost-aware-router-contract.md), [checkpoint log](log.md), and current code linked below. Review baseline: HEAD `9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc` plus all tracked/untracked working changes on `codex/cost-aware-router`.

## Current execution checkpoint

The reviewed dispatch, classifier and ledger changes are implemented. Trusted server request context precedes quota rewriting; actual physical dispatch validates route membership, capabilities, deployment identity, fresh billing contract and the exact normalized wire payload. SQLite reservations cover all five limit scopes before HTTP, including classifier overhead. Unknown and incomplete charges retain capacity across restart and reset.

History now distinguishes comparison-only evidence, nonoverlapping opening balances and unresolved coverage. Canonical totals preserve entry alias, selected alias, provider model and deployment ID. Conflicting final events quarantine exposure rather than releasing it. The CLI reports distinct pending/unknown counts and null totals when amounts are unknown. Provider-period admission requires explicit complete coverage; aggregate history cannot prove the partial activation day.

Final verification: 53 focused tests, 19 real loopback routing scenarios and 10 budget/recovery scenarios passed. Two consecutive independent reviews are clean with no medium-or-higher findings. Exact commands, source hashes and review outcomes are retained in the [immutable receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). Live billing bounds remain unresolved. No credentials, provider calls or live budget amounts are needed for local development.

## Historical assessment before resumed implementation

Keep LiteLLM and the useful work already done. The project has a working local test harness and a durable reservation ledger, but it does **not** yet establish the strict end-to-end contract. Both independent reviews found blocking issues. Clean-review count is zero.

The most important next change is one authorization boundary at the actual outgoing attempt. Every route, classifier result, quota rewrite and fallback must pass it. A classifier rejection alone cannot enforce policy: the pinned LiteLLM complexity router catches plugin exceptions and selects its own fallback.

Live strict activation remains blocked by missing verified billing bounds, especially for alpha Decisions. A local fixture with a declared contract cannot establish that a live provider obeys it. No live budget amounts have been supplied. Finish independent local work, preserve fail-closed behavior, and report the billing-contract blocker if it remains.

## Historical evidence at the planning checkpoint

| Area | Current result | Limit of evidence |
|---|---|---|
| Seven reviewed repairs | Stale quota/backoff, real-text filtering, failed benchmark cost, unknown prices, diagnostics, and answer-leaking vision prompts have focused regressions | Passing fixtures do not establish live model quality or billing |
| Runtime | LiteLLM 1.99.0 and jsonschema 4.26.0 pinned; Python 3.12.14 tested | Transitive dependencies/tokenizer bootstrap need a reproducible receipt |
| Ledger | SQLite atomic reservation, canonical budgets, logical request ceilings, restart persistence, event deduplication, unknown retention | Finality, accounting corrections, identity and history need work |
| Jev | Production plugin receives server estimates/capabilities/spend; accounting uses logical request metadata | Paid choice can bypass free-first; eligibility snapshot can become stale; classifier endpoint/output cap are not bound to the real request |
| Report | JSON CLI exposes model/day/month totals, attempts, resets, remaining and historical rows | History is stored separately, not reconciled into complete spend; pending/unknown are combined in summary |
| Real proxy | Retained PASS: 15 solver attempts, 2 classifier attempts, streams, fallback, quota, restart and two processes | Worker assertion permits zero successes; cancellation case omits partial usage; final rejection often checks only HTTP >=400 |
| Review this turn | 23 focused tests rerun: exit 0; code and retained proof inspected | Real proxy was not rerun for this documentation-only turn |

Current evidence: `outputs/local-proxy/proof.json`, `proxy.log`, `multi-worker-*.log`, and their SQLite ledgers. These are ignored and mutable. A final receipt must preserve sanitized evidence in a unique, registered raw record with code/config hashes.

## Historical review findings addressed by this execution

### Spec axis — blocking behavior

1. **P1: final fallback capability authorization is missing.** [CostGuard](../router/cost_guard.py) checks the entry route; [CostTransport](../router/cost_transport.py) checks origin/price/budget, without original capability requirements or candidate membership. A vision request can reach a priced text-only emergency model. Quota rewriting can also lose original-route context. Bind all targets to trusted deployment metadata and recheck at dispatch.
2. **P1: the assumed output bound is not always sent.** [request_charge](../router/cost_policy.py) substitutes a contractual cap when the request has none. The outbound JSON stays unchanged. Jev's cap exists only in a synthetic accounting wrapper. Bind reservation to the exact normalized outbound request and reject surfaces without an enforceable bound.
3. **P1: partial stream usage can release capacity.** [AccountedStream](../router/cost_transport.py) accepts any buffered usage.cost as final. Reproduction: reserve 90 out of 100, receive partial cost 10 without completion, and remaining becomes 90. Finality must be established by a provider-specific completion contract; timeout/cancel/partial cost alone is insufficient.
4. **P1: identities are conflated.** A provider-model-keyed contract contains one fixed alias. Two aliases sharing that model lose distinct attribution. The HTTP provider model is not stored separately from LiteLLM deployment identity. Preserve requested alias, selected alias, selected tier, canonical model, provider model and deployment ID separately.
5. **P1: classifier dispatch is not bound to the declared endpoint.** Jev checks the accounting contract's loopback origin but sends through a separate client to `JEV_DECISIONS_URL` or its external default. Validate the exact method/origin/path and controlled output contract before creating a reservation or opening a connection. Cover cancellation of this separate client too.
6. **P1: deterministic free-first is inconsistent.** Direct `choose()` prefers free; strict Jev receives free and paid candidates together and the fixture chooses paid while free exists. Apply free-first to the candidate set itself, then let Jev choose within that set. Unlock compatible paid fallback only after free options are unavailable, exhausted or fail under policy.
7. **P1: history is not reconciled.** [Ledger.import_activity](../router/spend_ledger.py) deduplicates aggregate rows but excludes all history from budget counters. Historical spend before activation therefore cannot constrain the current month. Introduce scoped opening balances and coverage; never guess overlap or substitute zero for missing history.
8. **Contract gap: fresh prices and billing coverage.** The schema has no price timestamp, expiry, account scope, supported request surface or complete billing-dimension contract. Counting UTF-8 bytes does not bound image pixels, remote content, audio duration, reasoning or provider-added fees. Reject unsupported/stale contracts and represent the reason explicitly.

### Standards/proof axis

- **P2: false-positive concurrency gate.** `successful <= 1` admits a run with no successful requests. Require exactly one admitted attempt and a typed budget rejection from the other worker while the first remains reserved. Inspect in-flight exposure, then settlement. Replace timing-only sleeps with synchronization.
- **P2: stale authority.** The classifier wiki still describes removed filtering; operations mixes the tested Python 3.12 environment with `py -3` strict tests. Reconcile current sections; retain historical checkpoint entries and append explicit corrections.
- **P2: evidence is broader than assertions.** “Budget prevents dispatch” currently exceeds the output-contract cap; it does not independently prove exhausted overall/model day/month budgets. Classifier accounting success can pass via fallback because its fixture still answers `tier` while strict mode requests `model`. Require expected diagnostics and wire/ledger observations.
- **Workflow correction:** some prior fixes preceded focused failing checks, and later notes overstate full verification. Do not invent RED evidence retroactively. Add missing regressions before the next behavioral edit and preserve actual failures/results.

## Current call flows

These are conceptual call flows verified against current code and selected pinned LiteLLM internals, not captured full Python stack traces.

```text
POST /v1/chat/completions
  -> LiteLLM proxy callbacks
     -> CostAwareGuard -> CostGuard.async_pre_call_hook [FIRST]
        -> server registry: original alias, capabilities, allowed deployment IDs, policy hash
        -> direct route: request_charge -> choose -> rewrite model
        -> jev: leave model for complexity router
     -> OpenRouterQuotaGuard.async_pre_call_hook [SECOND]
        -> fresh quota -> trusted exhaustion handoff -> optional rewrite
  -> LiteLLM resolves deployment / fallback
     -> CostGuard.async_pre_call_deployment_hook
        -> validate trusted deployment, original capabilities and supported adapter
        -> dispatch_context.set(request, deployment, policy_revision)
     -> LiteLLM/OpenAI adapter -> httpx
        -> CostTransport.handle_async_request
           -> recheck membership, capabilities, free-first, exact endpoint/model
           -> normalize actual body -> enforce output cap -> request_charge
           -> Ledger.reserve [BEGIN IMMEDIATE; global/model day/month + request]
           -> upstream HTTP
           -> AccountedStream -> Ledger.settle

Jev branch inside complexity routing
  -> pinned ComplexityRouter._classify_with_plugin
     -> RoutingContext(raw_messages, structured_messages, metadata)
     -> OpenRouterJevClassifier.classify
        -> transcript -> _eligible_models -> Decisions payload
        -> exact contract-bound Decisions JSON -> JevAccounting.reserve [required trusted request ID]
        -> contract origin/path/model/cap -> httpx.AsyncClient.post -> JevAccounting.settle
        -> recompute eligibility after settlement -> selected tier or _fallback_choice
     -> on plugin exception: LiteLLM _classifier_failure_outcome
        -> configured fallback tier [still passes final dispatch authority]
  -> tier maps to solver alias -> ordinary deployment flow above

Report/import
  tools/cost_report.py
    -> optional import_openrouter_activity -> Ledger.import_activity
    -> Ledger.report -> JSON stdout
```

## Implemented object boundaries

Current Python/JSON keys below are descriptive shapes. Monetary fields are integer USD nanodollars; a null amount remains unknown. They are not a runnable policy or invented live limits.

```python
trusted_context = {
    "id": "server-generated UUID",
    "entry_alias": "original requested alias",
    "payload": {...},                      # copied request, never report transcript
    "required_capabilities": frozenset(...),
    "allowed_deployments": frozenset(...),
    "policy_revision": "full policy SHA256",
    "failed_deployments": set(),
    "free_unavailable": False,             # trusted quota handoff only
    "expires": "monotonic timestamp",
}
deployment = {                             # keyed by LiteLLM model_info.id
    "alias": "selected alias", "provider_model": "wire model",
    "contract": "contract key", "capabilities": [...], "free": False,
}
candidate = {
    "alias": "tier or route", "canonical": "shared budget identity",
    "contract": "contract key", "deployment_ids": [...],
    "capabilities": [...], "free": False,
}
attempt = {
    "id": "physical attempt UUID", "request_id": "logical request UUID",
    "model": "canonical model", "entry_alias": "original alias",
    "alias": "selected alias", "provider_model": "wire model",
    "deployment_id": "trusted deployment", "selected_tier": None,
    "kind": "solver or classifier", "contract_revision": "revision",
    "billing_scope": "configured scope", "created": "UTC ISO timestamp",
    "day": "YYYY-MM-DD", "month": "YYYY-MM",
    "reserved": "integer bound", "estimated": "integer or null",
    "reported": "integer or null",
    "state": "pending | estimated | unknown | provider-reported",
    "contract_breached": 0,
}
```

`Ledger.report()` returns `unit`, `timezone`, `as_of`, `coverage`, `overall`, `models`, `attempts`, `historical_imports`, `historical_models`, and `historical_canonical`. Each overall/model `today` and `month` includes `provider_reported`, `estimated`, `known_estimated`, `exposure`, `remaining`, `limit`, `reset_at`, separate pending/unknown counts/exposure, `admission`, and coverage. A snapshot guides selection; only `reserve()` authorizes dispatch. Full definitions are in [schema](../router/cost-router.schema.json), [transport](../router/cost_transport.py), and [ledger](../router/spend_ledger.py).

## Historical target boundaries and object sketches

Keep the existing small modules. Extend them around explicit objects instead of introducing another gateway or a second routing engine. The following are proposed shapes, **not current schema or usable live configuration**. Money is integer USD nanodollars; omitted/unknown money is null, never implicit zero.

```typescript
type RequestContext = {
  requestId: string;                 // generated server-side
  entryAlias: string;                // before quota rewrite
  requiredCapabilities: string[];   // request + server route constraints
  policyRevision: string;
  billingScope: string;              // local-router scope or established provider scope
  failedDeploymentIds: string[];
  normalizedRequest: OpenAIRequest; // copied server-side; never echo private content in report
};

type Deployment = {
  id: string;                       // pinned LiteLLM deployment ID
  alias: string;                    // actual selected model group
  canonicalModel: string;           // shared accounting identity
  providerModel: string;            // outbound provider model
  origin: string;
  path: string;
  capabilities: string[];
  billingContractId: string;
};

type BillingContract = {
  id: string;
  revision: string;
  kind: 'loopback-fixture' | 'verified-provider'; // latter is currently unsupported
  validFrom: string;
  expiresAt: string;
  evidenceRef: string;
  origin: string;
  path: string;
  supportedSurfaces: string[];       // e.g. bounded text chat only
  maximumOutputTokens: number;
  inputRateNanos: bigint;
  outputRateNanos: bigint;
  fixedMaximumNanos: bigint;
  finalUsageRule: string;            // adapter-defined, evidenced finality
};

type Estimate = {
  estimatedNanos: bigint | null;
  maximumChargeNanos: bigint | null;
  contractRevision: string;
  requestDigest: string;            // exact normalized outbound body, not just transcript
  status: 'priced' | 'missing' | 'stale' | 'unsupported';
};

type Attempt = {
  id: string;
  requestId: string;
  kind: 'classifier' | 'solver';
  entryAlias: string;
  selectedAlias: string;
  selectedTier: string | null;
  canonicalModel: string;
  deploymentId: string;
  providerModel: string;
  billingScope: string;
  contractRevision: string;
  admittedAt: string;
  estimatedNanos: bigint | null;
  reservedNanos: bigint;
  observedCostNanos: bigint | null;  // provisional evidence
  finalCostNanos: bigint | null;
  state: 'reserved' | 'dispatched' | 'pending' | 'unknown' | 'final';
  providerRequestId: string | null;
};

type HistoryAggregate = {
  identity: { scope: string; dayUTC: string; providerModel: string; endpointId: string };
  canonicalModel: string;
  amountNanos: bigint | null;
  sourceRevision: string;
  coverage: 'nonoverlapping' | 'overlapping' | 'unknown';
  disposition: 'opening-balance' | 'comparison-only' | 'unresolved';
};
```

Use JSON integers for these conceptual bigint values at the Python API boundary; avoid JavaScript numeric conversion for values beyond its safe range. Budget policy must bound supported integers to the chosen storage representation. These shapes can be small dataclasses/validated dictionaries rather than a framework.

Jev's compact snapshot needs candidate alias/tier, canonical model, capabilities, estimate, maximum charge, model/overall/request remaining and rejection reasons. Do not include the ledger's whole transaction history. The snapshot is advisory and can race; the final atomic transaction decides admission.

## Target dispatch pseudocode

```python
def begin_request(client_body, route_policy):
    context = server_owned_context(client_body, route_policy)
    # Preserve identity/capabilities before quota decisions change the alias.
    return context

async def route(context):
    choices = eligible_deployments(context, current_report())
    choices = prefer_free_if_available(choices, quota_state(), context.failedDeploymentIds)
    if not choices:
        deny('no_eligible_deployment')
    if needs_jev(context):
        # Classifier itself is a budgeted, bounded physical attempt.
        answer = await dispatch_classifier(context, choices)
        candidate = validate_choice_or_choose_safe_fallback(answer, choices)
    else:
        candidate = deterministic_choice(choices)
    return await litellm_route(candidate, context)

async def authorize_and_send(context, resolved_deployment, outgoing_body):
    # Runs AFTER every LiteLLM resolver, quota rewrite, retry and fallback.
    deployment = trusted_registry.resolve(resolved_deployment)
    require_allowed_route_and_capabilities(context, deployment)
    require_free_first_or_recorded_fallback_reason(context, deployment)
    contract = require_current_complete_contract(deployment, outgoing_body)
    body = enforce_output_limit_and_supported_fields(outgoing_body, contract)
    estimate = calculate_bound(body, contract)  # same body we will send
    attempt = ledger.reserve_atomic(context, deployment, estimate)
    try:
        # No automatic HTTP retries: each physical attempt needs its own reservation.
        return await send_and_observe(body, deployment, attempt)
    except BaseException:  # includes cancellation; preserve original exception
        ledger.mark_unresolved_if_not_final(attempt)
        raise
```

The hook API must be demonstrated to enforce this boundary for each supported adapter. Do not assume a process-global httpx client intercepts every provider, sync method, tool or auxiliary network call. Unsupported execution paths must refuse strict-mode dispatch. All workers must use identical policy/contract revisions, not just equal numeric budget limits.

## Reservation and settlement pseudocode

```python
def reserve_atomic(context, deployment, estimate):
    require(estimate.maximumChargeNanos is not None)
    with sqlite_begin_immediate():
        require_policy_revision_and_coverage(context)
        require_fresh_contract(estimate.contractRevision)
        exposure = sum_final_and_unresolved_exposure()
        # Five checks share this transaction, using one canonical identity:
        for bucket in [overall_day, overall_month,
                       model_day(deployment.canonicalModel),
                       model_month(deployment.canonicalModel),
                       logical_request(context.requestId)]:
            require(exposure[bucket] + estimate.maximumChargeNanos <= limit[bucket])
        insert_attempt(state='reserved', bound=estimate.maximumChargeNanos)
    # Commit before any outgoing request bytes; crash here retains reservation.
    return attempt

def observe(attempt, event):
    with sqlite_begin_immediate():
        if duplicate_same_identity_and_payload(event):
            return
        if conflicting_duplicate(event):
            retain_exposure_and_flag_reconciliation()
            return
        record_event(event)
        if contract_proves_final_usage(event, complete_response_state):
            record_final_charge_without_clamping(event.amount)
            if event.amount > attempt.reservedNanos:
                flag_contract_breach_and_disable_further_dispatch_for_contract()
        else:
            record_provisional_evidence_keep_reservation()

def exposure(attempt):
    if attempt.state == 'final':
        return attempt.finalCostNanos
    return max(attempt.reservedNanos, attempt.observedCostNanos or 0)
```

The `or 0` above is only the lower bound of an absent provisional observation; the retained reservation still represents unresolved liability. Unknown spend is not reported as zero. If the charge contract is violated, recording the actual excess is honest accounting but cannot retroactively prevent overspend. The hard guarantee is conditional on a verified bound, which is why activation requires that evidence.

State flow: `reserved -> dispatched -> final`, or `dispatched -> pending/unknown -> final`. A crash before/after send retains the bound; an idle timeout does not refund it. Final zero requires explicit authoritative evidence. Define daily/monthly attribution around UTC admission and expose carried unresolved liabilities separately so users can distinguish today's charges from prior pending exposure.

## History and operator report plan

1. Establish billing scope and activation timestamp. An account-wide aggregate cannot be merged with an unrelated key/router scope.
2. Treat completed periods strictly before local activation as opening balances only when scope and coverage are known to be nonoverlapping.
3. Match overlapping per-attempt records by scoped provider request ID if available. Aggregate-only overlap remains comparison evidence; it is not silently added, subtracted or replaced with `max()`.
4. For unresolved activation-day/month history, show incomplete coverage. If the budget claims to cover that whole provider period, refuse paid admission until a supported opening balance or reconciliation is supplied. A clearly labeled router-since-activation report can still be produced.
5. Deduplicate by provider scope/day/model/endpoint, preserving import revisions. Changed aggregate values require explicit reconciliation rather than creating a second charge. Test old import IDs and schemas as well as new rows.

Proposed report shape:

```typescript
type ModelSpendReport = {
  canonicalModel: string;
  today: PeriodSpend;
  month: PeriodSpend;
  aliases: Record<string, { attemptCount: number }>;
};
type PeriodSpend = {
  finalSpendNanos: bigint | null;
  estimatedNanos: bigint | null;
  reservedExposureNanos: bigint;
  provisionalReportedNanos: bigint | null;
  openingBalanceNanos: bigint | null;
  pendingCount: number;
  unknownCount: number;
  remainingNanos: bigint | null;
  admission: 'allowed' | 'exhausted' | 'coverage_unknown' | 'contract_missing';
  resetsAtUTC: string;
  coverage: { scope: string; since: string; complete: boolean; gaps: string[] };
};
```

Expose per-request estimates and rejection reasons through the existing CLI first; an HTTP API is optional because the contract permits either. Snapshot report reads consistently. Do not build an unrelated dashboard. Avoid treating unknown estimate totals as zero, and preserve provider-reported amounts separately from computed estimates.

## Ordered work packages

Each package starts with raw evidence/wiki ingestion, then a focused failing test, the smallest repair, focused validation, and a checkpoint. Do not resume these packages until implementation work resumes.

| Order | Work / main files | Exit condition |
|---|---|---|
| 1 | Policy/deployment identities: cost schema, cost_policy, cost_guard, quota context | Trusted mapping covers direct aliases, Jev tiers, quota targets and all fallbacks; original capabilities survive rewrites; aliases sharing one model remain distinct |
| 2 | Actual dispatch contract: cost_transport, JevAccounting | Exact endpoint and outgoing cap validated; no accounting-only cap; missing/stale prices and unsupported billing surfaces rejected before network |
| 3 | Free-first and classifier behavior: jev_classifier, shared eligibility | Jev cannot choose paid while usable free candidates exist; classifier cost/failure/timeout preserves request identity; exhausted request budget rejects every resolver fallback |
| 4 | Stream/failure settlement: cost_transport, spend_ledger | Partial usage + cancellation retains bound; final usage settles once; duplicate/conflicting/late evidence handled; over-bound actual cost flags breached contract |
| 5 | Scope/history/report: spend_ledger, cost_report | Nonoverlapping opening balance counted once; ambiguous overlap visible and blocks unsupported whole-period guarantee; all requested spend/estimate/reset/coverage fields exposed |
| 6 | Real proxy matrix: local_proxy_probe and focused suites | Strong assertions prove all scenarios below with deterministic synchronization and real hooks; production module-loading/configuration parity checked |
| 7 | Evidence and independent reviews: wiki, requirements/config docs | Fresh exact commands/hashes/exit codes, consistent setup, two consecutive clean independent adversarial reviews; any code fix resets clean count |

Preserve the original repaired cases throughout. Reuse LiteLLM deployment resolution, retries/fallback traversal, custom hooks, response objects and available token/cost helpers when their behavior is suitable. The pinned native reservation code can shrink a reservation to remaining balance and skip unknown-cost reservation, so it is not a substitute for the strict gate unchanged. Record the exact native helper/gap rationale for each custom mechanism; never sum native spend logs and the custom ledger as independent charges.

## Acceptance matrix that must become real proof

| Scenario | Required observation |
|---|---|
| Shared aliases / deployments | Two real aliases share one canonical cap; each attempt keeps its actual selected alias, provider model and deployment ID |
| Five independent budget scopes | Hit overall day/month, model day/month and combined classifier+solver request ceilings separately; typed denial, zero forbidden upstream calls |
| Two proxy processes | Barrier-controlled overlap; exactly one admitted and one budget-denied; one in-flight reservation; both share the same policy/SQLite; persisted totals survive restart |
| Emergency / quota rewrites | Compatible paid fallback succeeds within cap; priced incompatible/unlisted fallback and quota targets never dispatch |
| Jev success | Actual Decisions request contains eligible candidates; diagnostics assert successful selection, not accidental fallback; solver receives selected eligible alias |
| Jev failure / rejection | Missing key, malformed answer, timeout, BudgetDenied and cancellation; LiteLLM's own fallback cannot bypass final authorization; classifier unknown cost stays reserved |
| Streaming | Partial usage then cancel, split SSE events, complete final usage, missing final usage, duplicate and conflicting final events |
| Prices / output | Missing, expired, invalid and unsupported billing contracts; absent/conflicting output limits; n > 1; exact outgoing JSON respects bound |
| Crashes / resets | Process termination while reservation outstanding, restart, UTC day/month rollover; unresolved capacity persists |
| History | Repeat import with changed label, distinct scopes, old schema/IDs, known nonoverlap, overlap, corrected aggregate, unknown historical amount |
| Original seven repairs | Keep current focused regressions; prove production classifier/health diagnostics where fake proxy can exercise them |

Use distinctive errors and record actual upstream attempts, not only `status >= 400`. Test finite synthetic nanodollar budgets only. All subprocesses must deny external sockets and avoid inherited provider secrets; prove the helper cannot silently bypass its own guard. Preserve unique run directories instead of overwriting the only proof. Runtime version in receipts must be measured, not a hardcoded label.

## Commands and completion receipt

Current focused command rerun in this review, exit 0:

```powershell
.venv312\Scripts\python.exe -m unittest tools.test_cost_policy tools.test_router_repairs tools.test_budget_ledger
```

After implementation resumes and each affected check passes, run the real local proof and structural checks:

```powershell
$env:CUSTOM_TIKTOKEN_CACHE_DIR = Join-Path $PWD 'outputs/token-cache'
.venv312\Scripts\python.exe tools\local_proxy_probe.py
py -3 tools\check_workspace.py
git -c safe.directory=C:/Users/Brandon/workspaces/litellm diff --check
```

Use Python 3.12 with `requirements.txt` for runtime setup. The installed environment is available locally; do not claim a clean machine can reproduce it until dependency and public tokenizer-cache setup is captured and tested. `py -3 tools/check_workspace.py` remains valid as the standard-library-only structural check. The current probe starts temporary loopback services and stops them; it is not a persistent operational server recipe.

The final delivery receipt must include changed files, exact validation commands/exit codes, scenario assertions/results, measured versions, code/policy hashes, proof locations, both review outcomes, setup/start/report instructions and remaining risks. Local proof and live billing/deployment must remain clearly separate. No paid limits, credentials or live activation are needed to finish local development.

No user question blocks this plan. The unresolved external dependency is a trustworthy bound for every live billable path. Do not ask for keys to paper over it, weaken the guarantee or mark the delivery goal complete.

Related: [cost awareness](cost-awareness.md), [operations](operations.md), [open questions](open-questions.md), [workflow](workflow.md).
