# Workspace bootstrap source note

Date: 2026-09-20. Origin: user request in the workspace bootstrap conversation.

## User direction

Read and ingest all files in `raw/`; organize this LiteLLM router workspace for
GitHub; make the project LLM-wiki-first using Karpathy's design; create `AGENTS.md`,
`README.md`, architecture documentation, and durable decisions and rules.
The user supplied https://github.com/bct9321/litellm-router.git as the destination.

## Bootstrap implementation choices

These are the agent's organizational choices implementing that request, not
historical router decisions supplied by the user:

- Preserve the six original source files byte-for-byte in `raw/`.
- Use `wiki/` for maintained, source-linked synthesis; `wiki/index.md` for navigation
  and `wiki/log.md` for append-only activity history.
- Put editable deployment inputs in `router/` and operator scripts in `tools/`.
  Initially these are exact copies, not a behavior change.
- Record source checksums and destinations in `wiki/source-manifest.json`.
- Use ordinary Markdown, relative links, and Git. LLM ingestion is an explicit
  maintenance workflow, not an installed automatic semantic compiler or stop hook.
- Keep new decisions source-backed, distinguish observed code from validated
  runtime behavior, and record unresolved contradictions rather than invent resolutions.
- Add offline checks and CI for the documentation/source baseline. Live inference
  and deployment are separate tasks because the imported tooling can incur costs.

## Inspected baseline

Only six files under `raw/` existed initially. No Git metadata, dependency lock,
container definition, deployment evidence, or captured benchmark results existed.
The supplied remote returned no refs on 2026-09-20.

## Design reference

Karpathy, [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f),
accessed 2026-09-20. Paraphrase: preserve raw sources, maintain a linked wiki with
an LLM, and give the agent a schema describing ingestion, querying, and maintenance.
Keep a content index and an activity log. This workspace uses that pattern with
additional project-specific provenance and verification rules.
