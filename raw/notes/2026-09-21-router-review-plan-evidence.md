# Router review and planning evidence

Date: 2026-09-21. Origin: user request in this task: "Review everything and write a clear plan forward. give sudocode, call stacks, object shapes, etc."
Status: review observations and proposed next work; not implementation approval for a changed contract.

The host reports the delivery goal paused. This turn reviews and documents the current worktree; it does not resume implementation. Baseline HEAD: 9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc. Scope includes tracked differences plus new router/, tools/, requirements, raw notes and wiki files. Existing raw content is preserved.

## Verification observed in this review

`.venv312\Scripts\python.exe -m unittest tools.test_cost_policy tools.test_router_repairs tools.test_budget_ledger`: exit 0; 23 tests passed. This is focused test evidence, not full contract proof.

The retained `outputs/local-proxy/proof.json` from the prior turn reports PASS with LiteLLM 1.99.0, Python 3.12.14, 15 solver attempts and 2 classifier attempts. It names multi-process shared-ledger, streaming, cancellation, fallback, quota and restart scenarios. The proxy was not rerun during this planning turn. Inspection of the retained multi-worker SQLite file found one attempt reserved at 102 nanodollars and reported at 20. The harness assertion accepts zero successful workers too, so the retained success does not make that assertion sufficient.

A read-only Python reproduction created a temporary Ledger with a 100-nanodollar limit, reserved 90, set an AccountedStream buffer to `data: {"usage":{"cost":0.00000001}}` without a terminal marker, and invoked `_settle()`. Observed: state `provider-reported`, remaining 90. Thus an incomplete stream can release 80 nanodollars of unresolved reservation.

A second reproduction called `request_charge` with a contract maximum of 4 output tokens and a request containing only messages. It returned estimate/bound 52/52 and left the outgoing object without an output-token ceiling. The estimator assumes a maximum that this path does not enforce on the wire.

## Current code and pinned upstream observations

- `router/cost_guard.py` checks entry-route candidates, but its deployment hook does not check original capabilities or allowed fallback membership. `router/cost_transport.py` enforces price/origin/budget, not capabilities. These checks are distinct.
- Pinned LiteLLM `router_strategy/complexity_router/complexity_router.py`, `_classify_with_plugin`, catches plugin exceptions and converts them to its configured fallback. Raising BudgetDenied in Jev cannot be the final authorization boundary.
- Solver contracts are keyed by provider model with one fixed alias. Two logical aliases sharing that model cannot both retain accurate attribution. Provider model, logical alias, classifier tier and LiteLLM deployment ID need distinct fields.
- Jev validates a loopback origin in its declared accounting contract but sends to a separate environment/default Decisions URL. That URL is not bound to the contract. Its output ceiling is added to an accounting wrapper, not the actual Decisions document.
- Strict Jev receives both free and paid candidates and can choose a paid candidate while free candidates remain; the current successful fixture deliberately does so. A deterministic free-first gate must make the intended policy explicit.
- Contracts have no price version/expiry or request-surface billing coverage fields. UTF-8 byte counting does not establish a general bound for image/audio/remote-content/reasoning/provider-side billing.
- History imports remain explicitly separate with overlap unresolved; no opening-balance reconciliation is implemented. A stable aggregate ID avoids duplicate rows but does not establish complete month spend.
- Pinned LiteLLM `proxy/spend_tracking/budget_reservation.py` can resize a crossing reservation to remaining capacity and skips reservation for unknown/nonpositive cost estimates. These paths do not meet this goal's hard upper-bound contract unchanged. Reuse proxy routing/hooks/usage facilities; keep strict corrections limited to demonstrated gaps.

## Independent review outcomes

Spec reviewer: not clean; missing fallback capability authorization, attribution, bounded classifier contract, and historical reconciliation. Standards/proof reviewer: not clean; weak multi-worker assertion and stale wiki claims, plus confirmed dispatch/output/finality gaps. These reviews do not satisfy the two-clean-review gate. Clean count: zero.

## Direction

Write a source-linked plan separating current implementation from proposed object shapes, call flows and algorithms. Preserve the seven repaired regression areas. Repair final-dispatch authority, actual charge bounds, final settlement, scoped history, and falsifiable integration proofs before requesting fresh independent completion reviews. No live limits are supplied or inferred. No provider calls, secret reads, deployment, merge or publishing are authorized by this review request.
