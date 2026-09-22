# Twenty-tier JEV scope and evidence — 2026-09-22

Origin: user-supplied Pasted text.txt, preserved separately without modification,
and the subsequent correction: "strict cost controls should be on a branch.
ensure you are working off the right code."

Accepted scope: expand four families to five strengths; maintain semantic aliases;
use the requested initial ChatGPT Luna/Terra/Sol assignments; do not extend normal
fallbacks upward; audit OpenRouter quota isolation; provide OAuth persistence setup.
Keep the existing single Decisions question. Failure must not promote to a higher tier.

Baseline verified after fetching origin: main/origin/main at 9f8d97b.
Strict cost controls remain at codex/cost-aware-router, 69d7d34. The initially empty
codex/jev-twenty-tiers branch was corrected to origin/main before runtime edits.
No strict cost code is part of this change. Existing raw bytes are preserved.

Observed locally: no container definition or host access is supplied in this repo.
Existing ignored runtime environment has LiteLLM 1.99.0; its ChatGPT authenticator
reads CHATGPT_TOKEN_DIR and performs device login via get_access_token(). Do not
retain or print tokens. Container mutation/login and live model availability remain
unverified; provide an explicit container setup recipe instead of claiming deployment.
Requested model IDs are user-selected initial policy, not verified provider access.

External evidence accessed 2026-09-22:
- https://github.com/BerriAI/litellm/issues/28044 reports DB-created ChatGPT streaming
  failure with YAML working in older versions. This does not prove the bug exists
  in installed 1.99.0; retain YAML deployments without asserting current bug status.
- https://github.com/BerriAI/litellm/blob/litellm_internal_staging/litellm/llms/chatgpt/authenticator.py
  corroborates the token-directory environment convention; installed source is the
  version-specific evidence used for the setup recipe.

Public verification seams: Jev classify with fake Decisions HTTP; YAML tier/alias
resolution using pinned LiteLLM; quota pre-call/header hooks with no provider HTTP;
regression equality of existing model deployments and fallback chains against raw.
These do not establish model quality, OAuth login or live streaming compatibility.
