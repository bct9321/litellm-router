# Jev classification

Status: locally verified implementation, 2026-09-21; final proof and two clean
independent reviews retained in the [receipt](../raw/notes/2026-09-21-local-delivery-receipt.md). Sources: [working classifier](../router/jev_classifier.py),
[cost policy](../router/cost_policy.py), [dispatch boundary](../router/cost_transport.py),
[delivery contract](../raw/notes/2026-09-21-cost-aware-router-contract.md), and
[execution authorization](../raw/notes/2026-09-21-router-plan-execution.md).
The [imported classifier](../raw/jev_classifier.py) remains historical evidence;
its former metadata filtering is not current behavior.

## Transcript and legacy mode

The plugin accepts mapping or LiteLLM object contexts with `structured_messages`
or `raw_messages`. It keeps system/user/assistant text and excludes tool-role
records. User requests containing `chat_id`, `message_id` or other metadata words
are preserved. Images are not passed as image inputs to the classifier.

By default the newest system/profile message and last eight conversation messages
are retained, with each message limited to 3,000 characters. This shortened
transcript is routing context, not the full solver cost estimate. Invalid limits
have controlled fallback behavior.

Without `COST_ROUTER_CONFIG`, the legacy Decisions API asks for one of eight tiers:
GENERAL, REASONING, AGENTIC or CODING, each EFFICIENT or CAPABLE. Implementation
work takes CODING precedence over analysis. `JEV_FAIL_TIER` defaults to
`GENERAL_CAPABLE`. This legacy mode does not provide the strict budget guarantee.

| Legacy variable | Default |
|---|---|
| `JEV_MODEL` | `typesafe/jev-1.13` |
| `JEV_DECISIONS_URL` | `https://openrouter.ai/api/alpha/decisions` |
| `JEV_TIMEOUT_SECONDS` | `5.0`, finite and positive |
| `JEV_MAX_MESSAGES` | `8`, positive |
| `JEV_MAX_CHARS_PER_MESSAGE` | `3000`, positive |
| `JEV_FAIL_TIER` | `GENERAL_CAPABLE` |
| `JEV_LOG_RAW_ANSWER`, `JEV_LOG_TIMING` | `true` |

`OPENROUTER_API_KEY` is required for the HTTP call. Missing keys, empty transcript,
handled request failures or invalid answers take the fallback path. Logs may
contain response data; sanitized evidence is required before retention.

## Strict local selection

With `COST_ROUTER_CONFIG`, the complete policy is validated at construction.
`routes.jev` candidates use the pinned LiteLLM tier names, mapped to configured
solver deployments. The guard captures the original request in a private registry;
Jev requires its generated request identity and matching policy revision. User
metadata cannot replace authoritative capabilities, payload or spend context.

For each candidate, Jev receives server-calculated estimate and conservative
bound, canonical model, capabilities, and current model/overall/request remaining
capacity. Estimates use the full original solver request and actual provider
model, not merely the shortened transcript. Invalid, expired, unsupported,
failed or unavailable deployments are excluded. Eligible free candidates exclude
paid candidates from the choice set. Quota exhaustion or configured free failures
can unlock compatible paid fallbacks.

The classifier's own charge is reserved under the same logical request. Its
contract binds the actual POST origin/path, provider model and output cap; strict
mode does not take endpoint/model overrides from the legacy environment variables.
The exact outgoing Decisions body includes `max_tokens` and is priced before
HTTP dispatch. Redirects and environment proxy inheritance are disabled. Only a
dated bounded loopback Decisions contract is currently supported; live alpha
Decisions lacks a verified maximum-charge contract and is refused.

On success, eligibility is recomputed after classifier settlement. Missing or
malformed choices and handled failures select only a currently eligible fallback.
Cancellation propagates while retaining unknown charge exposure. Failed billable
responses remain accounted; absent final cost never becomes zero.

The pinned LiteLLM complexity router can catch plugin errors and choose its own
fallback. Consequently Jev is advisory: every actual solver dispatch must still
pass the deterministic final gate for capabilities, allowed deployment, fresh
contract and atomic budget reservation.

## Verification boundary

[Classifier controls](../tools/test_classifier_controls.py) and
[original repairs](../tools/test_router_repairs.py) cover the public `classify`
seam with fake HTTP. [Local proxy probe](../tools/local_proxy_probe.py) exercises
the pinned real complexity-router path; [budget matrix](../tools/proxy_budget_matrix.py)
exercises independent budget scopes and concurrent processes. Current run outcomes
are retained in the [receipt](../raw/notes/2026-09-21-local-delivery-receipt.md) and [log](log.md).
Historical checkpoint claims retain their original scope and are superseded by
subsequent correction entries.

Related: [routing](routing.md), [cost awareness](cost-awareness.md),
[operations](operations.md), [delivery plan](router-delivery-plan.md).
