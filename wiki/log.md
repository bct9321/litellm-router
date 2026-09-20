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
