# Jev classification

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
