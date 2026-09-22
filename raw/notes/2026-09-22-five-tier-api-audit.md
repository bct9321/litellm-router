# Five-tier API compatibility audit — 2026-09-22

Status: STOP condition confirmed, requested architecture not implemented.
Branch expanded-tiers; HEAD and origin/main both
9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc. Installed LiteLLM 1.99.0.
This supersedes the earlier eight-tier-limit blocker for the revised design:
five capability tiers fit the count limit, but two distinct interfaces block use.

## Installed-source evidence

All source paths below are relative to .venv312/Lib/site-packages/litellm/.

1. router_strategy/complexity_router/config.py:973-992 lists plugins as a
   tier_definitions conflict (line 982); 1053-1055 rejects it. Actual message:
   `plugins cannot be combined with tier_definitions: these features rely on the
   built-in tier severity order, which a custom tier set does not define`.
   This rejects exactly five custom capability tiers with plugins, not their count.
2. types/router.py:968-979 declares ClassifierPlugin.classify -> str | None.
   router_strategy/complexity_router/complexity_router.py:1245-1256 creates a
   classifier-local RoutingContext. Lines 1265-1269 reject structured dictionary
   verdicts; 1281-1285 retain only tier plus generated diagnostic text. The
   classifier's top-level metadata writes and signals are not propagated.
   Lines 1541-1546 create a fresh RoutingContext from original request kwargs for
   the subsequent filtering plugin, with signals empty.
3. Router-level plugins are not a substitute: router.py:11698-11706 runs them
   before the Auto Router strategy; 11579-11582 gives them concrete provider model
   candidates rather than the selected capability tier's semantic alias pool.
4. Complexity-router plugin filtering (1547-1557) does not enforce subset output.
   A future family filter must explicitly narrow its incoming candidates and
   validate failure behavior; installed code cannot be cited as no-widening proof.

Precise missing interfaces: (a) supported coexistence of custom tier definitions
and post-classification routing plugins; (b) a structured classifier result or
explicit context propagation carrying both tier and server-generated request-scoped
family signals into that filtering stage. Adding (b) alone will not fix (a).
No private nested-metadata mutation, message mutation, shared-instance state,
ContextVar workaround, core edits or validation bypass were applied.
No installed upstream test suite for these APIs was found; runnable local probes
exercise the real public async_pre_routing_hook and real installed validation.

## Reproduction and verification

- Initial five-tier real-hook fixture: exit 1, three errors, all rejected at
  configuration validation before classification. Logged hypothesis and separated
  the two prerequisites without changing working YAML.
- `.venv312\Scripts\python.exe tools/test_routing_signal_api.py`: exit 0,
  four compatibility characterization tests. They demonstrate the custom-tier/plugin
  rejection; classifier metadata/signals absent downstream on a supported built-in
  path; structured verdict rejected and fallback used; and a positive control where
  preexisting metadata narrows the built-in pool to coding-expert.
  The built-in fixture is diagnostic only, not a replacement for the requested
  five-tier architecture. Socket connections are forbidden during hook execution.
- `.venv312\Scripts\python.exe -m unittest tools.test_twenty_tiers.TwentyTierTests.test_original_eight_criteria_and_capable_wording_are_preserved`:
  first exit 1 for changed original criteria, then exit 0 after restoring the exact
  original eight criteria and original CAPABLE instruction from raw source.
  Fake Decisions HTTP observes both public classifiers' outgoing payloads. This
  proves preserved wording, not live model classification equivalence.
- `py -3 tools/test_twenty_tiers.py`: exit 1, missing httpx in default interpreter.
- `.venv312\Scripts\python.exe tools/test_twenty_tiers.py`: exit 1,
  four tests, three pass and one errors on the unchanged older twenty-tier YAML.
  Working YAML was deliberately not rewritten before resolving API compatibility.
- Workspace check initially found a generated raw/__pycache__ bytecode file from
  reference import. Disabled bytecode writing for that import and removed only
  that generated file. Source bytes remain unchanged. Repeated focused regression
  and `py -3 tools/check_workspace.py`: exits 0, 12 raw registrations, 15 Markdown
  files, 13 Python syntax checks before ingestion of this receipt.
- `git -c safe.directory=C:/Users/Brandon/workspaces/litellm diff --check`: exit 0.
  Final receipt ingestion check is recorded separately in wiki/log.md.

## Independent reviews

signal_api_review: STOP, not a clean implementation review. Independently verified
missing handoff and custom-tier/plugin conflict; qualified its initial statement
that five tiers alone are supported. No files changed or provider calls.

five_tier_independent_review: STOP, not a clean implementation review. Independently
verified both blockers, ruled out Router-level plugin timing/candidate semantics,
and reran all four real-hook compatibility tests, exit 0. No files changed.

Consecutive clean implementation-review count: zero. The passing characterization
suite establishes incompatibility; it must not be reported as routing acceptance.

## Changes and limits

New request/audit raw records, source register/hash additions, affected wiki updates,
new tools/test_routing_signal_api.py, focused wording regression in
 tools/test_twenty_tiers.py, and restoration in router/jev_classifier.py.
No router/config.yaml changes in this resumed investigation. No OAuth login,
container operation, secret access, live inference, billing, provider registry
change, publishing, merge, core patch or eight-tier-limit modification.
Previous uncommitted draft remains incomplete and not deployable. Do not count
all twenty semantic routing assertions, unknown-input/failure tests, concurrent
signal isolation or no-widening acceptance as done; they depend on missing APIs.

Next safe input: identify a LiteLLM build exposing both supported interfaces, or
explicitly authorize a separately scoped compatibility investigation covering both
interfaces. The user's permitted possible signal-only compatibility change is
insufficient by itself. Do not infer permission to patch the tier cap or add
custom-tier/plugin coexistence from the request.

## Source and artifact hashes at audit

- .venv312/Lib/site-packages/litellm/types/router.py: e4d0232706568b7bc082efd12e1f2c4fcbcab37c54fa1d7a181fb5eb8baa3741

- .venv312/Lib/site-packages/litellm/router_strategy/complexity_router/config.py: f0396c4c391bf96a590ac61da57ed81e23b630ef036724420ff784b332dcec59

- .venv312/Lib/site-packages/litellm/router_strategy/complexity_router/complexity_router.py: 4636aacebae82683361f7e1502fa6a6cd3591190cdb82ba6867c08dcc3e798e2

- .venv312/Lib/site-packages/litellm/router.py: a74acc9a1c8b75de4956fd721543c5930faac8fb5d2e9b8dbb0e052f647af16a

- tools/test_routing_signal_api.py: dd6906ea4c63c24f574f353d467dbd4a5e02b92e9bc38c6250d74bfa070eb337

- tools/test_twenty_tiers.py: 53b81d62e61fe67db036fe29ba08b51b61fa57b2cfae4db9dd3c933b7ac7aa8b

- router/jev_classifier.py: de60c8cc1ddfdb8aa3652fab4a7c1d950a89e9a2f1d3544e3241f2ac8b8565b2
