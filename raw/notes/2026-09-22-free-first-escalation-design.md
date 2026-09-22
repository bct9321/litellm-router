# Free-first subscription escalation documentation — 2026-09-22

Origin: conversation following the upstream compatibility investigation on
expanded-tiers. This additive note preserves the latest user preference and the
architecture the user requested to document. Earlier raw evidence is unchanged.

User correction, verbatim:
"yeah but realistically i dont want to use chatgpt models that often i really want
to use free models as often as possible and escalte to chatgpt on failure or more
complex tasks."

After discussing the model roster, the user asked "whats the architecture look
like". The assistant proposed: JEV for one semantic classification; a small proxy
routing callback to validate family/capability and select a family-specific alias;
LiteLLM for deployment execution and explicit fallbacks. The user then requested
"document this".

## Policy to document

- Keep existing free EFFICIENT and CAPABLE primary solvers across all four families.
- Normal execution: free primary, then free backups, then configured ChatGPT
  subscription fallback, then paid API fallback last.
- Exceptionally complex tasks may select a subscription alias directly:
  ADVANCED -> Luna, EXPERT -> Terra, FRONTIER -> Sol as proposed initial policy.
- One semantic JEV decision contains family (GENERAL, REASONING, AGENTIC, CODING)
  and capability (EFFICIENT, CAPABLE, ADVANCED, EXPERT, FRONTIER). Preserve all
  twenty FAMILY_CAPABILITY semantic classes, independent of model/provider identity.
- Use the proposed supported proxy callback rather than configuring twenty actual
  LiteLLM tiers or relying on the unsupported custom-tier/plugin handoff. Five
  capability levels are application policy, not five built-in Auto Router tiers.
- Quota handling is outside JEV's semantic decision. Exhausted free capacity should
  skip unavailable free solver attempts and use the subscription fallback policy.
- Fast, vision and compression retain specialist routes; extending their fallback
  chains needs separate compatibility verification.

## Explicit supersession and limitations

The user's free-first correction supersedes the earlier no-subscription-on-failure
restriction and the suggestion to make ChatGPT the primary solver for CAPABLE.
Exact original fallback chains cannot remain unchanged while subscription steps
are inserted. Document the intended change; do not claim behavioral equivalence.
The old top-level quota rewrite straight to paid-general-capable conflicts with
subscription-before-paid policy and must be redesigned deliberately in later work.

The callback architecture and model assignments are a proposed implementation of
the preference, now recorded at the user's request. This turn is documentation
only; no runtime change, deployment, OAuth/login, provider call or publication is
performed. Prior conditional authorization to push a verified implementation is
not treated as permission to publish the known failing draft.

Unresolved: exact subscription model for each lower-tier failure; exhaustion/error
criteria and retry limits; fallbacks for direct subscription selections; paid API
opt-in/limits; quota/classifier failure handling; alias naming and proxy access
controls; baseline-versus-target fallback traces; all live model/auth/streaming
and quality evidence. JEV itself uses OpenRouter; free-first solver routing does
not establish that classification costs zero.
