#!/usr/bin/env python3
"""
test-models.py

PRODUCTION LITELLM ROUTER HEALTH CHECK

Purpose
-------
Answers:

    "Are the LiteLLM aliases and fallbacks I actually deployed healthy?"

This script talks to LiteLLM only.

It does NOT discover all OpenRouter free models.
Use discover-free-models.py for discovery/ranking.

Checks
------
- p50 / p95 / max latency
- success rate
- direct-primary rate
- fallback rate
- actual upstream model/group
- hard SLA violations
- one capability probe per route type
- Jev end-to-end routing

Environment
-----------
LITELLM_URL
LITELLM_API_KEY

Optional
--------
ROUTER_HEALTH_RUNS=3
ROUTER_HEALTH_RPM=10            # free-route client pacing; leaves fallback headroom
ROUTER_PAID_HEALTH_RPM=60       # paid-route client pacing
ROUTER_HEALTH_DELAY=0.0         # optional EXTRA delay beyond global pacer
MODEL_HEALTH_TIMEOUT=30
JEV_HEALTH_TIMEOUT=60
ROUTER_TEST_BACKUPS=1

Why only 10 RPM?
----------------
A single LiteLLM request can fan out to multiple OpenRouter :free requests when
fallbacks are traversed. Pacing client requests at 10 RPM leaves headroom under
OpenRouter's 20 free-model requests/minute limit so the health checker is less
likely to create the failures it is trying to measure.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


# ============================================================================
# CONFIG
# ============================================================================

BASE_URL = os.getenv(
    "LITELLM_URL",
    "http://127.0.0.1:4000",
).rstrip("/")

API_KEY = os.getenv(
    "LITELLM_API_KEY"
)

if not API_KEY:
    print(
        "ERROR: LITELLM_API_KEY is not set.",
        file=sys.stderr,
    )
    raise SystemExit(2)

RUNS = max(
    1,
    int(
        os.getenv(
            "ROUTER_HEALTH_RUNS",
            "3",
        )
    ),
)

# LiteLLM requests can internally fan out to multiple OpenRouter :free model
# attempts when fallbacks are traversed. Use a conservative account-wide client
# rate so the health checker does not manufacture its own 429/cooldown storm.
HEALTH_RPM = min(
    19.0,
    max(
        1.0,
        float(
            os.getenv(
                "ROUTER_HEALTH_RPM",
                "10",
            )
        ),
    ),
)

PAID_HEALTH_RPM = max(
    1.0,
    float(
        os.getenv(
            "ROUTER_PAID_HEALTH_RPM",
            "60",
        )
    ),
)

# Optional EXTRA delay. Normally leave at 0; the global pacer already spaces
# every health/capability request.
DELAY = max(
    0.0,
    float(
        os.getenv(
            "ROUTER_HEALTH_DELAY",
            "0.0",
        )
    ),
)

NORMAL_TIMEOUT = max(
    5.0,
    float(
        os.getenv(
            "MODEL_HEALTH_TIMEOUT",
            "30",
        )
    ),
)

JEV_TIMEOUT = max(
    5.0,
    float(
        os.getenv(
            "JEV_HEALTH_TIMEOUT",
            "60",
        )
    ),
)

TEST_BACKUPS = (
    os.getenv(
        "ROUTER_TEST_BACKUPS",
        "1",
    ).lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)


# ============================================================================
# CONTRACTS
# ============================================================================

@dataclass(frozen=True)
class Contract:
    target_seconds: float
    hard_seconds: float
    min_success_rate: float
    max_fallback_rate: float


CONTRACTS = {
    "FAST": Contract(
        0.8,
        2.0,
        0.95,
        0.20,
    ),
    "GENERAL_EFFICIENT": Contract(
        1.5,
        4.0,
        0.95,
        0.20,
    ),
    "GENERAL_CAPABLE": Contract(
        3.0,
        8.0,
        0.95,
        0.20,
    ),
    "REASONING_EFFICIENT": Contract(
        2.0,
        5.0,
        0.95,
        0.20,
    ),
    "REASONING_CAPABLE": Contract(
        4.0,
        10.0,
        0.95,
        0.20,
    ),
    "AGENTIC_EFFICIENT": Contract(
        1.5,
        4.0,
        0.95,
        0.20,
    ),
    "AGENTIC_CAPABLE": Contract(
        3.0,
        8.0,
        0.95,
        0.20,
    ),
    "CODING_EFFICIENT": Contract(
        1.5,
        4.0,
        0.95,
        0.20,
    ),
    "CODING_CAPABLE": Contract(
        3.0,
        8.0,
        0.95,
        0.20,
    ),
    "VISION": Contract(
        2.0,
        5.0,
        0.95,
        0.20,
    ),
    "COMPRESSION": Contract(
        3.0,
        8.0,
        0.95,
        0.20,
    ),
    "EMERGENCY": Contract(
        5.0,
        10.0,
        0.90,
        1.00,
    ),
    "JEV": Contract(
        4.0,
        8.0,
        0.95,
        0.30,
    ),
}


# ============================================================================
# CURRENT DEPLOYED ALIASES
# ============================================================================

ALIASES: dict[
    str,
    dict[str, Any],
] = {
    "jev": {
        "tier": "JEV",
        "expected": "-",
        "backup": False,
        "pool": "free",
    },
    "free-general-efficient": {
        "tier": "GENERAL_EFFICIENT",
        "expected": "openrouter/poolside/laguna-s-2.1:free",
        "backup": False,
        "pool": "free",
    },
    "free-general-efficient-backup": {
        "tier": "GENERAL_EFFICIENT",
        "expected": "openrouter/google/gemma-4-31b-it:free",
        "backup": True,
        "pool": "free",
    },
    "paid-general-efficient": {
        "tier": "GENERAL_EFFICIENT",
        "expected": "openrouter/poolside/laguna-s-2.1",
        "backup": False,
        "pool": "paid",
    },
    "paid-general-efficient-backup": {
        "tier": "GENERAL_EFFICIENT",
        "expected": "openrouter/google/gemma-4-31b-it",
        "backup": True,
        "pool": "paid",
    },
    "free-general-capable": {
        "tier": "GENERAL_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": False,
        "pool": "free",
    },
    "free-general-capable-backup": {
        "tier": "GENERAL_CAPABLE",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "backup": True,
        "pool": "free",
    },
    "paid-general-capable": {
        "tier": "GENERAL_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-general-capable-backup": {
        "tier": "GENERAL_CAPABLE",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "backup": True,
        "pool": "paid",
    },
    "free-reasoning-efficient": {
        "tier": "REASONING_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": False,
        "pool": "free",
    },
    "free-reasoning-efficient-backup": {
        "tier": "REASONING_EFFICIENT",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "backup": True,
        "pool": "free",
    },
    "paid-reasoning-efficient": {
        "tier": "REASONING_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-reasoning-efficient-backup": {
        "tier": "REASONING_EFFICIENT",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "backup": True,
        "pool": "paid",
    },
    "free-reasoning-capable": {
        "tier": "REASONING_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": False,
        "pool": "free",
    },
    "free-reasoning-capable-backup": {
        "tier": "REASONING_CAPABLE",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "backup": True,
        "pool": "free",
    },
    "paid-reasoning-capable": {
        "tier": "REASONING_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-reasoning-capable-backup": {
        "tier": "REASONING_CAPABLE",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "backup": True,
        "pool": "paid",
    },
    "free-agentic-efficient": {
        "tier": "AGENTIC_EFFICIENT",
        "expected": "openrouter/nex-agi/nex-n2.5-mini:free",
        "backup": False,
        "pool": "free",
    },
    "free-agentic-efficient-backup": {
        "tier": "AGENTIC_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": True,
        "pool": "free",
    },
    "paid-agentic-efficient": {
        "tier": "AGENTIC_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-agentic-efficient-backup": {
        "tier": "AGENTIC_EFFICIENT",
        "expected": "openrouter/poolside/laguna-s-2.1",
        "backup": True,
        "pool": "paid",
    },
    "free-agentic-capable": {
        "tier": "AGENTIC_CAPABLE",
        "expected": "openrouter/nex-agi/nex-n2.5-pro:free",
        "backup": False,
        "pool": "free",
    },
    "free-agentic-capable-backup": {
        "tier": "AGENTIC_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": True,
        "pool": "free",
    },
    "paid-agentic-capable": {
        "tier": "AGENTIC_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-agentic-capable-backup": {
        "tier": "AGENTIC_CAPABLE",
        "expected": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "backup": True,
        "pool": "paid",
    },
    "free-coding-efficient": {
        "tier": "CODING_EFFICIENT",
        "expected": "openrouter/nex-agi/nex-n2.5-mini:free",
        "backup": False,
        "pool": "free",
    },
    "free-coding-efficient-backup": {
        "tier": "CODING_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": True,
        "pool": "free",
    },
    "paid-coding-efficient": {
        "tier": "CODING_EFFICIENT",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-coding-efficient-backup": {
        "tier": "CODING_EFFICIENT",
        "expected": "openrouter/thinkingmachines/inkling-small",
        "backup": True,
        "pool": "paid",
    },
    "free-coding-capable": {
        "tier": "CODING_CAPABLE",
        "expected": "openrouter/nex-agi/nex-n2.5-pro:free",
        "backup": False,
        "pool": "free",
    },
    "free-coding-capable-backup": {
        "tier": "CODING_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": True,
        "pool": "free",
    },
    "paid-coding-capable": {
        "tier": "CODING_CAPABLE",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-coding-capable-backup": {
        "tier": "CODING_CAPABLE",
        "expected": "openrouter/thinkingmachines/inkling-small",
        "backup": True,
        "pool": "paid",
    },
    "fast": {
        "tier": "FAST",
        "expected": "openrouter/poolside/laguna-s-2.1:free",
        "backup": False,
        "pool": "free",
    },
    "fast-backup": {
        "tier": "FAST",
        "expected": "openrouter/google/gemma-4-31b-it:free",
        "backup": True,
        "pool": "free",
    },
    "paid-fast": {
        "tier": "FAST",
        "expected": "openrouter/poolside/laguna-s-2.1",
        "backup": False,
        "pool": "paid",
    },
    "paid-fast-backup": {
        "tier": "FAST",
        "expected": "openrouter/google/gemma-4-31b-it",
        "backup": True,
        "pool": "paid",
    },
    "vision": {
        "tier": "VISION",
        "expected": "openrouter/inclusionai/ling-3.0-flash-vl:free",
        "backup": False,
        "pool": "free",
    },
    "vision-backup": {
        "tier": "VISION",
        "expected": "openrouter/google/gemma-4-26b-a4b-it:free",
        "backup": True,
        "pool": "free",
    },
    "paid-vision": {
        "tier": "VISION",
        "expected": "openrouter/google/gemma-4-26b-a4b-it",
        "backup": False,
        "pool": "paid",
    },
    "paid-vision-backup": {
        "tier": "VISION",
        "expected": "openrouter/google/gemma-4-31b-it",
        "backup": True,
        "pool": "paid",
    },
    "compression": {
        "tier": "COMPRESSION",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731:free",
        "backup": False,
        "pool": "free",
    },
    "compression-backup": {
        "tier": "COMPRESSION",
        "expected": "openrouter/poolside/laguna-s-2.1:free",
        "backup": True,
        "pool": "free",
    },
    "paid-compression": {
        "tier": "COMPRESSION",
        "expected": "openrouter/deepseek/deepseek-v4-flash-0731",
        "backup": False,
        "pool": "paid",
    },
    "paid-compression-backup": {
        "tier": "COMPRESSION",
        "expected": "openrouter/poolside/laguna-s-2.1",
        "backup": True,
        "pool": "paid",
    },
    "free-emergency-capable": {
        "tier": "EMERGENCY",
        "expected": "openrouter/openrouter/free",
        "backup": True,
        "pool": "free",
    },
    "paid-emergency": {
        "tier": "EMERGENCY",
        "expected": "openrouter/openrouter/auto",
        "backup": True,
        "pool": "paid",
    },
}


# ============================================================================
# HELPERS
# ============================================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def percentile(
    values: list[float],
    p: float,
) -> float:
    if not values:
        return math.inf

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    rank = (len(ordered) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)

    if low == high:
        return ordered[low]

    fraction = rank - low

    return ordered[low] + (
        ordered[high] - ordered[low]
    ) * fraction


def fmt_seconds(
    value: float,
) -> str:
    if math.isinf(value):
        return "-"
    return f"{value:.2f}s"


def compact(
    value: Any,
    limit: int = 220,
) -> str:
    text = str(
        value or ""
    ).replace(
        "\n",
        " ",
    )

    return (
        text
        if len(text) <= limit
        else text[: limit - 3] + "..."
    )


def timeout_for(
    alias: str,
) -> float:
    return (
        JEV_TIMEOUT
        if alias == "jev"
        else NORMAL_TIMEOUT
    )


def extract_message(
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        return (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            or {}
        )
    except Exception:
        return {}


def extract_headers(
    response: httpx.Response,
) -> dict[str, Any]:
    headers = {
        key.lower(): value
        for key, value
        in response.headers.items()
    }

    return {
        "actual_model": headers.get(
            "x-litellm-model-name"
        ),
        "actual_group": headers.get(
            "x-litellm-model-group"
        ),
        "provider_ms": safe_float(
            headers.get(
                "x-litellm-response-duration-ms"
            )
        ),
        "overhead_ms": safe_float(
            headers.get(
                "x-litellm-overhead-duration-ms"
            )
        ),
        "fallbacks": safe_int(
            headers.get(
                "x-litellm-attempted-fallbacks"
            ), None
        ),
        "retries": safe_int(
            headers.get(
                "x-litellm-attempted-retries"
            ), None
        ),
        "fallback_errors": headers.get(
            "x-litellm-fallback-errors"
        ),
        "generation_id": headers.get(
            "llm_provider-x-generation-id"
        ),
        "quota_status": headers.get(
            "x-openrouter-free-status"
        ),
        "quota_remaining": headers.get(
            "x-openrouter-free-remaining"
        ),
    }


def extract_error(
    response: httpx.Response,
) -> str:
    try:
        body = response.json()

        error = body.get(
            "error",
            {},
        )

        if (
            isinstance(error, dict)
            and error.get("message")
        ):
            return str(
                error["message"]
            )[:700]

        return str(
            body
        )[:700]

    except Exception:
        return response.text[:700]


# ============================================================================
# GLOBAL LITELLM / OPENROUTER PACER
# ============================================================================

class GlobalRequestPacer:
    """
    Pace EVERY LiteLLM request made by this checker.

    The sleep happens BEFORE request timing starts, so pacing does not inflate
    p50/p95 latency measurements.

    This is intentionally conservative because one LiteLLM call can cause more
    than one OpenRouter :free request when a fallback chain is traversed.
    """

    def __init__(self, requests_per_minute: float) -> None:
        self.requests_per_minute = requests_per_minute
        self.interval_seconds = 60.0 / requests_per_minute
        self.next_request_at = 0.0
        self.request_count = 0

    def wait(self) -> None:
        now = time.perf_counter()

        if self.next_request_at > now:
            time.sleep(
                self.next_request_at - now
            )

        now = time.perf_counter()

        # Never "catch up" with a burst after a slow provider response.
        self.next_request_at = (
            now + self.interval_seconds
        )

        self.request_count += 1


FREE_REQUEST_PACER = GlobalRequestPacer(
    HEALTH_RPM
)

PAID_REQUEST_PACER = GlobalRequestPacer(
    PAID_HEALTH_RPM
)


def is_free_route(alias: str) -> bool:
    metadata = ALIASES.get(alias) or {}
    return metadata.get("pool") == "free"


# ============================================================================
# REQUEST
# ============================================================================

def post_chat(
    client: httpx.Client,
    alias: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Pace before starting the latency clock. Free and paid pools have separate
    # pacing because only the free pool shares OpenRouter's strict free quota.
    pacer = (
        FREE_REQUEST_PACER
        if is_free_route(alias)
        else PAID_REQUEST_PACER
    )
    pacer.wait()

    started = time.perf_counter()

    try:
        response = client.post(
            f"{BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=timeout_for(alias),
        )

        wall = (
            time.perf_counter()
            - started
        )

        diagnostics = extract_headers(
            response
        )

        if response.status_code == 200:
            data = response.json()
            message = extract_message(data)

            return {
                "success": True,
                "http": 200,
                "wall": wall,
                "provider": data.get(
                    "provider",
                    "?",
                ),
                "message": message,
                "content": str(
                    message.get("content")
                    or ""
                ).strip(),
                "reasoning": str(
                    message.get("reasoning")
                    or message.get(
                        "reasoning_content"
                    )
                    or ""
                ).strip(),
                "data": data,
                "diag": diagnostics,
                "error": "",
            }

        return {
            "success": False,
            "http": response.status_code,
            "wall": wall,
            "provider": "-",
            "message": {},
            "content": "",
            "reasoning": "",
            "data": {},
            "diag": diagnostics,
            "error": extract_error(
                response
            ),
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "http": "TIMEOUT",
            "wall": (
                time.perf_counter()
                - started
            ),
            "provider": "-",
            "message": {},
            "content": "",
            "reasoning": "",
            "data": {},
            "diag": {},
            "error": (
                f"Timed out after "
                f"{timeout_for(alias):.1f}s"
            ),
        }

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "http": "NETWORK",
            "wall": (
                time.perf_counter()
                - started
            ),
            "provider": "-",
            "message": {},
            "content": "",
            "reasoning": "",
            "data": {},
            "diag": {},
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }


# ============================================================================
# PERFORMANCE
# ============================================================================

def performance_probe(
    client: httpx.Client,
    alias: str,
) -> dict[str, Any]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Reply with exactly: OK"
                    ),
                }
            ],
            "max_tokens": 96,
            "temperature": 0,
        },
    )

    result["exact_ok"] = (
        result["success"]
        and result["content"].strip().upper()
        == "OK"
    )

    return result


# ============================================================================
# CAPABILITIES
# ============================================================================

def capability_general(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        'Return valid JSON containing '
                        'exactly {"animal":"cat","legs":4}'
                    ),
                }
            ],
            "max_tokens": 192,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    try:
        parsed = json.loads(
            result["content"]
        )

        return (
            result["success"]
            and parsed
            == {
                "animal": "cat",
                "legs": 4,
            },
            json.dumps(
                parsed,
                separators=(",", ":"),
            ),
        )

    except Exception:
        return (
            False,
            result["content"]
            or result["error"],
        )


def capability_reasoning(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Find the smallest positive integer n "
                        "such that n mod 5 = 2 and "
                        "n mod 7 = 3. "
                        "End with exactly FINAL=17"
                    ),
                }
            ],
            "max_tokens": 384,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*17\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def capability_agentic(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_weather",
                "description": (
                    "Get weather for a city."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                        }
                    },
                    "required": [
                        "city"
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]

    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Use the weather tool "
                        "for Rochester."
                    ),
                }
            ],
            "tools": tools,
            "tool_choice": "required",
            "max_tokens": 192,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    calls = (
        result
        .get("message", {})
        .get("tool_calls")
        or []
    )

    if not result["success"] or not calls:
        return (
            False,
            result["content"]
            or result["error"]
            or compact(result["message"]),
        )

    try:
        function = calls[0].get(
            "function",
            {},
        )

        arguments = json.loads(
            function.get(
                "arguments",
                "{}",
            )
        )

        passed = (
            function.get("name")
            == "lookup_weather"
            and str(
                arguments.get(
                    "city",
                    "",
                )
            ).lower()
            == "rochester"
        )

        return (
            passed,
            compact(calls),
        )

    except Exception as exc:
        return (
            False,
            f"{type(exc).__name__}: {exc}",
        )


def capability_coding(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Fix this Python function. "
                        "Return the complete corrected function.\n\n"
                        "def add(a, b):\n"
                        "    return a - b\n"
                    ),
                }
            ],
            "max_tokens": 192,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    answer = result["content"]

    normalized = (
        answer
        .replace(" ", "")
        .replace("\t", "")
    )

    passed = (
        "defadd(a,b):" in normalized
        and "returna+b" in normalized
    )

    return (
        result["success"]
        and passed,
        answer or result["error"],
    )


# Valid 8x8 pure-red RGB PNG.
RED_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSnc"
    "AAAAEklEQVR4nGP8z4AdMOEQH6QSAM1BAQ/oQeJv"
    "AAAAAElFTkSuQmCC"
)


def capability_vision(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Identify the dominant color. "
                                "End with FINAL=<color-name>."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": RED_IMAGE_DATA_URL,
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 160,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*red\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def capability_compression(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    filler = (
        "Routine maintenance entry "
        "with no required identifier. "
    )

    document = (
        filler * 180
        + "\nCRITICAL A: codename ORCHID-71.\n"
        + filler * 180
        + "\nCRITICAL B: primary port 4817.\n"
        + filler * 180
        + "\nCRITICAL C: recovery phrase BLUE LANTERN.\n"
        + filler * 180
    )

    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Read this document and preserve "
                        "all three critical facts. "
                        "Return them clearly.\n\n"
                        + document
                    ),
                }
            ],
            "max_tokens": 512,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = all(
        value.lower() in text.lower()
        for value in (
            "ORCHID-71",
            "4817",
            "BLUE LANTERN",
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def capability_fast(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Convert HELLO WORLD to lowercase. "
                        "End with exactly FINAL=hello world"
                    ),
                }
            ],
            "max_tokens": 96,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*hello world\s*$",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def capability_emergency(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "End your response with "
                        "exactly FINAL=READY"
                    ),
                }
            ],
            "max_tokens": 160,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*READY\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def capability_jev(
    client: httpx.Client,
    alias: str,
) -> tuple[bool, str]:
    result = post_chat(
        client,
        alias,
        {
            "model": alias,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Simple general task. "
                        "End your response with "
                        "exactly FINAL=ROUTER_OK"
                    ),
                }
            ],
            "max_tokens": 192,
            "temperature": 0,
            "reasoning": {
                "effort": "low",
            },
        },
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*ROUTER_OK\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


CAPABILITY_TESTS = {
    "FAST": capability_fast,
    "GENERAL_EFFICIENT": capability_general,
    "GENERAL_CAPABLE": capability_general,
    "REASONING_EFFICIENT": capability_reasoning,
    "REASONING_CAPABLE": capability_reasoning,
    "AGENTIC_EFFICIENT": capability_agentic,
    "AGENTIC_CAPABLE": capability_agentic,
    "CODING_EFFICIENT": capability_coding,
    "CODING_CAPABLE": capability_coding,
    "VISION": capability_vision,
    "COMPRESSION": capability_compression,
    "EMERGENCY": capability_emergency,
    "JEV": capability_jev,
}


# ============================================================================
# EVALUATION
# ============================================================================

def evaluate_alias(
    client: httpx.Client,
    alias: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    contract = CONTRACTS[
        metadata["tier"]
    ]

    probes: list[
        dict[str, Any]
    ] = []

    for index in range(RUNS):
        result = performance_probe(
            client,
            alias,
        )

        probes.append(
            result
        )

        if (
            index + 1 < RUNS
            and DELAY > 0
        ):
            time.sleep(
                DELAY
            )

    successful = [
        result
        for result in probes
        if result["success"]
    ]

    latencies = [
        result["wall"]
        for result in successful
    ]

    success_rate = (
        len(successful) / RUNS
    )

    p50 = percentile(
        latencies,
        0.50,
    )

    p95 = percentile(
        latencies,
        0.95,
    )

    maximum = (
        max(latencies)
        if latencies
        else math.inf
    )

    fallback_count = sum(
        1
        for result in successful
        if safe_int(
            result
            .get("diag", {})
            .get("fallbacks")
        ) > 0
    )

    fallback_rate = (
        fallback_count / RUNS
    )

    fallback_diagnostics_coverage = (
        sum(result.get("diag", {}).get("fallbacks") is not None for result in successful) / len(successful)
        if successful else 0.0
    )

    direct_count = sum(
        1
        for result in successful
        if (
            result
            .get("diag", {})
            .get("actual_group")
            == alias
            and (
                alias == "jev"
                or metadata["expected"] == "-"
                or (
                    result
                    .get("diag", {})
                    .get("actual_model")
                    == metadata["expected"]
                )
            )
        )
    )

    direct_rate = (
        direct_count / RUNS
    )

    hard_violations = sum(
        1
        for result in successful
        if (
            result["wall"]
            > contract.hard_seconds
        )
    )

    capability_function = (
        CAPABILITY_TESTS[
            metadata["tier"]
        ]
    )

    try:
        (
            capability_ok,
            capability_detail,
        ) = capability_function(
            client,
            alias,
        )

    except Exception as exc:
        capability_ok = False
        capability_detail = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

    failures: list[str] = []
    warnings: list[str] = []

    missing_diagnostics = sum(
        result.get("diag", {}).get("fallbacks") is None
        for result in successful
    )
    if missing_diagnostics:
        failures.append(f"fallback diagnostics unknown for {missing_diagnostics} successful request(s)")

    if (
        success_rate
        < contract.min_success_rate
    ):
        failures.append(
            f"success {success_rate:.0%} "
            f"< "
            f"{contract.min_success_rate:.0%}"
        )

    if p95 > contract.hard_seconds:
        failures.append(
            f"p95 {p95:.2f}s "
            f"> hard "
            f"{contract.hard_seconds:.2f}s"
        )

    if hard_violations:
        failures.append(
            f"{hard_violations} "
            "hard-SLA violation(s)"
        )

    if (
        fallback_rate
        > contract.max_fallback_rate
    ):
        failures.append(
            f"fallback {fallback_rate:.0%} "
            f"> "
            f"{contract.max_fallback_rate:.0%}"
        )

    if not capability_ok:
        failures.append(
            "capability probe failed"
        )

    if p95 > contract.target_seconds:
        warnings.append(
            f"p95 {p95:.2f}s "
            f"> target "
            f"{contract.target_seconds:.2f}s"
        )

    if (
        alias != "jev"
        and direct_rate < 0.80
    ):
        warnings.append(
            f"direct-primary only "
            f"{direct_rate:.0%}"
        )

    if failures:
        verdict = "UNHEALTHY"
        icon = "❌"

    elif warnings:
        verdict = "HEALTHY/WARN"
        icon = "⚠️"

    else:
        verdict = "HEALTHY"
        icon = "✅"

    actual_models = sorted(
        {
            result
            .get("diag", {})
            .get("actual_model")
            or "-"
            for result in successful
        }
    )

    actual_groups = sorted(
        {
            result
            .get("diag", {})
            .get("actual_group")
            or "-"
            for result in successful
        }
    )

    providers = sorted(
        {
            result.get(
                "provider",
                "?",
            )
            for result in successful
        }
    )

    return {
        "alias": alias,
        "tier": metadata["tier"],
        "expected": metadata["expected"],
        "backup": metadata["backup"],
        "pool": metadata.get("pool", "unknown"),
        "verdict": verdict,
        "icon": icon,
        "runs": RUNS,
        "success_rate": success_rate,
        "fallback_rate": fallback_rate,
        "fallback_diagnostics_coverage": fallback_diagnostics_coverage,
        "direct_rate": direct_rate,
        "p50": p50,
        "p95": p95,
        "max": maximum,
        "hard_violations": hard_violations,
        "capability_ok": capability_ok,
        "capability_detail": (
            capability_detail
        ),
        "actual_models": actual_models,
        "actual_groups": actual_groups,
        "providers": providers,
        "failures": failures,
        "warnings": warnings,
        "probes": probes,
    }


# ============================================================================
# OUTPUT
# ============================================================================

def print_result(
    result: dict[str, Any],
) -> None:
    contract = CONTRACTS[
        result["tier"]
    ]

    print(
        f"{result['icon']} "
        f"{result['alias']:<34} "
        f"{result['tier']:<21} "
        f"{result['verdict']}"
    )

    print(
        f"      SLA          : "
        f"target<="
        f"{contract.target_seconds:.1f}s "
        f"hard<="
        f"{contract.hard_seconds:.1f}s "
        f"success>="
        f"{contract.min_success_rate:.0%} "
        f"fallback<="
        f"{contract.max_fallback_rate:.0%}"
    )

    print(
        f"      latency      : "
        f"p50="
        f"{fmt_seconds(result['p50'])} "
        f"p95="
        f"{fmt_seconds(result['p95'])} "
        f"max="
        f"{fmt_seconds(result['max'])}"
    )

    print(
        f"      routing      : "
        f"success="
        f"{result['success_rate']:.0%} "
        f"fallback="
        f"{result['fallback_rate']:.0%} "
        f"direct="
        f"{result['direct_rate']:.0%}"
    )

    print(
        f"      capability   : "
        f"{'PASS' if result['capability_ok'] else 'FAIL'} "
        f"("
        f"{compact(result['capability_detail'], 260)}"
        f")"
    )

    print(
        f"      expected     : "
        f"{result['expected']}"
    )

    print(
        f"      groups       : "
        f"{', '.join(result['actual_groups'])}"
    )

    print(
        f"      models       : "
        f"{', '.join(result['actual_models'])}"
    )

    print(
        f"      providers    : "
        f"{', '.join(result['providers'])}"
    )

    quota_states = sorted(
        {
            str(probe.get("diag", {}).get("quota_status") or "-")
            for probe in result.get("probes", [])
        }
    )
    print(
        f"      pool/quota   : "
        f"{result.get('pool', '?')} / "
        f"{', '.join(quota_states)}"
    )

    for failure in result["failures"]:
        print(
            f"      ❌ {failure}"
        )

    for warning in result["warnings"]:
        print(
            f"      ⚠ {warning}"
        )

    print()


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    aliases = {
        alias: metadata
        for alias, metadata
        in ALIASES.items()
        if (
            TEST_BACKUPS
            or not metadata["backup"]
        )
    }

    headers = {
        "Authorization": (
            f"Bearer {API_KEY}"
        ),
        "Content-Type": (
            "application/json"
        ),
    }

    print(
        f"LiteLLM production health "
        f"({RUNS} probes + capability check per alias)"
    )

    print(
        f"free_rpm={HEALTH_RPM:.1f} "
        f"free_interval={FREE_REQUEST_PACER.interval_seconds:.2f}s "
        f"paid_rpm={PAID_HEALTH_RPM:.1f} "
        f"paid_interval={PAID_REQUEST_PACER.interval_seconds:.2f}s "
        f"extra_delay={DELAY:.2f}s"
    )

    print(
        "=" * 145
    )

    results: list[
        dict[str, Any]
    ] = []

    with httpx.Client(
        headers=headers,
    ) as client:
        for alias, metadata in aliases.items():
            result = evaluate_alias(
                client,
                alias,
                metadata,
            )

            results.append(
                result
            )

            print_result(
                result
            )

            if DELAY > 0:
                time.sleep(
                    DELAY
                )

    print(
        "=" * 145
    )

    print()

    healthy = [
        result
        for result in results
        if result["verdict"]
        == "HEALTHY"
    ]

    warned = [
        result
        for result in results
        if result["verdict"]
        == "HEALTHY/WARN"
    ]

    unhealthy = [
        result
        for result in results
        if result["verdict"]
        == "UNHEALTHY"
    ]

    print(
        f"✅ Healthy:       "
        f"{len(healthy)}"
    )

    print(
        f"⚠️ Healthy/warn:  "
        f"{len(warned)}"
    )

    print(
        f"❌ Unhealthy:     "
        f"{len(unhealthy)}"
    )

    if unhealthy:
        print()
        print(
            "❌ Routes needing attention:"
        )

        for result in unhealthy:
            print(
                f"   {result['alias']}: "
                + "; ".join(
                    result["failures"]
                )
            )

    if warned:
        print()
        print(
            "⚠️ Routes worth watching:"
        )

        for result in warned:
            print(
                f"   {result['alias']}: "
                + "; ".join(
                    result["warnings"]
                )
            )

    print()

    print(
        "LiteLLM client requests sent: "
        f"free={FREE_REQUEST_PACER.request_count} "
        f"paid={PAID_REQUEST_PACER.request_count} "
        f"total={FREE_REQUEST_PACER.request_count + PAID_REQUEST_PACER.request_count}"
    )

    print()

    if unhealthy:
        print(
            "RESULT: PRODUCTION ROUTER "
            "HAS UNHEALTHY ROUTES"
        )
        return 1

    if warned:
        print(
            "RESULT: PRODUCTION ROUTER "
            "HEALTHY WITH WARNINGS"
        )
        return 0

    print(
        "RESULT: PRODUCTION ROUTER HEALTHY"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
