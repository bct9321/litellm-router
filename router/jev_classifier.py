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
The actual solver models remain free OpenRouter models.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Mapping, Sequence

import httpx


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

_RUNTIME_METADATA_RE = re.compile(
    r"("
    r"runtime context|"
    r"runtime-generated|"
    r"chat_id|"
    r"message_id|"
    r"inbound_event_kind"
    r")",
    re.IGNORECASE,
)


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

        # Ignore obvious Hermes/runtime metadata injected as user text.
        if (
            role == "user"
            and _RUNTIME_METADATA_RE.search(text)
        ):
            continue

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
    ) -> str:

        classify_start = time.perf_counter()

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
                f"[JEV ROUTER] using fallback tier={FAIL_TIER}",
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

            return FAIL_TIER

        # --------------------------------------------------------------------
        # Build transcript
        # --------------------------------------------------------------------

        transcript = _classification_transcript(
            context
        )

        if not transcript:

            print(
                "[JEV ROUTER] no usable transcript",
                flush=True,
            )

            print(
                f"[JEV ROUTER] using fallback tier={FAIL_TIER}",
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
                        "reason=no_transcript"
                    ),
                    flush=True,
                )

            return FAIL_TIER

        # ====================================================================
        # JEV DECISION REQUEST
        # ====================================================================

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

        # ====================================================================
        # CALL OPENROUTER DECISIONS API
        # ====================================================================

        try:

            jev_start = time.perf_counter()

            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    "https://openrouter.ai/api/alpha/decisions",

                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },

                    json=payload,
                )

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

            if response.is_error:

                print(
                    (
                        f"[JEV ROUTER] HTTP {response.status_code}: "
                        f"{response.text}"
                    ),
                    flush=True,
                )

                response.raise_for_status()

            result = response.json()

            # =================================================================
            # RAW DIAGNOSTICS
            # =================================================================

            raw_answer = (
                result
                .get("answers", {})
                .get("tier")
            )

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
                .get("tier", {})
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

            choice = str(
                choice or ""
            ).strip().upper()

            # =================================================================
            # VALIDATE
            # =================================================================

            if choice in TIERS:

                total_latency = (
                    time.perf_counter()
                    - classify_start
                )

                print(
                    (
                        "[JEV ROUTER] "
                        f"selected tier={choice} "
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
                            f"tier={choice}"
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

        except httpx.HTTPStatusError as exc:

            print(
                (
                    "[JEV ROUTER] HTTPStatusError: "
                    f"{exc.response.status_code} "
                    f"{exc.response.text}"
                ),
                flush=True,
            )

        except httpx.TimeoutException as exc:

            print(
                f"[JEV ROUTER] timeout: {exc}",
                flush=True,
            )

        except httpx.HTTPError as exc:

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

        print(
            f"[JEV ROUTER] using fallback tier={FAIL_TIER}",
            flush=True,
        )

        if self.log_timing:
            print(
                (
                    "[JEV ROUTER] "
                    f"total_classifier_latency={total_latency:.3f}s "
                    "result=FALLBACK "
                    f"tier={FAIL_TIER}"
                ),
                flush=True,
            )

        return FAIL_TIER

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