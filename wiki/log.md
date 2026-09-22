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

## [2026-09-22] ingest | Twenty tiers on the main baseline

Preserved and registered the original request and additive scope/branch correction. Verified origin/main at 9f8d97b after fetch; strict cost work remains isolated at 69d7d34. Corrected the empty task branch before edits. Proposed taxonomy, alias mapping, non-escalating failures and operational gaps ingested into wiki. Next: focused failing public-seam checks and narrow implementation; no live provider calls.

## [2026-09-22] RED and partial GREEN | Expanded-tiers compatibility

Renamed task branch to expanded-tiers at user request. No strict-cost code added.
Twenty-choice classifier fake-HTTP test is green. Pinned LiteLLM config validation
fails: maximum eight custom tiers; upstream source confirms the same limit.
Retained new immutable evidence and asked for compatibility direction. Original
failing suite first exposed test setup issues (tokenizer cache and plugin instance),
then reproduced 21 assertions before implementation. After expansion the remaining
failure is the real eight-tier cap, not a test setup issue.

Quota regression failed on sixteen ChatGPT cases because the header hook queried
OpenRouter. Added bypass to both hooks; focused quota test passes. Prepared OAuth
container mount/login instructions; no deployment host or container changes made.

## [2026-09-22] stop-condition audit | Not complete

[Immutable audit receipt](../raw/notes/2026-09-22-expanded-tiers-blocked-audit.md) records branch/baseline, exact command outcomes, changed artifacts, two independent NOT CLEAN reviews, and next safe input. py -3 focused test exits 1 (httpx absent); existing virtual environment runs 3 tests with two passes and a real eight-tier validation error. Separate raw YAML regression passes all 46 solver deployments, eight existing mappings/definitions and fallback/settings comparisons. Structural check and git diff --check pass. Restored accidentally re-encoded pre-existing wiki text from baseline, preserving additive entries. No cap bypass, behavior workaround, live action or deployment. Clean-review count zero; goal remains incomplete.

Final audit ingestion: `py -3 tools/check_workspace.py` exit 0, 11 immutable raw hashes/registrations, 15 Markdown files, wiki index coverage and 12 Python syntax checks. Imported raw hashes remain unchanged. No runtime change or passing twenty-tier integration is claimed.

## [2026-09-22] ingest | Resume with five-tier architecture

Registered revised user contract before runtime/test edits. Investigating installed 1.99.0 classifier-to-plugin handoff with a real public-hook probe; YAML remains untouched pending compatibility. Independent source audit started. No cap patch or OAuth work.

## [2026-09-22] RED | Five-tier plugin combination rejected

Real public-hook fixture exited 1 with three configuration errors before classification:
`plugins cannot be combined with tier_definitions`. Hypothesis: installed 1.99.0
has a separate explicit custom-tier/plugin restriction, in addition to missing
classifier-signal propagation. Retain that rejection as an API characterization
case; investigate handoff independently with supported built-in tiers. This does
not substitute built-in tiers for the accepted five-tier design or remove its
acceptance blocker. No working YAML or LiteLLM core change.

## [2026-09-22] RED | Restore original CAPABLE wording

Focused public-classifier test against immutable raw classifier exits 1: original
GENERAL_CAPABLE criteria gained upward-deferral text. Hypothesis: restore all
original eight criteria and the exact original CAPABLE instruction, leaving new
criteria additive. This repairs the expressly requested wording regression but
does not prove unchanged model decisions or solve the five-tier API blockers.

## [2026-09-22] RED | Reference import generated raw bytecode

Structural check reported unregistered raw/__pycache__/jev_classifier.cpython-312.pyc.
Hypothesis: importing immutable reference source in the new wording regression
created disposable bytecode. Disable bytecode writing during that reference import
and remove only the exact generated file; preserve every raw source and hash.
The combined shell continued to diff --check, so its aggregate exit 0 must not
be reported as a workspace-check pass. Rerun the structural check separately.

## [2026-09-22] STOP | Five-tier compatibility investigation

[Immutable receipt](../raw/notes/2026-09-22-five-tier-api-audit.md) records both API blockers, exact outputs, installed-source hashes, changed artifacts and two independent STOP reviews. Four real-hook characterization tests pass by proving incompatibility; zero clean implementation reviews. Restored original eight criterion texts and CAPABLE instruction after focused RED; focused regression GREEN. Default Python lacks httpx; existing venv executes broader test suite with three passes and unchanged twenty-tier YAML failure. No YAML change, OAuth work, core patch, validation bypass or live call. Revised five-tier design remains unimplemented under explicit stop condition.

Final API-audit ingestion: `py -3 tools/check_workspace.py` exit 0, 13 raw hashes/registrations, 15 Markdown files, wiki index coverage, 13 Python syntax checks. These structural checks do not certify the blocked architecture.

## [2026-09-22] research | Verify supported path before authorized push

Registered user continuation/push authorization. Current upstream main still contains both blockers. Independent research checks releases and tests; coordinator inspected the existing supported proxy callback rewrite seam. Preparing a concrete alternative instead of making unapproved core changes. No push of the failing draft.

## [2026-09-22] research outcome | No supported upgrade found

Preserved and registered [release research](../raw/notes/2026-09-22-upstream-five-tier-research.md): v1.102.0 commit 95293834e833b2d2979f87d1bd2a5be45db6728a and pinned current main retain both blockers; upstream tests assert rejection. Direct API checks supersede stale web-cache versions. Prepared and independently reviewed the supported callback proposal. Review identified changed fallback-root risk and required a baseline failure trace plus explicit preservation. User architecture choice is pending via async question. No runtime edits, dependency installs or push in this turn; existing failing draft is not a satisfactory publishable result.

## [2026-09-22] document | Free-first subscription escalation

Captured the latest user correction and documentation request in a new immutable
[design note](../raw/notes/2026-09-22-free-first-escalation-design.md), registered its
hash, and rewrote the existing [callback design page](semantic-routing-alternative.md)
as the current proposed architecture. Included Mermaid flow, roles, all twenty
semantic classes, existing free primary assignments, full proposed model roster,
quota behavior, specialist boundaries, examples, open implementation decisions and
required tests/reviews. R006 explicitly supersedes no-failure escalation and the
built-in-tier integration proposal; the ChatGPT-as-CAPABLE-primary suggestion is
discarded. Added current-versus-historical notices to architecture, routing,
classifier, quota, operations, evaluation and open questions; updated the index.

Documentation only: runtime/config/test files and all existing raw bytes were
left unchanged in this turn. No OAuth, provider requests, deployment, push or
implementation acceptance claim. Next: resolve detailed fallback/quota policy
and implement/test the proposed callback in separately tracked execution. Offline
structural and documentation diff checks follow.

Verification: `py -3 tools/check_workspace.py` exit 0 (16 raw hashes/registrations, 16 Markdown files, wiki coverage, 13 Python syntax checks). Documentation `git diff --check` exit 0. No runtime tests or live checks were needed or run for this documentation-only turn.

## [2026-09-22] ingest | Implement and publish callback routing

Registered explicit user implementation/commit/push authorization and proposed narrow defaults before behavior changes. All prior raw records preserved; expanded-tiers remains based on main. Runtime work and review now resumes on the supported callback architecture, not Auto Router.

## [2026-09-22] implementation | Free-first callback routing

Implemented one request-local semantic decision, four-candidate family filter,
quota-after-classification, target/fallback authorization, fail-closed target
model guardrails and local missing-callback provider. Replaced invalid twenty-tier
Auto Router config. Preserved original solver deployments and eight criteria;
inserted Luna before paid fallbacks, with direct higher aliases falling back to
family paid-capable. Direct family aliases also receive root-only fallback lists.
Specialist lists remain unchanged. Unknown/stale quota uses configured fail-open
or fail-closed behavior. Dependencies pinned for offline reproducibility.

Focused RED/GREEN checks covered callback absence, rejected overrides, permission,
quota exhaustion/staleness and config. Initial independent reviews found real
`acompletion` rejection, user_config/retry override gaps and recursive direct-alias
fallback reordering. Each was reproduced with a failing regression and fixed.
Latest combined suites: 21 tests pass; all twenty concurrent outcomes and fake-HTTP
Router traces pass. Two final clean review verdicts are still pending. No live
provider, OAuth, deployment, commit or push yet. Existing raw source bytes preserved.

## [2026-09-22] acceptance | Two clean independent reviews

Registered [acceptance receipt](../raw/notes/2026-09-22-callback-acceptance.md),
including failed-review findings/fixes, two final independent clean verdicts,
21-test results and reviewed runtime/test fingerprints. Reconciled current wiki
status to verified offline. No live provider/OAuth/deployment evidence is claimed.
Next: final integrity/diff checks, commit and push the authorized expanded-tiers
branch; verify remote commit identity. Strict cost branch remains unchanged.

Final pre-publication checks: workspace integrity passed with 18 raw hashes/registrations, 16 Markdown files and 15 Python syntax checks; diff whitespace check passed. Remote main matches base 9f8d97b; expanded-tiers does not yet exist remotely. No secrets, ignored auth files or environment files are included. The following commit publishes only this branch, without merge or deployment.
