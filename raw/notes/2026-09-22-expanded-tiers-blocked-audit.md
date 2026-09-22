# Expanded-tiers failed-state audit — 2026-09-22

Origin: active user goal continuation, current commands and two independent
read-only adversarial reviews. This is a partial-work receipt, not completion.

## Accepted stop condition and baseline

User requires twenty semantic tiers, preservation of the existing eight semantics,
deployments and ordinary fallbacks, no failure escalation, real pinned LiteLLM
configuration validation, two consecutive clean reviews and an offline check.
User explicitly requires stopping when required LiteLLM APIs cannot support
defensible verification or source evidence conflicts. No compatibility patch has
been authorized or applied. A prior question about allowing one was answered by
requesting evidence, not by approving a workaround.

Current branch: expanded-tiers. HEAD and fetched origin/main both equal
9f8d97b5ada521e3e9c356dfc2b305fc5c2333dc. Strict cost controls remain on
codex/cost-aware-router at 69d7d34a8162567e714917c80f426eae256ba75b. All current
task edits are uncommitted; no publication, merge or deployment occurred.

## Commands and observed results

- `py -3 tools/test_twenty_tiers.py`: exit 1, `ModuleNotFoundError: No module named 'httpx'`.
- `.venv312\Scripts\python.exe tools/test_twenty_tiers.py`: exit 1; ran 3 tests,
  two passed and the configuration test errored. Exact validator message:
  `tier_definitions must define between 2 and 8 tiers, got 20`.
- `py -3 tools/check_workspace.py`: exit 0 before this receipt was ingested;
  `PASS: 10 raw hashes/registrations, 15 Markdown files, wiki index coverage,
  12 Python syntax checks. No API calls.` Final receipt-ingestion check follows
  in wiki/log.md.
- `git -c safe.directory=C:/Users/Brandon/workspaces/litellm diff --check`: exit 0;
  informational CRLF-to-LF notices only.
- Inline Python/YAML regression executed using `.venv312\Scripts\python.exe -`:
  exit 0. Compared parsed raw/config.yaml and router/config.yaml: all 46 original
  non-JEV deployments, eight original tier mappings and descriptions, fallback
  tier, complete router settings/fallback chains, general settings and callback
  settings are equal. This is structural evidence, not unchanged classifier behavior.
- Installed environment metadata: LiteLLM 1.99.0, httpx 0.28.1, PyYAML 6.0.3.

The twenty supplied fake Decisions choices are accepted by the classifier; this
does not test whether a real classifier chooses the right strength. Direct
ChatGPT alias/provider hook inputs bypass quota in the test. The test replaces
the quota helper, so actual proxy propagation and end-to-end provider isolation
remain unproven.

## Independent reviews

Reviewer adversarial_audit: NOT CLEAN. Reviewer independent_audit: NOT CLEAN.
Neither edited files, installed dependencies, read credentials or called providers.
Consecutive clean count: zero. Both found:

1. High: twenty-tier YAML cannot load through LiteLLM 1.99.0's public config seam.
2. Medium or higher: classifier CAPABLE instruction changed from difficult/deep
   work to moderate work with established approaches, with new upward-deferral
   text. This violates the explicit existing-semantics preservation requirement.
3. Medium: retained YAML regression assertions occur after the failing parser
   construction and therefore never run in the test suite. The separate inline
   comparison establishes current equality but does not repair retained coverage.
4. Medium: no timeout/HTTP-error/invalid-answer or failure-tier override tests
   prove that transport failures cannot promote into higher tiers.

The first reviewer additionally identified a scope conflict: top-level jev is
checked for OpenRouter quota before classification and can still be rewritten to
paid-general-capable. Preserving that existing behavior is not the same as
bypassing OpenRouter for every request eventually classified to ChatGPT. Synthetic
response provider metadata in a header-hook test does not prove actual proxy or
streaming metadata propagation. No broad isolation claim is justified.

## Current changed artifacts

- .gitignore
- router/config.yaml
- router/jev_classifier.py
- router/openrouter_quota_guard.py
- tools/test_twenty_tiers.py
- raw/notes/2026-09-22-twenty-tier-request.txt
- raw/notes/2026-09-22-twenty-tier-scope.md
- raw/notes/2026-09-22-tier-limit-evidence.md
- raw/notes/2026-09-22-expanded-tiers-blocked-audit.md
- wiki/index.md, wiki/classifier.md, wiki/decisions.md, wiki/log.md
- wiki/open-questions.md, wiki/operations.md, wiki/quota-guard.md, wiki/routing.md
- wiki/source-manifest.json, wiki/sources.md

Pre-existing wiki text was restored from Git after detecting an accidental
encoding round-trip in earlier append scripts; additive entries remain. Imported
raw bytes and old manifest hashes were not altered.

## Stop and next safe input

No runtime/test workaround is applied after reproducing the explicit stop
condition. Need a supported LiteLLM build/configuration approach that admits twenty
custom tiers, or explicit revised authorization for a version-pinned compatibility
change. Then restore old criteria semantics, separate regression checks, add
failure-path checks and verify real routing before restarting independent reviews.
The definition of done is unchanged and the goal remains incomplete.

OAuth mount/login recipe is prepared in wiki/operations.md only. OAuth tokens,
container persistence, live provider availability, billing, Responses streaming
and model quality were not accessed or verified. The historical DB streaming
issue is not asserted to affect installed 1.99.0.
