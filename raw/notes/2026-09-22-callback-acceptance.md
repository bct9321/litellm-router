# Callback routing offline acceptance — 2026-09-22

Scope: implement, commit and push expanded-tiers under the user authorization
in 2026-09-22-callback-implementation-authorization.md. Base HEAD before commit:
9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc. Strict cost branch remains
69d7d34a8162567e714917c80f426eae256ba75b; it was not merged or edited.

## Verification

Python 3.12, installed LiteLLM 1.99.0, httpx 0.28.1, PyYAML 6.0.3.
Command: `.venv312\Scripts\python.exe -m unittest tools.test_callback_routing tools.test_twenty_tiers tools.test_routing_signal_api`.
Result: exit 0, 21 tests passed. No live provider calls; HTTP and solver transports
are fixtures. Current code, tests and constraints are linked from the wiki.
`py -3 tools/check_workspace.py`: exit 0 before this receipt, 17 raw registrations,
16 Markdown files, 15 Python syntax checks. Final ingestion reruns this check.

Evidence covers all twenty concurrent semantic decisions, one classifier call per
request, family/capability/class names, four candidates narrowed to the exact alias,
unknown/missing decision safety, no widening, cancellation, lower-tier classifier
failure defaults, malicious decision metadata isolation, unsupported input/override
rejection, target permission and model guardrail rejection, quota exhaustion and
stale/unknown policy, subscription quota bypass, original eight criteria and CAPABLE
wording, original solver assignments, specialist fallback preservation, callback
loader and missing-callback local failure, real ProxyLogging acompletion path, and
real Router ordered fallback attempts using fake HTTP for all five capabilities.

Intentional differences: no built-in Auto Router; classified and direct family
aliases use root-only fallback lists to avoid nested reordering. Free family chains
insert Luna before the original paid sequence; direct higher tiers use paid-capable
family primary/backup/emergency. Missing callback has no paid fallback. Expired
quota is unknown. Client routing/retry overrides on jev are rejected; model-level
guardrails on execution targets fail closed. This is not a spending limit.

## Independent review history

Runtime reviewer `/root/callback_runtime_review` first found real acompletion type
rejection and user_config/router_settings_override bypass. Re-review found
model_group_retry_policy could override num_retries. Spec reviewer
`/root/callback_spec_review` found direct family aliases still followed recursive
fallbacks and skipped paid-efficient entries. Each issue was reproduced RED, then
fixed GREEN. No initial failed review is counted as acceptance.

Final runtime reviewer verdict (verbatim):
> Clean for the documented offline publication scope. No remaining medium/high
> findings identified in the current runtime changes.
> Confirmed previous fixes, request-local semantic routing, authorization/guardrail
> rejection, and ordered fallbacks for classified and direct family routes.
> Independently reran the combined suite: 21 tests passed.

Final spec reviewer verdict (verbatim):
> Clean re-review — no remaining medium/high findings in the current tree.
> Confirmed the direct-alias fix covers all 20 family aliases and eight free backup
> aliases, preserving the complete configured fallback order.
> Confirmed model_group_retry_policy overrides are rejected on jev.
> Confirmed target model guardrails fail closed and have regression coverage.
> Independently reran all three suites: 21 tests passed, including real Router
> failure traces through the callback.

Both final reviews concern the same runtime/test changes; final source registration
and prose status reconciliation followed. They are independent offline acceptance,
not certification of provider availability, subscription authentication, streaming,
classifier quality, deployment or spending limits. No OAuth/login work was done.

## Reviewed file fingerprints

SHA-256 of LF-normalized UTF-8 contents (Git working files normalize line endings):

- `router/jev_router.py`: `1c6ee3c7a4da16140ba5eee94ce28b993e9c77facce11ecfe776773b6560ef8c`
- `router/jev_classifier.py`: `2da01e9525679c77e418841448b16ea2194ad0dd77c73ab7a6cac1c179312aa9`
- `router/openrouter_quota_guard.py`: `0c09e0eb6cfba7d098548d7d01e59d172f4620ee15e96a2b271162ef611e050d`
- `router/config.yaml`: `f03f50cab4ca7930abea24f659ae9635e1f06868cf8c11d077b424df10743921`
- `requirements.txt`: `649bc774b8918b916cddd000b43aa542edc768d748b08b20e52fa3d280d2c3c3`
- `tools/test_callback_routing.py`: `6e5d2c8a1472bd08df6ee8c90085fdfd75bf8b4eb71cc76b94e835597e0a5027`
- `tools/test_twenty_tiers.py`: `cf824a853beca6e11b364c7c894c6318ac2f0a96f5ca656d0d9b1737887bf45f`
- `tools/test_routing_signal_api.py`: `dd6906ea4c63c24f574f353d467dbd4a5e02b92e9bc38c6250d74bfa070eb337`
