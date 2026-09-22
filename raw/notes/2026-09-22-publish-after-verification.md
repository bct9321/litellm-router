# Continue and publish authorization — 2026-09-22

User: "do it and push tthe branch when satisifed."
Refers to the preceding plan: investigate a supported LiteLLM version/API; implement
if supported; otherwise present a concrete alternative or narrow compatibility
proposal; verify all semantic paths and obtain two clean independent reviews.

Authorization covers publishing expanded-tiers to configured origin after a
verified result. It does not waive the earlier no-core-tier-cap-patch restriction,
authorize deployment/OAuth, or approve an unannounced architectural substitution.
Existing dirty work is task-owned; baseline remains origin/main 9f8d97b.

Current live upstream source inspected 2026-09-22 still rejects plugins combined
with custom tier definitions and accepts only string/None custom classifier results:
- https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/router_strategy/complexity_router/config.py
- https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/router_strategy/complexity_router/complexity_router.py
- https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/types/router.py
Independent release/source research is in progress; no assertion of an exhaustive
search of all releases is made.

Concrete proposed alternative: retain the semantic decision and alias registry,
but perform deterministic selection in a supported proxy CustomLogger pre-call
callback for the jev entrypoint instead of the built-in complexity Auto Router.
Installed proxy/utils.py 1732-1741 invokes and accepts callback-modified request
data; the existing quota callback already uses this model-alias rewrite seam.
This is a proposed design change requiring user choice, not implemented behavior.
