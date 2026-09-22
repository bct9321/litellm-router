# Jev classification

Current proposed contract (2026-09-22): the [free-first callback design](semantic-routing-alternative.md) uses one family-plus-capability decision and twenty semantic classes. Provider/auth/cost state does not determine semantics. Lower-tier wording has been restored in the draft; structured callback integration and classification quality remain unverified. Historical interface investigations follow.

Status: observed source behavior, 2026-09-20.
Source: [jev_classifier.py](../raw/jev_classifier.py), especially
`_classification_transcript`, `OpenRouterJevClassifier.classify`, and `FAIL_TIER`.

## Input and choice

The plugin accepts object or mapping contexts using `structured_messages` or
`raw_messages`. It extracts text, keeps system/user/assistant messages, removes
empty messages, and discards user messages matching runtime metadata markers.
Tool-role messages and image blocks are not included as image inputs.

The transcript includes the newest system/profile message plus the last eight
non-system messages by default; each message is truncated to 3,000 characters.
This is a per-message limit, not a total token budget. Metadata matching can also
drop genuine user requests containing phrases such as `chat_id`.

The payload uses `state.records` and question `tier`, sent to
`https://openrouter.ai/api/alpha/decisions`, with default model `typesafe/jev-1.13`.
The response reads `answers.tier.choice`, accepts a wrapped value/choice/label,
uppercases it, and returns it only if it belongs to the eight allowed tiers.

## Classification policy

- CODING covers requested implementation, software debugging, tests, or repository
  edits; it takes precedence over REASONING when code work is requested.
- AGENTIC covers primary orchestration, delegation, tools, and autonomous workflows.
- REASONING covers analysis, planning, architecture, and review without primary implementation.
- GENERAL covers writing, explanation, synthesis, and remaining general work.
- EFFICIENT means bounded, low-ambiguity work. CAPABLE covers uncertainty, difficult
  debugging, broad changes, branching workflows, and high rework risk.

Hermes profile labels are routing evidence rather than fixed overrides. Mixed
orchestration/implementation intent is not given an exhaustive precedence rule.

## Failures and configuration

Missing provider key, empty usable transcript, handled HTTP/network/timeout errors,
invalid response shape, or invalid choice lead to `JEV_FAIL_TIER`, default
`GENERAL_CAPABLE`. An unsupported fallback tier is reset to that default.
Transcript construction occurs before the API-call exception handler, so this is
not a guarantee that every malformed input or environment value fails safely.

| Variable | Imported default |
|---|---|
| `JEV_MODEL` | `typesafe/jev-1.13` |
| `JEV_TIMEOUT_SECONDS` | `5.0` |
| `JEV_MAX_MESSAGES` | `8` |
| `JEV_MAX_CHARS_PER_MESSAGE` | `3000` |
| `JEV_FAIL_TIER` | `GENERAL_CAPABLE` |
| `JEV_LOG_RAW_ANSWER` | `true` |
| `JEV_LOG_TIMING` | `true` |

Fallback tier selection is distinct from the proxy's paid fallback chains.
Classification, HTTP-error, and timing logs may contain provider data; review
captured output before retaining it as public evidence.

Related: [routing](routing.md), [evaluation differences](evaluation.md), [open questions](open-questions.md).

## Proposed twenty-class expansion — 2026-09-22

[Accepted scope](../raw/notes/2026-09-22-twenty-tier-scope.md): retain one tier decision, expand its choices and criteria to twenty semantic classes. Describe ADVANCED as hard bounded work, EXPERT as deep systemic work, FRONTIER as exceptional novel/ambiguous work. Preserve family precedence and existing lower-tier failure defaults; failure overrides cannot promote into the three new levels.

## Audit correction

[Both independent reviews](../raw/notes/2026-09-22-expanded-tiers-blocked-audit.md) found the draft changed CAPABLE instructions, contrary to the accepted preservation requirement. Twenty fake choices being accepted is only output-schema evidence. Existing-semantics and failure-path verification remain incomplete; no finished routing claim is made.

## Revised structured decision prerequisite

[Revised contract](../raw/notes/2026-09-22-five-tier-routing-request.md): one family-plus-capability decision; return capability to LiteLLM and publish family using a supported request-scoped field. Investigate real hook propagation; do not rely on shared mutable state or alter the tier cap. Restore baseline CAPABLE wording.

## Five-tier handoff audit and wording repair

[Evidence](../raw/notes/2026-09-22-five-tier-api-audit.md): the required supported handoff is absent. Real-hook probes demonstrate lost classifier metadata/signals and rejected structured returns. Original eight criteria and CAPABLE instruction have been restored and compared through fake Decisions HTTP; live classification equivalence is not established. No five-tier implementation is claimed.
