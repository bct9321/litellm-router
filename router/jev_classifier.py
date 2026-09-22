"""
jev_classifier.py

Single custom LiteLLM Auto Router classifier for:

    Hermes -> LiteLLM -> Jev -> Free OpenRouter Solvers

The classifier chooses:

    1. Capability
       - GENERAL
       - REASONING
       - AGENTIC
       - CODING

    2. Strength
       - EFFICIENT
       - CAPABLE

This gives LiteLLM exactly 8 tiers.

Static/specialized Hermes tasks should bypass this router where appropriate:

    fast        -> fast free model
    vision      -> vision-capable free model
    compression -> long-context free model

Jev only CLASSIFIES the request.
The solver routes are free-first with configured paid fallbacks.
"""

from __future__ import annotations

import os
import asyncio
import math
import json
import uuid
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import httpx

from router.spend_ledger import Ledger, BudgetDenied, usd_nanos
from router.cost_policy import Candidate, candidate_is_eligible, request_charge, decisions_charge, validate_contract, validate_policy, policy_revision


# ============================================================================
# TIERS
# ============================================================================

TIERS = (
    "GENERAL_EFFICIENT",
    "GENERAL_CAPABLE",
    "REASONING_EFFICIENT",
    "REASONING_CAPABLE",
    "AGENTIC_EFFICIENT",
    "AGENTIC_CAPABLE",
    "CODING_EFFICIENT",
    "CODING_CAPABLE",
)


class JevAccounting:
    """Optional strict accounting for a classifier endpoint with a known bound."""
    def __init__(self):
        config_path = os.getenv("COST_ROUTER_CONFIG")
        self.ledger = None
        self.contract = None
        if config_path:
            config = json.loads(Path(config_path).read_text(encoding="utf-8"))
            validate_policy(config)
            self.ledger = Ledger(config["ledger"], config["limits"],
                                 billing_scope=config.get("billing_scope", "router-only"),
                                 coverage_mode=config.get("coverage_mode", "router-only"),
                                 policy_revision=policy_revision(config))
            self.contract = config.get("classifier")
            if not config.get("routes", {}).get("jev", {}).get("candidates"):
                raise ValueError("Strict classifier requires routes.jev candidates")
            if not self.contract:
                raise ValueError("Cost-aware mode requires a bounded classifier contract")
            validate_contract(self.contract, surface='decisions')
            if not isinstance(self.contract.get('provider_model'), str) or not self.contract['provider_model']:
                raise ValueError('Strict classifier requires a contracted provider model')
            self.endpoint = self.contract['origin'].rstrip('/') + self.contract['path']

    def reserve(self, request_id=None, request_payload=None):
        if not self.ledger:
            return None
        attempt = str(uuid.uuid4())
        if not request_id:
            raise BudgetDenied('Strict classifier requires server logical request identity')
        logical_request = request_id
        estimate, bound = decisions_charge(self.contract, request_payload)
        self.ledger.reserve(attempt, logical_request, self.contract["canonical"], "jev",
                            self.contract.get("deployment", "jev"), bound, estimate,
                            kind="classifier", entry_alias="jev", provider_model=request_payload["model"],
                            contract_revision=self.contract["revision"])
        return attempt

    def settle(self, attempt, response=None):
        if not attempt:
            return
        cost = None
        if response is not None:
            try:
                usage = response.json().get("usage") or {}
                cost = usd_nanos(usage.get("cost"))
            except (ValueError, AttributeError, TypeError):
                pass
        self.ledger.settle(attempt, attempt + ":classifier:" + str(cost), cost,
                           "provider-reported" if cost is not None else "unknown")


# ============================================================================
# FALLBACK
# ============================================================================

FAIL_TIER = os.getenv(
    "JEV_FAIL_TIER",
    "GENERAL_CAPABLE",
)

if FAIL_TIER not in TIERS:
    FAIL_TIER = "GENERAL_CAPABLE"


# ============================================================================
# FILTERS
# ============================================================================

# ============================================================================
# MESSAGE NORMALIZATION
# ============================================================================

def _content_to_text(content: Any) -> str:
    """
    Convert OpenAI/LiteLLM message content into plain text.
    """

    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, Mapping):
        text = (
            content.get("text")
            or content.get("content")
        )

        if isinstance(text, str):
            return text

        return str(content)

    if isinstance(content, Sequence) and not isinstance(
        content,
        (str, bytes, bytearray),
    ):
        parts: list[str] = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)

            elif isinstance(block, Mapping):
                text = (
                    block.get("text")
                    or block.get("content")
                )

                if isinstance(text, str):
                    parts.append(text)

        return "\n".join(parts)

    return str(content)


def _extract_messages(
    context: Any,
) -> list[dict[str, Any]]:
    """
    Extract messages from the LiteLLM classifier context.

    Supports:

        context.structured_messages
        context.raw_messages

    plus Mapping equivalents.
    """

    messages = getattr(
        context,
        "structured_messages",
        None,
    )

    if messages is None:
        messages = getattr(
            context,
            "raw_messages",
            None,
        )

    if messages is None and isinstance(
        context,
        Mapping,
    ):
        messages = (
            context.get("structured_messages")
            or context.get("raw_messages")
        )

    if not messages:
        return []

    result: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, Mapping):
            result.append(dict(message))

        else:
            result.append(
                {
                    "role": getattr(
                        message,
                        "role",
                        "unknown",
                    ),
                    "content": getattr(
                        message,
                        "content",
                        "",
                    ),
                }
            )

    return result


# ============================================================================
# BUILD CLASSIFICATION TRANSCRIPT
# ============================================================================

def _classification_transcript(
    context: Any,
) -> str:
    """
    Build the transcript Jev sees.

    Important:

    - Preserve the newest Hermes system/profile prompt.
    - Keep recent conversation context.
    - Remove obvious runtime metadata.
    - Limit individual message size.
    """

    max_messages = int(
        os.getenv(
            "JEV_MAX_MESSAGES",
            "8",
        )
    )

    max_chars = int(
        os.getenv(
            "JEV_MAX_CHARS_PER_MESSAGE",
            "3000",
        )
    )

    if max_messages <= 0 or max_chars <= 0:
        raise ValueError("Transcript limits must be positive")

    useful: list[tuple[str, str]] = []

    for message in _extract_messages(context):
        role = str(
            message.get(
                "role",
                "unknown",
            )
        ).lower()

        if role not in {
            "system",
            "user",
            "assistant",
        }:
            continue

        text = _content_to_text(
            message.get(
                "content",
                "",
            )
        ).strip()

        if not text:
            continue

        # User text is not a reliable metadata discriminator. Keep it even when
        # it discusses runtime fields; tool-role records are excluded above.

        if len(text) > max_chars:
            text = (
                text[:max_chars]
                + "\n[truncated for routing]"
            )

        useful.append(
            (
                role,
                text,
            )
        )

    if not useful:
        return ""

    # ------------------------------------------------------------------------
    # Preserve Hermes profile identity
    # ------------------------------------------------------------------------

    system_messages = [
        item
        for item in useful
        if item[0] == "system"
    ]

    conversation_messages = [
        item
        for item in useful
        if item[0] != "system"
    ]

    selected: list[tuple[str, str]] = []

    # Always preserve newest system/profile prompt.
    if system_messages:
        selected.extend(
            system_messages[-1:]
        )

    # Then include recent conversation.
    selected.extend(
        conversation_messages[-max_messages:]
    )

    return "\n\n".join(
        f"{role.upper()}:\n{text}"
        for role, text in selected
    )


# ============================================================================
# JEV CLASSIFIER
# ============================================================================

class OpenRouterJevClassifier:
    """
    Custom LiteLLM Auto Router classifier backed by OpenRouter Jev.

    Returns exactly one of the configured LiteLLM tier names.
    """

    def __init__(self) -> None:

        # Pin a known Decisions-compatible Jev model.
        #
        # Can be overridden:
        #
        #   JEV_MODEL=typesafe/...
        #
        self.model = os.getenv(
            "JEV_MODEL",
            "typesafe/jev-1.13",
        )

        self.timeout = float(
            os.getenv(
                "JEV_TIMEOUT_SECONDS",
                "5.0",
            )
        )
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("JEV_TIMEOUT_SECONDS must be finite and positive")
        self.accounting = JevAccounting()
        if self.accounting.contract:
            self.model = self.accounting.contract["provider_model"]
        self.cost_config = None
        config_path = os.getenv("COST_ROUTER_CONFIG")
        if config_path:
            self.cost_config = json.loads(Path(config_path).read_text(encoding="utf-8"))

        # Raw answer logging.
        #
        # Disable later:
        #
        #   JEV_LOG_RAW_ANSWER=false
        #
        self.log_raw_answer = (
            os.getenv(
                "JEV_LOG_RAW_ANSWER",
                "true",
            ).lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        # Timing logging.
        #
        # Disable with:
        #
        #   JEV_LOG_TIMING=false
        #
        self.log_timing = (
            os.getenv(
                "JEV_LOG_TIMING",
                "true",
            ).lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

    # ========================================================================
    # CLASSIFY
    # ========================================================================

    async def classify(
        self,
        context: Any,
        *,
        diagnostics: dict | None = None,
    ) -> str:

        if diagnostics is None:
            diagnostics = {}
        diagnostics.update(ok=False, cost=None, cost_kind='unknown', prediction=None)

        classify_start = time.perf_counter()
        attempt = None
        strict_model_selection = bool(self.cost_config)

        # --------------------------------------------------------------------
        # OpenRouter API key
        # --------------------------------------------------------------------

        api_key = os.getenv(
            "OPENROUTER_API_KEY"
        )

        if not api_key:

            print(
                "[JEV ROUTER] OPENROUTER_API_KEY missing",
                flush=True,
            )

            print(
                f"[JEV ROUTER] using fallback tier={self._fallback_choice(context, '')}",
                flush=True,
            )

            if self.log_timing:
                total_latency = (
                    time.perf_counter()
                    - classify_start
                )

                print(
                    (
                        "[JEV ROUTER] "
                        f"total_classifier_latency={total_latency:.3f}s "
                        "result=FALLBACK "
                        "reason=missing_api_key"
                    ),
                    flush=True,
                )

            return self._fallback_choice(context, '')

        # --------------------------------------------------------------------
        # Build transcript
        # --------------------------------------------------------------------

        try:
            transcript = _classification_transcript(context)
        except (ValueError, TypeError, AttributeError):
            print("[JEV ROUTER] invalid transcript input/configuration", flush=True)
            return self._fallback_choice(context, '')

        if not transcript:

            print(
                "[JEV ROUTER] no usable transcript",
                flush=True,
            )

            fallback = self._fallback_choice(context, transcript)
            print(f"[JEV ROUTER] using fallback tier={fallback}", flush=True)

            if self.log_timing:
                total_latency = (
                    time.perf_counter()
                    - classify_start
                )

                print(
                    (
                        "[JEV ROUTER] "
                        f"total_classifier_latency={total_latency:.3f}s "
                        "result=FALLBACK "
                        "reason=no_transcript"
                    ),
                    flush=True,
                )

            return fallback

        # ====================================================================
        # JEV DECISION REQUEST
        # ====================================================================

        eligible_models = self._eligible_models(context, transcript)
        # A classifier-only bounded contract preserves the legacy tier API;
        # strict model choice activates when the policy supplies model routes.
        if strict_model_selection and not eligible_models:
            raise BudgetDenied('Strict Jev mode has no eligible priced/capability-compatible model')

        payload = {

            "model": self.model,

            # ----------------------------------------------------------------
            # STATE
            # ----------------------------------------------------------------

            "state": {

                "description": (
                    "Route a Hermes AI-agent request to exactly one FREE solver tier. "

                    "First determine CAPABILITY. "

                    "CODING applies when the requested work includes implementation, "
                    "writing or modifying code, repository edits, software debugging, "
                    "tests, TDD, refactoring, terminal engineering, or fixing a software defect. "
                    "If code must be changed or produced, CODING takes precedence over REASONING. "

                    "AGENTIC applies when the primary work is tool selection, MCP routing, "
                    "orchestration, delegation, Kanban decomposition, multi-agent coordination, "
                    "or executing a multi-step autonomous workflow. "

                    "REASONING applies to planning, architecture, design review, analysis, "
                    "tradeoffs, diagnosis, or difficult decisions when implementation or code "
                    "changes are NOT the primary requested output. "

                    "GENERAL applies to conversation, writing, summarization, research synthesis, "
                    "explanation, and miscellaneous tasks that do not clearly belong to CODING, "
                    "AGENTIC, or REASONING. "

                    "Then determine STRENGTH: EFFICIENT or CAPABLE. "

                    "Use the Hermes system/profile prompt as strong routing evidence. "

                    "Worker generally implies CODING for software-engineering work. "
                    "Planner generally implies REASONING. "
                    "Reviewer generally implies REASONING. "
                    "Orchestrator generally implies AGENTIC. "
                    "Default and Researcher generally imply GENERAL unless the actual request "
                    "clearly belongs to another capability."
                ),

                "records": [
                    {
                        "id": "request",
                        "record": transcript,
                    }
                ],
            },

            # ----------------------------------------------------------------
            # QUESTION
            # ----------------------------------------------------------------

            "questions": {

                "tier": {

                    "type": "choice",

                    "instructions": (
                        "Choose exactly one solver tier. "

                        "Choose the capability before choosing strength. "

                        "CODING has precedence over REASONING whenever implementation, "
                        "code modification, software debugging, repository editing, tests, "
                        "TDD, refactoring, or terminal engineering is requested. "

                        "AGENTIC should be used when the primary work involves orchestration, "
                        "tool use, MCP selection, delegation, multi-agent coordination, "
                        "Kanban decomposition, or autonomous workflow execution. "

                        "REASONING should be used when the primary output is architecture, "
                        "planning, review, analysis, diagnosis, or decision-making and "
                        "substantial implementation is not requested. "

                        "GENERAL should be used when none of those specialist capabilities "
                        "clearly apply. "

                        "After selecting capability, choose EFFICIENT when the smaller/faster "
                        "specialist is highly likely to complete the work correctly with low "
                        "ambiguity and limited blast radius. "

                        "Choose CAPABLE for difficult debugging, deep reasoning, broad blast "
                        "radius, cross-file changes, concurrency or distributed systems, "
                        "unfamiliar systems, repeated failures, architecture plus implementation, "
                        "long branching workflows, high uncertainty, or high rework risk. "

                        "Use the full transcript, especially the Hermes system/profile prompt."
                    ),

                    "criteria": {

                        "GENERAL_EFFICIENT": (
                            "Routine conversation, writing, summarization, explanation, "
                            "research synthesis, or miscellaneous low-ambiguity work."
                        ),

                        "GENERAL_CAPABLE": (
                            "Difficult or ambiguous general-purpose work requiring stronger "
                            "broad capability but which does not clearly belong to coding, "
                            "agentic execution, or dedicated reasoning."
                        ),

                        "REASONING_EFFICIENT": (
                            "Planning, analysis, design, review, diagnosis, or tradeoff "
                            "evaluation with limited ambiguity and no substantial implementation "
                            "or code modification requested."
                        ),

                        "REASONING_CAPABLE": (
                            "Architecture, deep causal analysis, subtle review, major tradeoffs, "
                            "high uncertainty, difficult planning, or difficult diagnosis where "
                            "implementation or code modification is not the primary requested output."
                        ),

                        "AGENTIC_EFFICIENT": (
                            "Short and obvious tool workflows, simple MCP selection, delegation, "
                            "or task decomposition with few branches and easy verification."
                        ),

                        "AGENTIC_CAPABLE": (
                            "Long or branching autonomous workflows, orchestration, uncertain "
                            "tool selection, dependency planning, recovery, multi-agent coordination, "
                            "or complex execution requiring multiple dependent actions."
                        ),

                        "CODING_EFFICIENT": (
                            "Localized and well-specified implementation, obvious software bug fixes, "
                            "small repository edits, tests, TDD, boilerplate, or bounded refactors."
                        ),

                        "CODING_CAPABLE": (
                            "Hard software debugging, cross-file implementation, unfamiliar systems, "
                            "major refactors, concurrency or distributed-system defects, architecture "
                            "plus implementation, repeated failures, or high-blast-radius code changes."
                        ),
                    },
                }
            },
        }

        if strict_model_selection:
            payload['state']['description'] = (
                'Select exactly one model from the server-owned eligible_models list. '
                'Use capability requirements and current remaining budgets; never invent a model or price.'
            )
            payload['state']['eligible_models'] = eligible_models
            payload['questions'] = {'model': {'type': 'choice', 'instructions': 'Choose one eligible model alias.',
                                              'criteria': {row['alias']: row for row in eligible_models}}}

        # ====================================================================
        # CALL OPENROUTER DECISIONS API
        # ====================================================================

        try:

            jev_start = time.perf_counter()

            metadata = context.get('metadata', {}) if isinstance(context, Mapping) else getattr(context, 'metadata', {})
            if strict_model_selection:
                from router.cost_transport import get_request_context
                request_id = get_request_context(metadata)['id']
            else:
                request_id = None
            if self.accounting.contract:
                payload['max_tokens'] = self.accounting.contract['max_output_tokens']
            attempt = self.accounting.reserve(request_id, payload)
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=False, trust_env=False
            ) as client:

                if self.accounting.contract:
                    # Reservation may wait for a database lock past quote expiry.
                    validate_contract(self.accounting.contract, surface='decisions')
                response = await client.post(
                    self.accounting.endpoint if strict_model_selection else os.getenv("JEV_DECISIONS_URL", "https://openrouter.ai/api/alpha/decisions"),

                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },

                    json=payload,
                )
            self.accounting.settle(attempt, response)

            jev_latency = (
                time.perf_counter()
                - jev_start
            )

            if self.log_timing:
                print(
                    (
                        "[JEV ROUTER] "
                        f"jev_api_latency={jev_latency:.3f}s "
                        f"http_status={response.status_code}"
                    ),
                    flush=True,
                )

            # ----------------------------------------------------------------
            # Show actual OpenRouter error response.
            # ----------------------------------------------------------------

            try:
                result = response.json()
                usage = result.get('usage') or {}
                raw_cost = usage.get('cost') if isinstance(usage, Mapping) else None
                if raw_cost is not None and not isinstance(raw_cost, bool):
                    cost = float(raw_cost)
                    if math.isfinite(cost) and cost >= 0:
                        diagnostics.update(cost=cost, cost_kind='provider-reported')
                diagnostics.update(provider_id=result.get('id'), model=result.get('model', self.model))
            except (ValueError, TypeError, AttributeError):
                result = {}

            if response.is_error:

                print(
                    (
                        f"[JEV ROUTER] HTTP {response.status_code}: "
                        f"{response.text}"
                    ),
                    flush=True,
                )

                response.raise_for_status()

            # =================================================================
            # RAW DIAGNOSTICS
            # =================================================================

            answer_key = 'model' if strict_model_selection else 'tier'
            raw_answer = result.get('answers', {}).get(answer_key)

            if self.log_raw_answer:

                print(
                    f"[JEV ROUTER] raw answer={raw_answer}",
                    flush=True,
                )

            # =================================================================
            # EXTRACT CHOICE
            # =================================================================

            answer = (
                result
                .get("answers", {})
                .get(answer_key, {})
            )

            choice = answer.get(
                "choice"
            )

            confidence = answer.get(
                "confidence"
            )

            probabilities = answer.get(
                "probabilities"
            )

            # Some response versions may wrap the choice.
            if isinstance(
                choice,
                Mapping,
            ):

                choice = (
                    choice.get("value")
                    or choice.get("choice")
                    or choice.get("label")
                    or ""
                )

            raw_choice = str(choice or '').strip()
            if strict_model_selection:
                aliases = {row['alias'].upper(): row['alias'] for row in eligible_models}
                choice = aliases.get(raw_choice.upper(), '')
            else:
                choice = raw_choice.upper()

            # =================================================================
            # VALIDATE
            # =================================================================

            current_models = self._eligible_models(context, transcript) if strict_model_selection else []
            valid_choices = {row['alias'] for row in current_models} if strict_model_selection else set(TIERS)
            if choice in valid_choices:

                diagnostics.update(ok=True, prediction=choice)

                total_latency = (
                    time.perf_counter()
                    - classify_start
                )

                print(
                    (
                        "[JEV ROUTER] "
                        f"selected {'model' if strict_model_selection else 'tier'}={choice} "
                        f"confidence={confidence}"
                    ),
                    flush=True,
                )

                if self.log_timing:
                    print(
                        (
                            "[JEV ROUTER] "
                            f"total_classifier_latency={total_latency:.3f}s "
                            f"jev_api_latency={jev_latency:.3f}s "
                            f"local_overhead={max(0.0, total_latency - jev_latency):.3f}s "
                            f"result=SUCCESS "
                            f"{'model' if strict_model_selection else 'tier'}={choice}"
                        ),
                        flush=True,
                    )

                return choice

            print(
                (
                    "[JEV ROUTER] invalid or missing tier "
                    f"returned={choice!r}"
                ),
                flush=True,
            )

            if probabilities:
                print(
                    (
                        "[JEV ROUTER] probabilities="
                        f"{probabilities}"
                    ),
                    flush=True,
                )

        # ====================================================================
        # ERRORS
        # ====================================================================

        except asyncio.CancelledError:
            self.accounting.settle(attempt)
            raise

        except httpx.HTTPStatusError as exc:
            self.accounting.settle(attempt)

            print(
                (
                    "[JEV ROUTER] HTTPStatusError: "
                    f"{exc.response.status_code} "
                    f"{exc.response.text}"
                ),
                flush=True,
            )

        except httpx.TimeoutException as exc:
            self.accounting.settle(attempt)

            print(
                f"[JEV ROUTER] timeout: {exc}",
                flush=True,
            )

        except httpx.HTTPError as exc:
            self.accounting.settle(attempt)

            print(
                (
                    "[JEV ROUTER] HTTP error="
                    f"{type(exc).__name__}: {exc}"
                ),
                flush=True,
            )

        except (
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as exc:
            self.accounting.settle(attempt)

            print(
                (
                    "[JEV ROUTER] classifier error="
                    f"{type(exc).__name__}: {exc}"
                ),
                flush=True,
            )

        # ====================================================================
        # FAIL SAFE
        # ====================================================================

        total_latency = (
            time.perf_counter()
            - classify_start
        )

        fallback = self._fallback_choice(context, transcript)
        print(f"[JEV ROUTER] using fallback tier={fallback}", flush=True)

        if self.log_timing:
            print(
                (
                    "[JEV ROUTER] "
                    f"total_classifier_latency={total_latency:.3f}s "
                    "result=FALLBACK "
                    f"tier={fallback}"
                ),
                flush=True,
            )

        return fallback

    def _fallback_choice(self, context, transcript):
        """Return only a currently eligible configured fallback in strict mode."""
        if not self.cost_config:
            return FAIL_TIER
        rows = self._eligible_models(context, transcript)
        if not rows:
            raise BudgetDenied('Strict Jev fallback has no eligible model')
        return rows[0]['alias']

    def _eligible_models(self, context, transcript):
        """Build the server-owned Jev choice set from current ledger capacity."""
        if not self.cost_config:
            return []
        routes = self.cost_config.get('routes', {})
        route = routes.get('jev')
        candidate_rows = route.get('candidates', []) if route else []
        if not candidate_rows:
            raise BudgetDenied('Strict Jev requires configured candidates')
        metadata = context.get('metadata', {}) if isinstance(context, Mapping) else getattr(context, 'metadata', {})
        from router.cost_transport import get_request_context
        trusted = get_request_context(metadata)
        if trusted['policy_revision'] != policy_revision(self.cost_config):
            raise BudgetDenied('request_policy_revision_mismatch')
        route_required = route.get('required_capabilities', []) if isinstance(route, Mapping) else []
        required = frozenset(route_required) | trusted['required_capabilities']
        request_payload = trusted['payload']
        report = self.accounting.ledger.report()
        request_remaining = self.accounting.ledger.request_remaining(trusted['id'])
        result = []
        for row in candidate_rows:
            capabilities = frozenset(row.get('capabilities', []))
            contract = self.cost_config.get('contracts', {}).get(row.get('contract'))
            if not contract:
                continue
            try:
                charges = []
                for identifier in row.get('deployment_ids', []):
                    if identifier not in trusted['allowed_deployments'] or identifier in trusted['failed_deployments']:
                        continue
                    deployment = self.cost_config['deployments'][identifier]
                    if deployment['free'] and trusted['free_unavailable']:
                        continue
                    outgoing = dict(request_payload, model=deployment['provider_model'])
                    charges.append(request_charge(contract, outgoing))
                if not charges:
                    continue
                estimate = max(charge[0] for charge in charges)
                bound = max(charge[1] for charge in charges)
            except (ValueError, KeyError):
                continue
            candidate = Candidate(alias=row['alias'], canonical=row['canonical'], capabilities=capabilities,
                                  free=bool(row.get('free')), estimate=estimate, bound=bound)
            if bound <= request_remaining and candidate_is_eligible(candidate, required, report):
                model = report['models'].get(row['canonical'])
                result.append({'alias': row['alias'], 'canonical': row['canonical'],
                               'capabilities': sorted(capabilities), 'free': bool(row.get('free')),
                               'estimate': estimate, 'bound': bound,
                               'remaining_today': model['today']['remaining'] if model else None,
                               'remaining_month': model['month']['remaining'] if model else None,
                               'remaining_request': request_remaining,
                               'remaining_overall_today': report['overall']['today']['remaining'],
                               'remaining_overall_month': report['overall']['month']['remaining']})
        free = [item for item in result if item['free']]
        return sorted(free or result, key=lambda item: (item['estimate'], item['alias']))

    # ========================================================================
    # CALLABLE INTERFACE
    # ========================================================================

    async def __call__(
        self,
        context: Any,
    ) -> str:

        return await self.classify(
            context
        )


# ============================================================================
# LITELLM PLUGIN EXPORT
# ============================================================================

# config.yaml:
#
#   classifier_plugin: jev_classifier.jev_classifier
#
jev_classifier = OpenRouterJevClassifier()
