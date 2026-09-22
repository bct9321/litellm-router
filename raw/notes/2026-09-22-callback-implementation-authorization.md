# Callback implementation and publication — 2026-09-22

User: "so do it in branch and commit / push", referring to the documented
free-first callback architecture. This authorizes implementing that architecture,
verifying it, committing and pushing expanded-tiers; no deployment/live calls.

Implementation choices (proposed until verified): preserve all original solver
YAML entries. One JEV twenty-way choice is parsed to a structured family/capability
decision in the same operation; no second classifier call or unsupported provider
JSON schema. Normal lower-tier routes and backups insert advanced-<family> (Luna)
after all free attempts and before original paid fallbacks. Higher direct routes
map ADVANCED/EXPERT/FRONTIER to Luna/Terra/Sol, with family paid-capable chain on
failure; do not climb subscription strengths on transport failure. Specialists
remain unchanged. Classifier failure returns existing lower-tier fail default;
solver fallback never changes the original semantic class.

The pre-call callback orders classification then quota handling and target access
validation; quota-exhausted lower semantic aliases rewrite to advanced-family.
Unknown/stale quota keeps legacy fail-open policy unless explicitly configured
fail-closed, with stale snapshots treated unknown. Custom placeholder provider
for jev fails locally if callback is missing; remove original jev paid fallback
chain so missing integration cannot execute a paid model. SDK users must explicitly
run the callback; proxy configuration wires it. Restrict jev input to text chat
completion initially; specialist/modality routes bypass it. Explicit client routing
or endpoint overrides on jev are rejected, not forwarded. Target access and
model-level guardrails must not be bypassed; fail closed on unsupported guardrails
rather than silently execute them incorrectly.

Fallback selection uses configured LiteLLM solver chains, now intentionally
subscription-before-paid. Invalid request handling and retry limits remain pinned
LiteLLM behavior; no application retry loop. Limits/paid eligibility are not strict
budget controls (separate cost-aware branch untouched). Preserve request-local
semantics and no provider/auth/cost data in JEV decision input.

Acceptance: focused RED/GREEN tests, all twenty outcomes, malformed/failure and
concurrency cases, real ProxyLogging pre-call + real Router with fake HTTP,
existing solver/specialist preservation, quota bypass, offline integrity, two
consecutive clean independent reviews; only then commit and push. No OAuth tokens,
model availability, streaming/live costs or model quality claims.
