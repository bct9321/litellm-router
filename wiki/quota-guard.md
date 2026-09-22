# OpenRouter quota guard

Current proposed quota behavior (2026-09-22): see the [free-first callback design](semantic-routing-alternative.md). Quota exhaustion should skip unavailable free solver attempts in favor of the subscription fallback policy. The baseline top-level jev-to-paid rewrite below conflicts with that target and needs deliberate reordering; no guard behavior changed in this documentation turn.

Status: observed source behavior, 2026-09-20; API and hook integration unverified.
Source: [openrouter_quota_guard.py](../raw/openrouter_quota_guard.py),
`DEFAULT_ROUTE_MAP`, `_get_snapshot`, `async_pre_call_hook`, and header hook.

## Decision flow

The pre-call hook checks aliases in its explicit free-route map and model names
ending in `:free`. Other models pass through unchanged. It calls `/api/v1/key`
and expects `data.free_model_daily_requests` with `used`, `limit`, and `remaining`.
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

For example, a reserve threshold of 25 triggers exhaustion behavior at 25 remaining.
It is a routing threshold, not an atomic reservation. The snapshot and lock are
per process; there is no distributed quota counter or request-by-request decrement.

On refresh failure, `_get_snapshot` returns a previous snapshot even when stale.
This occurs regardless of `FAIL_OPEN`; that flag is consulted only if no snapshot
is returned. Consequently `FAIL_OPEN=false` is not strict fresh-data enforcement.
Also, action `block` alone does not turn the entire router into free-only mode:
other configured fallback chains can still spend money.

## Visibility

The post-call hook fetches quota even for responses whose original route was paid.
It returns `x-openrouter-free-used`, `-limit`, `-remaining`, `-percent`, `-status`,
and `x-openrouter-quota-cache-age`. When no snapshot exists it returns only status
`unknown`. Header delivery through an actual proxy/stream remains to be verified.

Related: [architecture](architecture.md), [operations](operations.md), [open questions](open-questions.md).

## ChatGPT isolation — 2026-09-22

[Request and evidence](../raw/notes/2026-09-22-tier-limit-evidence.md). Both public hooks now bypass OpenRouter lookup for the twelve new ChatGPT aliases, direct chatgpt/ names, or explicit ChatGPT provider metadata. Response provider metadata also suppresses OpenRouter headers after Jev routing. Verified with fake/no-network hook checks; actual proxy header delivery remains unverified.
