# OpenRouter quota guard

Status: current implementation, 2026-09-21; final integration/review gates pending.
Source: [working quota guard](../router/openrouter_quota_guard.py), with
[original imported source](../raw/openrouter_quota_guard.py) retained as historical
evidence. The [repair contract](../raw/notes/2026-09-21-cost-aware-router-contract.md)
and [execution authorization](../raw/notes/2026-09-21-router-plan-execution.md)
govern these changes.

## Decision flow

The pre-call hook checks aliases in its explicit free-route map and model names
ending in `:free`. Other models pass through unchanged. It calls `/api/v1/key`
and expects `data.free_model_daily_requests` with `used`, `limit`, and `remaining`.
All three must be nonnegative integers (booleans are rejected), `used <= limit`,
and `remaining == limit - used`; malformed/inconsistent counts are unknown.
It caches the snapshot under an async lock, normally for 30 seconds (minimum 5).

| State | Condition | Action |
|---|---|---|
| unknown | No usable snapshot | Continue if fail-open; otherwise HTTP 503 |
| exhausted | remaining ≤ reserve threshold | Rewrite a known alias if action=route; otherwise HTTP 429 |
| critical | used ≥ 90%, not exhausted | Keep route; log status transition |
| warning | used ≥ 80%, not critical/exhausted | Keep route; log status transition |
| ok | Below the thresholds | Keep route |

`jev` rewrites to `paid-general-capable`; free capability aliases rewrite to the
corresponding paid alias, and `fast`, `vision`, and `compression` to their paid
forms. A concrete `:free` slug without a mapping is blocked at exhaustion. The
guard does not blindly strip `:free` to invent a paid model.

## Controls

| Environment variable | Default |
|---|---|
| `OPENROUTER_QUOTA_CACHE_SECONDS` | 30 |
| `OPENROUTER_QUOTA_WARN_PERCENT` | 80 |
| `OPENROUTER_QUOTA_CRITICAL_PERCENT` | 90 |
| `OPENROUTER_QUOTA_BLOCK_REMAINING` | 0 |
| `OPENROUTER_QUOTA_FAIL_OPEN` | true |
| `OPENROUTER_QUOTA_EXHAUSTED_ACTION` | route (`route` or `block`) |
| `OPENROUTER_KEY_URL` | `https://openrouter.ai/api/v1/key` |
| `OPENROUTER_QUOTA_ROUTE_MAP` | `{}`; valid string-to-string entries extend the default map |

For example, a reserve threshold of 25 triggers exhaustion behavior at 25 remaining.
It is a routing threshold, not an atomic reservation. The snapshot and lock are
per process; there is no distributed quota counter or request-by-request decrement.

On refresh failure or missing/malformed data, `_get_snapshot` returns unknown;
it never returns an expired snapshot as current. Failed refreshes are backed off
for the configured cache interval, including repeated calls from response-header
hooks. `OPENROUTER_QUOTA_FAIL_OPEN=false` therefore returns HTTP 503 when fresh
quota cannot be established. The legacy default remains `true`; the strict local
proof explicitly configures `false`.

In cost-aware mode the cost guard captures original route requirements before
quota rewriting. A verified exhaustion rewrite marks free deployments unavailable
in trusted request context. The actual paid target still needs allowed-deployment,
capability, billing-contract and budget authorization at final dispatch. The quota
route map cannot create spending permission. Conversely, `action=block` alone is
not a free-only spending policy: other configured fallback paths are separate.

Historical correction: the imported source reused stale data after failed refresh,
regardless of fail-open, and lacked failed-refresh backoff. That defect is repaired
in the working copy; the raw source bytes remain unchanged.

## Visibility

The post-call hook fetches quota even for responses whose original route was paid.
It returns `x-openrouter-free-used`, `-limit`, `-remaining`, `-percent`, `-status`,
and `x-openrouter-quota-cache-age`. When no snapshot exists it returns only status
`unknown`. Focused fake-HTTP checks cover status and refresh backoff; actual
proxy/stream evidence must be read from the named runs in [log](log.md), not
inferred from hook existence. Final proof/review is still pending.

Related: [architecture](architecture.md), [operations](operations.md), [open questions](open-questions.md).

## Schema correction and repair contract, 2026-09-21

The [additive correction](../raw/notes/2026-09-21-cost-aware-router-contract.md) establishes that the official key reference documents free_model_daily_requests. The earlier research schema-absence claim is superseded. Implemented repair: stale/missing/malformed snapshots are unknown, `OPENROUTER_QUOTA_FAIL_OPEN=false` rejects them, and failed refreshes have backoff. Quota rewrites remain subject to capabilities and deterministic budgets in the strict dispatch adapter. [Focused repairs](../tools/test_router_repairs.py) and the [real-proxy harness](../tools/local_proxy_probe.py) are the verification seams; no live quota guarantee is claimed.
