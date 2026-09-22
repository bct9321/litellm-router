#!/usr/bin/env python3
"""
discover-free-models.py

LIVE OPENROUTER FREE + PAID-SIBLING DISCOVERY + QUALIFICATION

Purpose
-------
Answers:

    "What are the best currently-available FREE OpenRouter models for each job?"
    "What exact PAID siblings exist for those free models?"
    "Which free and paid candidates best satisfy each Hermes routing tier?"

This script talks DIRECTLY to OpenRouter and deliberately bypasses LiteLLM.

Default behavior tests BOTH:
  - concrete :free variants
  - exact paid siblings present in the live catalog

Use --no-free to skip all free inference calls and qualify paid siblings only.

It is separate from test-models.py, which checks the health of the aliases
already deployed in LiteLLM.

Workflow
--------
1. Pull OpenRouter's live model catalog.
2. Keep zero-cost text/chat-capable models.
3. Exclude obvious non-chat endpoints (embeddings, rerankers, TTS, safety-only).
4. Run small performance probes against every candidate.
5. Run capability probes:
      FAST
      GENERAL
      REASONING
      AGENTIC / TOOLS
      CODING
      VISION (only when image input is advertised)
      COMPRESSION (only when context >= 1M)
6. Rank models independently for each tier.
7. Preserve history so a temporary free-tier outage does not permanently
   eliminate an otherwise-good model.

Outputs
-------
openrouter-free-results.json
openrouter-free-rankings.md
recommended-models.yaml
openrouter-free-history.json

Environment
-----------
OPENROUTER_API_KEY              required

Optional
--------
DISCOVERY_RUNS=3
DISCOVERY_RPM=18                # global inference pacing; OpenRouter free max is 20 RPM
DISCOVERY_PROBE_DELAY=0.0       # optional EXTRA delay beyond global pacer
DISCOVERY_TIMEOUT=30
DISCOVERY_OUTPUT_DIR=/tmp/openrouter-free-discovery
DISCOVERY_MAX_MODELS=0          # 0 = all
DISCOVERY_VERBOSE=0
DISCOVERY_INCLUDE_SPECIALIZED=0

Notes
-----
- 404/429/5xx/timeouts hurt CURRENT health; they do not delete history.
- Discovery rankings are empirical qualification results, not replacements
  for public benchmark suites.
- The script does not change LiteLLM config automatically.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


# ============================================================================
# CONFIG
# ============================================================================

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    print("ERROR: OPENROUTER_API_KEY is not set.", file=sys.stderr)
    raise SystemExit(2)

RUNS = max(1, int(os.getenv("DISCOVERY_RUNS", "3")))

# OpenRouter free models are globally rate-limited. Use a little headroom under
# the documented 20 RPM ceiling so timing jitter does not create self-inflicted
# 429s. This pacer applies to EVERY inference request, including capability tests.
DISCOVERY_RPM = min(
    19.0,
    max(
        1.0,
        float(os.getenv("DISCOVERY_RPM", "18")),
    ),
)

# Paid sibling calls do not use the :free 20-RPM pool. Keep a separate pacer so
# paid qualification can run faster without corrupting free-tier pacing.
PAID_DISCOVERY_RPM = max(
    1.0,
    float(os.getenv("DISCOVERY_PAID_RPM", "60")),
)

# Optional paid hard gates. 0 disables the corresponding price ceiling.
# Values are dollars per 1M tokens.
MAX_PAID_INPUT_PER_M = max(
    0.0,
    float(os.getenv("DISCOVERY_MAX_PAID_INPUT_PER_M", "0")),
)
MAX_PAID_OUTPUT_PER_M = max(
    0.0,
    float(os.getenv("DISCOVERY_MAX_PAID_OUTPUT_PER_M", "0")),
)

# Optional EXTRA delay after model/probe loops. Normally leave at 0 because the
# global request pacer already spaces every inference call.
PROBE_DELAY = max(
    0.0,
    float(os.getenv("DISCOVERY_PROBE_DELAY", "0.0")),
)

TIMEOUT = max(5.0, float(os.getenv("DISCOVERY_TIMEOUT", "30")))
MAX_MODELS = max(0, int(os.getenv("DISCOVERY_MAX_MODELS", "0")))

VERBOSE = os.getenv(
    "DISCOVERY_VERBOSE",
    "0",
).lower() in {"1", "true", "yes", "on"}

INCLUDE_SPECIALIZED = os.getenv(
    "DISCOVERY_INCLUDE_SPECIALIZED",
    "0",
).lower() in {"1", "true", "yes", "on"}

OUTPUT_DIR = Path(
    os.getenv(
        "DISCOVERY_OUTPUT_DIR",
        "/tmp/openrouter-free-discovery",
    )
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Legacy paths are retained so existing workflows do not break.
RESULTS_PATH = OUTPUT_DIR / "openrouter-free-results.json"
RANKINGS_PATH = OUTPUT_DIR / "openrouter-free-rankings.md"
RECOMMENDATIONS_PATH = OUTPUT_DIR / "recommended-models.yaml"
HISTORY_PATH = OUTPUT_DIR / "openrouter-free-history.json"

# New Phase-2 artifacts.
MODEL_RESULTS_PATH = OUTPUT_DIR / "openrouter-model-results.json"
MODEL_RANKINGS_PATH = OUTPUT_DIR / "openrouter-model-rankings.md"
PAID_SIBLINGS_PATH = OUTPUT_DIR / "paid-siblings.yaml"
CAPABILITIES_PATH = OUTPUT_DIR / "model-capabilities.json"
ROUTING_PATH = OUTPUT_DIR / "recommended-routing.yaml"

NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat()


# ============================================================================
# TIER CONTRACTS
# ============================================================================

@dataclass(frozen=True)
class Tier:
    name: str
    target_seconds: float
    hard_seconds: float
    min_context: int
    capability_floor: float
    requires_tools: bool = False
    requires_image: bool = False


TIERS: dict[str, Tier] = {
    "FAST": Tier(
        "FAST",
        target_seconds=0.8,
        hard_seconds=2.0,
        min_context=32_000,
        capability_floor=0.80,
    ),
    "GENERAL_EFFICIENT": Tier(
        "GENERAL_EFFICIENT",
        target_seconds=1.5,
        hard_seconds=4.0,
        min_context=128_000,
        capability_floor=0.85,
    ),
    "GENERAL_CAPABLE": Tier(
        "GENERAL_CAPABLE",
        target_seconds=3.0,
        hard_seconds=8.0,
        min_context=128_000,
        capability_floor=0.80,
    ),
    "REASONING_EFFICIENT": Tier(
        "REASONING_EFFICIENT",
        target_seconds=2.0,
        hard_seconds=5.0,
        min_context=128_000,
        capability_floor=0.75,
    ),
    "REASONING_CAPABLE": Tier(
        "REASONING_CAPABLE",
        target_seconds=4.0,
        hard_seconds=10.0,
        min_context=128_000,
        capability_floor=0.90,
    ),
    "AGENTIC_EFFICIENT": Tier(
        "AGENTIC_EFFICIENT",
        target_seconds=1.5,
        hard_seconds=4.0,
        min_context=128_000,
        capability_floor=0.85,
        requires_tools=True,
    ),
    "AGENTIC_CAPABLE": Tier(
        "AGENTIC_CAPABLE",
        target_seconds=3.0,
        hard_seconds=8.0,
        min_context=128_000,
        capability_floor=0.90,
        requires_tools=True,
    ),
    "CODING_EFFICIENT": Tier(
        "CODING_EFFICIENT",
        target_seconds=1.5,
        hard_seconds=4.0,
        min_context=128_000,
        capability_floor=0.80,
    ),
    "CODING_CAPABLE": Tier(
        "CODING_CAPABLE",
        target_seconds=3.0,
        hard_seconds=8.0,
        min_context=128_000,
        capability_floor=0.90,
    ),
    "VISION": Tier(
        "VISION",
        target_seconds=2.0,
        hard_seconds=5.0,
        min_context=128_000,
        capability_floor=1.00,
        requires_image=True,
    ),
    "COMPRESSION": Tier(
        "COMPRESSION",
        target_seconds=3.0,
        hard_seconds=8.0,
        min_context=1_000_000,
        capability_floor=1.00,
    ),
    "EMERGENCY": Tier(
        "EMERGENCY",
        target_seconds=5.0,
        hard_seconds=10.0,
        min_context=128_000,
        capability_floor=0.70,
    ),
}


# ============================================================================
# FILTERING / HELPERS
# ============================================================================

TRANSIENT_CODES = {408, 409, 429, 500, 502, 503, 504}

SPECIALIZED_PATTERNS = (
    "embed",
    "embedding",
    "rerank",
    "tts",
    "text-to-speech",
    "speech",
    "transcrib",
    "content-safety",
    "content safety",
    "moderation",
    "guardrail",
    "lyria",
    "music generation",
    "music-generation",
)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def percentile(values: list[float], p: float) -> float:
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


def fmt_seconds(value: float | None) -> str:
    if value is None or math.isinf(value):
        return "-"
    return f"{value:.2f}s"


def compact(value: Any, limit: int = 220) -> str:
    text = str(value or "").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def architecture(model: dict[str, Any]) -> dict[str, Any]:
    return model.get("architecture") or {}


def input_modalities(model: dict[str, Any]) -> set[str]:
    return {
        str(x).lower()
        for x in architecture(model).get("input_modalities", [])
    }


def output_modalities(model: dict[str, Any]) -> set[str]:
    return {
        str(x).lower()
        for x in architecture(model).get("output_modalities", [])
    }


def supported_parameters(model: dict[str, Any]) -> set[str]:
    return {
        str(x)
        for x in (model.get("supported_parameters") or [])
    }


def price_is_zero(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def is_zero_cost_model(model: dict[str, Any]) -> bool:
    pricing = model.get("pricing") or {}

    return (
        price_is_zero(pricing.get("prompt"))
        and price_is_zero(pricing.get("completion"))
        and price_is_zero(pricing.get("request"))
    )



def is_free_variant_id(model_id: str) -> bool:
    return str(model_id).endswith(":free")


def base_model_id_for_free(model_id: str) -> str | None:
    model_id = str(model_id)

    if not is_free_variant_id(model_id):
        return None

    return model_id[:-5]


def price_per_million(
    model: dict[str, Any],
    key: str,
) -> float | None:
    pricing = model.get("pricing") or {}
    value = pricing.get(key)

    if value is None:
        return None

    try:
        price = float(value) * 1_000_000.0
        return price if math.isfinite(price) and price >= 0 and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def normalized_pricing(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt_per_million": price_per_million(model, "prompt"),
        "completion_per_million": price_per_million(model, "completion"),
        "request": (
            price_per_million(model, "request") / 1_000_000.0
            if price_per_million(model, "request") is not None else None
        ),
    }


def is_paid_chat_candidate(model: dict[str, Any]) -> bool:
    """
    Exact paid sibling eligibility.

    We intentionally require a non-zero-cost base model. A free-only base route
    is not treated as a paid safety path.
    """
    model_id = str(model.get("id", ""))

    if not model_id or is_free_variant_id(model_id):
        return False

    if is_expired(model):
        return False

    if is_zero_cost_model(model):
        return False

    if "text" not in input_modalities(model):
        return False

    if "text" not in output_modalities(model):
        return False

    if not INCLUDE_SPECIALIZED and is_specialized(model):
        return False

    return True

def is_expired(model: dict[str, Any]) -> bool:
    """
    Return True when OpenRouter reports an expiration date that has passed.

    OpenRouter may return either:
      - offset-aware ISO timestamps, e.g. 2026-09-30T00:00:00+00:00
      - UTC timestamps ending in Z
      - offset-naive ISO timestamps

    Normalize all parsed values to UTC-aware datetimes before comparing them
    with NOW so mixed timestamp formats cannot crash discovery.
    """
    value = model.get("expiration_date")

    if not value:
        return False

    try:
        expiry = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if expiry.tzinfo is None:
            expiry = expiry.replace(
                tzinfo=timezone.utc
            )
        else:
            expiry = expiry.astimezone(
                timezone.utc
            )

        return expiry <= NOW

    except (
        ValueError,
        TypeError,
    ):
        # An unparseable catalog timestamp should not make discovery fail.
        # Keep the model and let live request qualification determine health.
        return False


def is_specialized(model: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(model.get("id", "")),
            str(model.get("name", "")),
            str(model.get("description", "")),
        ]
    ).lower()

    return any(
        pattern in haystack
        for pattern in SPECIALIZED_PATTERNS
    )


def is_chat_candidate(model: dict[str, Any]) -> bool:
    model_id = str(model.get("id", ""))

    # Benchmark concrete models, not OpenRouter's random free router.
    if model_id == "openrouter/free":
        return False

    if is_expired(model):
        return False

    if not is_zero_cost_model(model):
        return False

    # This qualifier is specifically about OpenRouter's concrete :free
    # variants. Other zero-priced preview/media endpoints are not part of the
    # free-model router pool we want to benchmark.
    if not is_free_variant_id(model_id):
        return False

    if "text" not in input_modalities(model):
        return False

    if "text" not in output_modalities(model):
        return False

    if not INCLUDE_SPECIALIZED and is_specialized(model):
        return False

    return True


def json_dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================================
# HISTORY
# ============================================================================

def load_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {
            "version": 1,
            "models": {},
        }

    try:
        return json.loads(
            HISTORY_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {
            "version": 1,
            "models": {},
        }


def historical_success_rate(
    history: dict[str, Any],
    model_id: str,
) -> float | None:
    runs = (
        history
        .get("models", {})
        .get(model_id, {})
        .get("runs", [])
    )

    values = [
        safe_float(run.get("success_rate"), -1.0)
        for run in runs[-10:]
    ]

    values = [
        value
        for value in values
        if value >= 0
    ]

    if not values:
        return None

    return sum(values) / len(values)


def save_history(
    history: dict[str, Any],
    summaries: list[dict[str, Any]],
) -> None:
    models = history.setdefault(
        "models",
        {},
    )

    for summary in summaries:
        model_id = summary["id"]

        entry = models.setdefault(
            model_id,
            {
                "first_seen": NOW_ISO,
                "runs": [],
            },
        )

        entry["last_seen"] = NOW_ISO
        entry["name"] = summary.get("name")

        entry["runs"].append(
            {
                "timestamp": NOW_ISO,
                "status": summary["status"],
                "success_rate": summary["performance"]["success_rate"],
                "p50": summary["performance"]["p50"],
                "p95": summary["performance"]["p95"],
                "max": summary["performance"]["max"],
                "capabilities": summary["capabilities"],
            }
        )

        # Keep recent history bounded.
        entry["runs"] = entry["runs"][-50:]

    history["updated_at"] = NOW_ISO

    json_dump(
        HISTORY_PATH,
        history,
    )


# ============================================================================
# GLOBAL OPENROUTER INFERENCE PACER
# ============================================================================

class GlobalRequestPacer:
    """
    Enforce one account-wide minimum interval between OpenRouter inference calls.

    This is intentionally global across performance AND capability probes.
    Sleeping only between performance probes is not sufficient because the
    capability suite can otherwise burst dozens of calls and trigger 429s.
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

        # Schedule from the actual send slot, not the previous requested slot,
        # so slow generations never cause a catch-up burst afterward.
        self.next_request_at = (
            now + self.interval_seconds
        )

        self.request_count += 1


FREE_REQUEST_PACER = GlobalRequestPacer(
    DISCOVERY_RPM
)

PAID_REQUEST_PACER = GlobalRequestPacer(
    PAID_DISCOVERY_RPM
)


# ============================================================================
# OPENROUTER REQUESTS
# ============================================================================

def get_key_info(
    client: httpx.Client,
) -> dict[str, Any]:
    response = client.get(
        f"{OPENROUTER_BASE}/key",
        timeout=15,
    )

    response.raise_for_status()

    data = response.json().get("data", {})

    quota = data.get("free_model_daily_requests") or {}

    return {
        "is_free_tier": data.get("is_free_tier"),
        "free_used": safe_int(quota.get("used"), -1),
        "free_limit": safe_int(quota.get("limit"), -1),
        "free_remaining": safe_int(quota.get("remaining"), -1),
        "spend_limit": data.get("limit"),
        "spend_limit_remaining": data.get("limit_remaining"),
    }


def get_catalog(
    client: httpx.Client,
) -> list[dict[str, Any]]:
    response = client.get(
        f"{OPENROUTER_BASE}/models",
        params={
            "output_modalities": "text",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get(
        "data",
        [],
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


def post_chat(
    client: httpx.Client,
    model_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    # Pacing is test infrastructure and MUST NOT be included in measured model
    # latency. Wait first, then start the wall clock.
    pacer = (
        FREE_REQUEST_PACER
        if is_free_variant_id(model_id)
        else PAID_REQUEST_PACER
    )

    pacer.wait()
    started = time.perf_counter()

    try:
        response = client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            json=payload,
            timeout=TIMEOUT,
        )

        wall = time.perf_counter() - started

        if response.status_code == 200:
            data = response.json()
            message = extract_message(data)

            return {
                "success": True,
                "http": 200,
                "wall": wall,
                "data": data,
                "message": message,
                "content": str(
                    message.get("content") or ""
                ).strip(),
                "reasoning": str(
                    message.get("reasoning")
                    or message.get("reasoning_content")
                    or ""
                ).strip(),
                "error": "",
                "transient": False,
            }

        error_text = response.text[:700]

        try:
            error_json = response.json()
            error = error_json.get("error")

            if isinstance(error, dict):
                error_text = str(
                    error.get("message")
                    or error_text
                )[:700]
        except Exception:
            pass

        if response.status_code == 429:
            error_text = (
                "RATE_LIMITED: "
                + error_text
            )

        return {
            "success": False,
            "http": response.status_code,
            "wall": wall,
            "data": {},
            "message": {},
            "content": "",
            "reasoning": "",
            "error": error_text,
            "transient": (
                response.status_code
                in TRANSIENT_CODES
            ),
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "http": "TIMEOUT",
            "wall": time.perf_counter() - started,
            "data": {},
            "message": {},
            "content": "",
            "reasoning": "",
            "error": (
                f"Timed out after "
                f"{TIMEOUT:.1f}s"
            ),
            "transient": True,
        }

    except httpx.HTTPError as exc:
        return {
            "success": False,
            "http": "NETWORK",
            "wall": time.perf_counter() - started,
            "data": {},
            "message": {},
            "content": "",
            "reasoning": "",
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
            "transient": True,
        }


def base_payload(
    model_id: str,
) -> dict[str, Any]:
    return {
        "model": model_id,
        "temperature": 0,
    }


def add_low_reasoning_if_supported(
    payload: dict[str, Any],
    model: dict[str, Any],
) -> None:
    if "reasoning" in supported_parameters(model):
        payload["reasoning"] = {
            "effort": "low",
        }


# ============================================================================
# PERFORMANCE
# ============================================================================

def performance_probe(
    client: httpx.Client,
    model_id: str,
) -> dict[str, Any]:
    payload = base_payload(
        model_id
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Reply with exactly: OK"
                    ),
                }
            ],
            "max_tokens": 96,
        }
    )

    result = post_chat(
        client,
        model_id,
        payload,
    )

    result["exact_ok"] = (
        result["success"]
        and result["content"].strip().upper() == "OK"
    )

    return result


# ============================================================================
# CAPABILITY PROBES
# ============================================================================

def probe_fast(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    model_id = model["id"]

    payload = base_payload(
        model_id
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Convert HELLO WORLD to lowercase. "
                        "End your response with exactly "
                        "FINAL=hello world"
                    ),
                }
            ],
            "max_tokens": 96,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model_id,
        payload,
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
        result["success"] and passed,
        text or result["error"],
    )


def probe_general(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    model_id = model["id"]

    payload = base_payload(
        model_id
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        'Return valid JSON containing exactly: '
                        '{"animal":"cat","legs":4}'
                    ),
                }
            ],
            "max_tokens": 160,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    if "response_format" in supported_parameters(model):
        payload["response_format"] = {
            "type": "json_object",
        }

    result = post_chat(
        client,
        model_id,
        payload,
    )

    try:
        parsed = json.loads(
            result["content"]
        )

        passed = (
            parsed
            == {
                "animal": "cat",
                "legs": 4,
            }
        )

        return (
            result["success"]
            and passed,
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


def reasoning_payload(
    model: dict[str, Any],
    prompt: str,
) -> dict[str, Any]:
    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "max_tokens": 384,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    return payload


def probe_reasoning_basic(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    prompt = (
        "A box contains 12 balls total and only red and blue balls. "
        "There are twice as many red balls as blue balls. "
        "Solve it and end your response with exactly FINAL=8"
    )

    result = post_chat(
        client,
        model["id"],
        reasoning_payload(
            model,
            prompt,
        ),
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*8\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


def probe_reasoning_hard(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    prompt = (
        "Find the smallest positive integer n such that "
        "n mod 5 = 2 and n mod 7 = 3. "
        "Solve it and end your response with exactly FINAL=17"
    )

    result = post_chat(
        client,
        model["id"],
        reasoning_payload(
            model,
            prompt,
        ),
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


def probe_agentic(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    if "tools" not in supported_parameters(model):
        return (
            False,
            "catalog does not advertise tools",
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_weather",
                "description": (
                    "Get the weather for a city."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                        }
                    },
                    "required": ["city"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
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
            "max_tokens": 160,
        }
    )

    if "tool_choice" in supported_parameters(model):
        payload["tool_choice"] = "required"

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model["id"],
        payload,
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
        call = calls[0]
        function = call.get(
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


def probe_coding_basic(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
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
            "max_tokens": 180,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model["id"],
        payload,
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


def probe_coding_hard(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    prompt = (
        "Analyze this Python code:\n"
        "values = [1, 2, 3, 4]\n"
        "result = [x * x for x in values if x % 2 == 0]\n"
        "print(sum(result))\n\n"
        "End your response with exactly FINAL=20"
    )

    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "max_tokens": 256,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model["id"],
        payload,
    )

    text = result["content"]

    passed = bool(
        re.search(
            r"FINAL\s*=\s*20\b",
            text,
            re.IGNORECASE,
        )
    )

    return (
        result["success"]
        and passed,
        text or result["error"],
    )


# Valid 8x8 pure-red RGB PNG.
RED_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSnc"
    "AAAAEklEQVR4nGP8z4AdMOEQH6QSAM1BAQ/oQeJv"
    "AAAAAElFTkSuQmCC"
)


def probe_vision(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    if "image" not in input_modalities(model):
        return (
            False,
            "catalog does not advertise image input",
        )

    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Identify the dominant color "
                                "of this image. "
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
            "max_tokens": 128,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model["id"],
        payload,
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


def probe_compression(
    client: httpx.Client,
    model: dict[str, Any],
) -> tuple[bool, str]:
    context = safe_int(
        model.get("context_length")
    )

    if context < 1_000_000:
        return (
            False,
            f"context {context:,} < 1,000,000",
        )

    filler = (
        "Routine maintenance entry with "
        "no required identifier. "
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

    payload = base_payload(
        model["id"]
    )

    payload.update(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Read the document and preserve "
                        "the three critical facts. "
                        "Return them clearly.\n\n"
                        + document
                    ),
                }
            ],
            "max_tokens": 512,
        }
    )

    add_low_reasoning_if_supported(
        payload,
        model,
    )

    result = post_chat(
        client,
        model["id"],
        payload,
    )

    text = result["content"]

    # Compression capability is about preservation, not JSON obedience.
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


# ============================================================================
# MODEL EVALUATION
# ============================================================================

def run_capability(
    client: httpx.Client,
    model: dict[str, Any],
    function: Any,
) -> dict[str, Any]:
    try:
        passed, detail = function(
            client,
            model,
        )

        return {
            "pass": bool(passed),
            "detail": compact(
                detail,
                350,
            ),
        }

    except Exception as exc:
        return {
            "pass": False,
            "detail": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }


def evaluate_model(
    client: httpx.Client,
    model: dict[str, Any],
) -> dict[str, Any]:
    model_id = model["id"]

    print(f"\n[{model_id}]")

    performance: list[dict[str, Any]] = []

    for index in range(RUNS):
        result = performance_probe(
            client,
            model_id,
        )

        performance.append(
            result
        )

        marker = (
            "✓"
            if result["success"]
            else "!"
        )

        print(
            f"  perf {index + 1}/{RUNS}: "
            f"{marker} {result['http']} "
            f"{result['wall']:.2f}s"
        )

        if (
            index + 1 < RUNS
            and PROBE_DELAY > 0
        ):
            time.sleep(
                PROBE_DELAY
            )

    successful = [
        result
        for result in performance
        if result["success"]
    ]

    latencies = [
        result["wall"]
        for result in successful
    ]

    success_rate = (
        len(successful) / RUNS
    )

    exact_ok_rate = (
        sum(
            1
            for result in successful
            if result.get("exact_ok")
        )
        / RUNS
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

    if success_rate == 1.0:
        status = "HEALTHY"
    elif success_rate > 0:
        status = "DEGRADED"
    else:
        status = "UNAVAILABLE"

    # If the endpoint is completely unavailable today, record it and avoid
    # spending more calls on capability tests.
    if not successful:
        capabilities = {
            name: {
                "pass": False,
                "detail": (
                    "not tested: endpoint unavailable "
                    "during performance screen"
                ),
            }
            for name in (
                "fast",
                "general",
                "reasoning_basic",
                "reasoning_hard",
                "agentic",
                "coding_basic",
                "coding_hard",
                "vision",
                "compression",
            )
        }

    else:
        capabilities = {
            "fast": run_capability(
                client,
                model,
                probe_fast,
            ),
            "general": run_capability(
                client,
                model,
                probe_general,
            ),
            "reasoning_basic": run_capability(
                client,
                model,
                probe_reasoning_basic,
            ),
            "reasoning_hard": run_capability(
                client,
                model,
                probe_reasoning_hard,
            ),
            "agentic": run_capability(
                client,
                model,
                probe_agentic,
            ),
            "coding_basic": run_capability(
                client,
                model,
                probe_coding_basic,
            ),
            "coding_hard": run_capability(
                client,
                model,
                probe_coding_hard,
            ),
        }

        if "image" in input_modalities(model):
            capabilities["vision"] = (
                run_capability(
                    client,
                    model,
                    probe_vision,
                )
            )
        else:
            capabilities["vision"] = {
                "pass": False,
                "detail": (
                    "catalog does not advertise image input"
                ),
            }

        if safe_int(
            model.get("context_length")
        ) >= 1_000_000:
            capabilities["compression"] = (
                run_capability(
                    client,
                    model,
                    probe_compression,
                )
            )
        else:
            capabilities["compression"] = {
                "pass": False,
                "detail": "context < 1M",
            }

    if VERBOSE:
        for name, value in capabilities.items():
            print(
                f"  {name:<16}: "
                f"{'PASS' if value['pass'] else 'FAIL'} "
                f"{value['detail']}"
            )
    else:
        capability_passes = sum(
            1
            for value in capabilities.values()
            if value["pass"]
        )

        print(
            f"  capabilities: "
            f"{capability_passes}/"
            f"{len(capabilities)} "
            f"| p50={fmt_seconds(p50)} "
            f"p95={fmt_seconds(p95)} "
            f"| success={success_rate:.0%}"
        )

    return {
        "id": model_id,
        "name": model.get("name"),
        "description": model.get("description"),
        "variant": model.get("_discovery_variant", "free"),
        "paired_model": model.get("_paired_model"),
        "free_sibling": model.get("_free_sibling"),
        "paid_sibling": model.get("_paid_sibling"),
        "pricing_per_million": normalized_pricing(model),
        "context_length": safe_int(
            model.get("context_length")
        ),
        "expiration_date": model.get(
            "expiration_date"
        ),
        "architecture": architecture(model),
        "supported_parameters": sorted(
            supported_parameters(model)
        ),
        "pricing": model.get("pricing"),
        "status": status,
        "performance": {
            "runs": RUNS,
            "success_rate": success_rate,
            "exact_ok_rate": exact_ok_rate,
            "p50": (
                None
                if math.isinf(p50)
                else p50
            ),
            "p95": (
                None
                if math.isinf(p95)
                else p95
            ),
            "max": (
                None
                if math.isinf(maximum)
                else maximum
            ),
            "errors": [
                {
                    "http": result["http"],
                    "error": result["error"],
                    "transient": result.get(
                        "transient",
                        False,
                    ),
                }
                for result in performance
                if not result["success"]
            ],
        },
        "capabilities": capabilities,
    }


# ============================================================================
# TIER SCORING
# ============================================================================

def capability_value(
    summary: dict[str, Any],
    name: str,
) -> float:
    return (
        1.0
        if (
            summary
            .get("capabilities", {})
            .get(name, {})
            .get("pass")
        )
        else 0.0
    )


def tier_capability_score(
    tier_name: str,
    summary: dict[str, Any],
) -> float:
    value = lambda name: (
        capability_value(
            summary,
            name,
        )
    )

    if tier_name == "FAST":
        return (
            0.75 * value("fast")
            + 0.25 * value("general")
        )

    if tier_name == "GENERAL_EFFICIENT":
        return (
            0.70 * value("general")
            + 0.30 * value("fast")
        )

    if tier_name == "GENERAL_CAPABLE":
        return (
            0.40 * value("general")
            + 0.25 * value("reasoning_basic")
            + 0.20 * value("reasoning_hard")
            + 0.15 * value("coding_basic")
        )

    if tier_name == "REASONING_EFFICIENT":
        return (
            0.70 * value("reasoning_basic")
            + 0.30 * value("general")
        )

    if tier_name == "REASONING_CAPABLE":
        return (
            0.30 * value("reasoning_basic")
            + 0.55 * value("reasoning_hard")
            + 0.15 * value("general")
        )

    if tier_name == "AGENTIC_EFFICIENT":
        return (
            0.80 * value("agentic")
            + 0.20 * value("general")
        )

    if tier_name == "AGENTIC_CAPABLE":
        return (
            0.60 * value("agentic")
            + 0.25 * value("reasoning_basic")
            + 0.15 * value("general")
        )

    if tier_name == "CODING_EFFICIENT":
        return (
            0.70 * value("coding_basic")
            + 0.20 * value("coding_hard")
            + 0.10 * value("general")
        )

    if tier_name == "CODING_CAPABLE":
        return (
            0.30 * value("coding_basic")
            + 0.50 * value("coding_hard")
            + 0.20 * value("reasoning_basic")
        )

    if tier_name == "VISION":
        return (
            0.85 * value("vision")
            + 0.15 * value("general")
        )

    if tier_name == "COMPRESSION":
        return (
            0.90 * value("compression")
            + 0.10 * value("general")
        )

    if tier_name == "EMERGENCY":
        return (
            0.60 * value("general")
            + 0.40 * value("fast")
        )

    return 0.0



TIER_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "FAST": {
        "capability": 0.15,
        "reliability": 0.25,
        "speed": 0.50,
        "cost": 0.10,
    },
    "GENERAL_EFFICIENT": {
        "capability": 0.35,
        "reliability": 0.25,
        "speed": 0.30,
        "cost": 0.10,
    },
    "GENERAL_CAPABLE": {
        "capability": 0.55,
        "reliability": 0.25,
        "speed": 0.10,
        "cost": 0.10,
    },
    "REASONING_EFFICIENT": {
        "capability": 0.45,
        "reliability": 0.25,
        "speed": 0.20,
        "cost": 0.10,
    },
    "REASONING_CAPABLE": {
        "capability": 0.60,
        "reliability": 0.20,
        "speed": 0.10,
        "cost": 0.10,
    },
    "AGENTIC_EFFICIENT": {
        "capability": 0.40,
        "reliability": 0.30,
        "speed": 0.20,
        "cost": 0.10,
    },
    "AGENTIC_CAPABLE": {
        "capability": 0.50,
        "reliability": 0.30,
        "speed": 0.10,
        "cost": 0.10,
    },
    "CODING_EFFICIENT": {
        "capability": 0.45,
        "reliability": 0.25,
        "speed": 0.20,
        "cost": 0.10,
    },
    "CODING_CAPABLE": {
        "capability": 0.60,
        "reliability": 0.20,
        "speed": 0.10,
        "cost": 0.10,
    },
    "VISION": {
        "capability": 0.60,
        "reliability": 0.20,
        "speed": 0.10,
        "cost": 0.10,
    },
    "COMPRESSION": {
        "capability": 0.65,
        "reliability": 0.20,
        "speed": 0.05,
        "cost": 0.10,
    },
    "EMERGENCY": {
        "capability": 0.15,
        "reliability": 0.55,
        "speed": 0.15,
        "cost": 0.15,
    },
}


def paid_cost_score(summary: dict[str, Any]) -> float:
    """
    Free models score 1.0. Paid models receive a smooth 0..1 score based on a
    blended $/1M price. Cost is deliberately only one component of tier score.
    """
    if summary.get("variant") == "free":
        return 1.0

    pricing = summary.get("pricing_per_million") or {}
    input_price = pricing.get("prompt_per_million")
    output_price = pricing.get("completion_per_million")

    if input_price is None or output_price is None:
        return 0.0

    blended = (
        0.70 * max(0.0, float(input_price))
        + 0.30 * max(0.0, float(output_price))
    )

    return 1.0 / (1.0 + blended)


def score_for_tier(
    tier: Tier,
    summary: dict[str, Any],
    history: dict[str, Any],
) -> dict[str, Any]:
    model_id = summary["id"]
    performance = summary["performance"]

    current_success = safe_float(
        performance.get("success_rate")
    )

    historical_success = (
        historical_success_rate(
            history,
            model_id,
        )
    )

    reliability = (
        current_success
        if historical_success is None
        else (
            0.75 * current_success
            + 0.25 * historical_success
        )
    )

    p95 = performance.get("p95")

    if p95 is None:
        speed_score = 0.0
    elif p95 <= tier.target_seconds:
        speed_score = 1.0
    else:
        span = max(
            0.001,
            (
                2.0 * tier.hard_seconds
                - tier.target_seconds
            ),
        )

        speed_score = max(
            0.0,
            1.0
            - (
                (p95 - tier.target_seconds)
                / span
            ),
        )

    capability_score = (
        tier_capability_score(
            tier.name,
            summary,
        )
    )

    context = safe_int(
        summary.get("context_length")
    )

    parameters = set(
        summary.get(
            "supported_parameters",
            [],
        )
    )

    inputs = {
        str(value).lower()
        for value in (
            summary
            .get("architecture", {})
            .get("input_modalities", [])
        )
    }

    reasons: list[str] = []

    metadata_ok = True

    if context < tier.min_context:
        metadata_ok = False
        reasons.append(
            f"context {context:,} "
            f"< {tier.min_context:,}"
        )

    if (
        tier.requires_tools
        and "tools" not in parameters
    ):
        metadata_ok = False
        reasons.append(
            "tools not advertised"
        )

    if (
        tier.requires_image
        and "image" not in inputs
    ):
        metadata_ok = False
        reasons.append(
            "image input not advertised"
        )

    capability_ok = (
        capability_score
        >= tier.capability_floor
    )

    if not capability_ok:
        reasons.append(
            f"capability "
            f"{capability_score:.0%} "
            f"< {tier.capability_floor:.0%}"
        )

    hard_speed_ok = (
        p95 is not None
        and p95 <= tier.hard_seconds
    )

    if not hard_speed_ok:
        reasons.append(
            f"p95 "
            f"{p95 if p95 is not None else 'n/a'} "
            f"> hard {tier.hard_seconds}s"
        )

    current_usable = (
        current_success > 0
    )

    cost_score = paid_cost_score(summary)
    pricing = summary.get("pricing_per_million") or {}

    paid_price_ok = True

    if summary.get("variant") == "paid":
        input_price = pricing.get("prompt_per_million")
        output_price = pricing.get("completion_per_million")

        if any(not isinstance(value, (int, float)) or isinstance(value, bool)
               or not math.isfinite(value) or value < 0
               for value in (input_price, output_price, pricing.get("request"))):
            paid_price_ok = False
            reasons.append("paid price unknown or invalid")

        if (
            MAX_PAID_INPUT_PER_M > 0
            and input_price is not None
            and input_price > MAX_PAID_INPUT_PER_M
        ):
            paid_price_ok = False
            reasons.append(
                f"paid input ${input_price:.3f}/M "
                f"> ceiling ${MAX_PAID_INPUT_PER_M:.3f}/M"
            )

        if (
            MAX_PAID_OUTPUT_PER_M > 0
            and output_price is not None
            and output_price > MAX_PAID_OUTPUT_PER_M
        ):
            paid_price_ok = False
            reasons.append(
                f"paid output ${output_price:.3f}/M "
                f"> ceiling ${MAX_PAID_OUTPUT_PER_M:.3f}/M"
            )

    if not current_usable:
        reasons.append(
            "no successful request this run"
        )

    if summary["status"] == "DEGRADED":
        reasons.append(
            "currently degraded"
        )

    elif summary["status"] == "UNAVAILABLE":
        reasons.append(
            "currently unavailable"
        )

    eligible = (
        metadata_ok
        and capability_ok
        and hard_speed_ok
        and current_usable
        and paid_price_ok
    )

    weights = TIER_SCORE_WEIGHTS[tier.name]

    score = 100.0 * (
        weights["capability"] * capability_score
        + weights["reliability"] * reliability
        + weights["speed"] * speed_score
        + weights["cost"] * cost_score
    )

    return {
        "model": model_id,
        "name": summary.get("name"),
        "score": round(
            score,
            2,
        ),
        "eligible": eligible,
        "capability_score": round(
            capability_score,
            4,
        ),
        "reliability_score": round(
            reliability,
            4,
        ),
        "speed_score": round(
            speed_score,
            4,
        ),
        "cost_score": round(
            cost_score,
            4,
        ),
        "variant": summary.get("variant"),
        "paired_model": summary.get("paired_model"),
        "pricing_per_million": pricing,
        "current_success_rate": (
            current_success
        ),
        "historical_success_rate": (
            historical_success
        ),
        "p50": performance.get("p50"),
        "p95": performance.get("p95"),
        "max": performance.get("max"),
        "context_length": context,
        "status": summary["status"],
        "reasons": reasons,
    }


def rank_models(
    summaries: list[dict[str, Any]],
    history: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for tier_name, tier in TIERS.items():
        rows = [
            score_for_tier(
                tier,
                summary,
                history,
            )
            for summary in summaries
        ]

        rows.sort(
            key=lambda row: (
                row["eligible"],
                row["score"],
                row["current_success_rate"],
                -(
                    row["p95"]
                    if row["p95"] is not None
                    else 9999
                ),
            ),
            reverse=True,
        )

        rankings[tier_name] = rows

    return rankings


# ============================================================================
# OUTPUT
# ============================================================================

def write_rankings_markdown(
    summaries: list[dict[str, Any]],
    rankings: dict[
        str,
        list[dict[str, Any]],
    ],
) -> None:
    lines = [
        "# OpenRouter Free Model Rankings",
        "",
        f"Generated: `{NOW_ISO}`",
        "",
        f"Candidates tested: **{len(summaries)}**",
        f"Performance probes/model: **{RUNS}**",
        "",
        "> Current free-tier outages lower today's score but do not erase history.",
        "",
    ]

    for tier_name, rows in rankings.items():
        lines.extend(
            [
                f"## {tier_name}",
                "",
                "| # | Model | Score | Eligible | Health | p50 | p95 | Success | Context | Notes |",
                "|---:|---|---:|:---:|---|---:|---:|---:|---:|---|",
            ]
        )

        for index, row in enumerate(
            rows[:10],
            start=1,
        ):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(index),
                        f"`{row['model']}`",
                        f"{row['score']:.2f}",
                        (
                            "yes"
                            if row["eligible"]
                            else "no"
                        ),
                        row["status"],
                        fmt_seconds(
                            row["p50"]
                        ),
                        fmt_seconds(
                            row["p95"]
                        ),
                        (
                            f"{row['current_success_rate']:.0%}"
                        ),
                        f"{row['context_length']:,}",
                        (
                            "; ".join(
                                row["reasons"]
                            )
                            or "—"
                        ),
                    ]
                )
                + " |"
            )

        lines.append("")

    RANKINGS_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_recommendations_yaml(
    rankings: dict[
        str,
        list[dict[str, Any]],
    ],
) -> None:
    lines = [
        f'generated_at: "{NOW_ISO}"',
        'source: "openrouter-live-free-discovery"',
        "tiers:",
    ]

    for tier_name, rows in rankings.items():
        eligible = [
            row
            for row in rows
            if row["eligible"]
        ][:5]

        lines.append(
            f"  {tier_name}:"
        )

        if not eligible:
            lines.append(
                "    candidates: []"
            )
            continue

        lines.append(
            "    candidates:"
        )

        for row in eligible:
            lines.extend(
                [
                    f'      - model: "{row["model"]}"',
                    f'        score: {row["score"]:.2f}',
                    f'        status: "{row["status"]}"',
                    (
                        "        success_rate: "
                        f"{row['current_success_rate']:.4f}"
                    ),
                    (
                        "        p50_seconds: "
                        f"{row['p50'] if row['p50'] is not None else 'null'}"
                    ),
                    (
                        "        p95_seconds: "
                        f"{row['p95'] if row['p95'] is not None else 'null'}"
                    ),
                    (
                        "        context_length: "
                        f"{row['context_length']}"
                    ),
                ]
            )

    RECOMMENDATIONS_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def print_top_rankings(
    rankings: dict[
        str,
        list[dict[str, Any]],
    ],
) -> None:
    print(
        "\n"
        + "=" * 120
    )

    print(
        "TOP FREE MODEL CANDIDATES"
    )

    print(
        "=" * 120
    )

    for tier_name, rows in rankings.items():
        eligible = [
            row
            for row in rows
            if row["eligible"]
        ][:3]

        print(
            f"\n{tier_name}"
        )

        if not eligible:
            print(
                "  No model passed the current contract."
            )
            continue

        for index, row in enumerate(
            eligible,
            start=1,
        ):
            print(
                f"  {index}. "
                f"{row['model']:<55} "
                f"score={row['score']:>6.2f} "
                f"p95={fmt_seconds(row['p95']):>7} "
                f"success={row['current_success_rate']:.0%}"
            )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and qualify OpenRouter :free models and their exact "
            "paid siblings. Default: test both pools."
        )
    )

    parser.add_argument(
        "--no-free",
        action="store_true",
        help=(
            "Do not send any :free inference requests. Discover the free "
            "catalog for pairing, but test paid siblings only."
        ),
    )

    parser.add_argument(
        "--no-paid",
        action="store_true",
        help=(
            "Test only :free variants. Paid siblings are still discovered "
            "and written to paid-siblings.yaml."
        ),
    )

    parser.add_argument(
        "--force-partial-free",
        action="store_true",
        help=(
            "Allow a free run even when /api/v1/key reports too few remaining "
            "free requests to finish all selected free candidates. Normally "
            "the script skips the free pool rather than produce biased rankings."
        ),
    )

    parser.add_argument(
        "--max-models",
        type=int,
        default=MAX_MODELS,
        help="Limit the number of free models selected before sibling pairing.",
    )

    parser.add_argument(
        "--paid-rpm",
        type=float,
        default=PAID_DISCOVERY_RPM,
        help="Maximum paid-sibling qualification requests/minute.",
    )

    parser.add_argument(
        "--max-paid-input-per-m",
        type=float,
        default=MAX_PAID_INPUT_PER_M,
        help=(
            "Optional paid eligibility ceiling in $/1M input tokens. "
            "0 disables the ceiling."
        ),
    )

    parser.add_argument(
        "--max-paid-output-per-m",
        type=float,
        default=MAX_PAID_OUTPUT_PER_M,
        help=(
            "Optional paid eligibility ceiling in $/1M output tokens. "
            "0 disables the ceiling."
        ),
    )

    args = parser.parse_args()

    if args.no_free and args.no_paid:
        parser.error("--no-free and --no-paid cannot be used together")

    return args


def estimate_requests_for_model(model: dict[str, Any]) -> int:
    # Performance probes.
    total = RUNS

    # fast, general, reasoning_basic, reasoning_hard, agentic,
    # coding_basic, coding_hard. Agentic may not issue a request when tools
    # are absent, so this is intentionally a conservative upper bound.
    total += 7

    if "image" in input_modalities(model):
        total += 1

    if safe_int(model.get("context_length")) >= 1_000_000:
        total += 1

    return total


def build_paid_sibling_map(
    free_models: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {
        str(model.get("id", "")): model
        for model in catalog
    }

    paid_models: list[dict[str, Any]] = []
    sibling_rows: list[dict[str, Any]] = []
    seen_paid: set[str] = set()

    for free_model in free_models:
        free_id = str(free_model.get("id", ""))
        paid_id = base_model_id_for_free(free_id)
        paid_model = by_id.get(paid_id or "")

        exists = bool(
            paid_model
            and is_paid_chat_candidate(paid_model)
        )

        sibling_row = {
            "free_model": free_id,
            "paid_sibling_exists": exists,
            "paid_model": paid_id if exists else None,
            "free_context_length": safe_int(
                free_model.get("context_length")
            ),
            "paid_context_length": (
                safe_int(paid_model.get("context_length"))
                if exists and paid_model
                else None
            ),
            "paid_pricing_per_million": (
                normalized_pricing(paid_model)
                if exists and paid_model
                else None
            ),
            "free_expiration_date": free_model.get("expiration_date"),
        }

        sibling_rows.append(sibling_row)

        free_model["_discovery_variant"] = "free"
        free_model["_paid_sibling"] = (
            paid_id if exists else None
        )
        free_model["_paired_model"] = (
            paid_id if exists else None
        )

        if exists and paid_model and paid_id not in seen_paid:
            paid_copy = dict(paid_model)
            paid_copy["_discovery_variant"] = "paid"
            paid_copy["_free_sibling"] = free_id
            paid_copy["_paired_model"] = free_id
            paid_models.append(paid_copy)
            seen_paid.add(paid_id)

    return paid_models, sibling_rows


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    return json.dumps(str(value))


def write_paid_siblings_yaml(
    sibling_rows: list[dict[str, Any]],
) -> None:
    lines = [
        f'generated_at: "{NOW_ISO}"',
        'source: "openrouter-live-catalog"',
        "models:",
    ]

    for row in sibling_rows:
        lines.extend(
            [
                f'  - free_model: {yaml_scalar(row["free_model"])}',
                (
                    "    paid_sibling_exists: "
                    f'{yaml_scalar(row["paid_sibling_exists"])}'
                ),
                f'    paid_model: {yaml_scalar(row["paid_model"])}',
                (
                    "    free_context_length: "
                    f'{yaml_scalar(row["free_context_length"])}'
                ),
                (
                    "    paid_context_length: "
                    f'{yaml_scalar(row["paid_context_length"])}'
                ),
                (
                    "    free_expiration_date: "
                    f'{yaml_scalar(row["free_expiration_date"])}'
                ),
            ]
        )

        pricing = row.get("paid_pricing_per_million")

        if pricing is None:
            lines.append(
                "    paid_pricing_per_million: null"
            )
        else:
            lines.extend(
                [
                    "    paid_pricing_per_million:",
                    (
                        "      input: "
                        f'{yaml_scalar(pricing.get("prompt_per_million"))}'
                    ),
                    (
                        "      output: "
                        f'{yaml_scalar(pricing.get("completion_per_million"))}'
                    ),
                ]
            )

    PAID_SIBLINGS_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_phase2_rankings_markdown(
    summaries: list[dict[str, Any]],
    rankings_by_pool: dict[str, dict[str, list[dict[str, Any]]]],
    mode: str,
    quota_info: dict[str, Any] | None,
) -> None:
    lines = [
        "# OpenRouter Model Qualification Rankings",
        "",
        f"Generated: `{NOW_ISO}`",
        f"Mode: **{mode}**",
        f"Models tested: **{len(summaries)}**",
        f"Performance probes/model: **{RUNS}**",
        "",
        (
            "> Hard requirements (context/tools/vision/latency and optional "
            "paid price ceilings) gate eligibility before scoring."
        ),
        "",
    ]

    if quota_info:
        lines.extend(
            [
                "## Free quota at start",
                "",
                (
                    f"- used: `{quota_info.get('free_used')}` / "
                    f"`{quota_info.get('free_limit')}`"
                ),
                f"- remaining: `{quota_info.get('free_remaining')}`",
                "",
            ]
        )

    for pool in ("free", "paid"):
        pool_rankings = rankings_by_pool.get(pool) or {}

        lines.extend(
            [
                f"# {pool.upper()} POOL",
                "",
            ]
        )

        if not pool_rankings:
            lines.extend(
                [
                    "_Not tested in this run._",
                    "",
                ]
            )
            continue

        for tier_name, rows in pool_rankings.items():
            lines.extend(
                [
                    f"## {tier_name}",
                    "",
                    (
                        "| # | Model | Score | Eligible | Health | p95 | "
                        "Success | Context | Input $/M | Output $/M | Notes |"
                    ),
                    (
                        "|---:|---|---:|:---:|---|---:|---:|---:|---:|---:|---|"
                    ),
                ]
            )

            for index, row in enumerate(rows[:10], start=1):
                pricing = row.get("pricing_per_million") or {}
                inp = pricing.get("prompt_per_million")
                out = pricing.get("completion_per_million")

                lines.append(
                    "| "
                    + " | ".join(
                        [
                            str(index),
                            f"`{row['model']}`",
                            f"{row['score']:.2f}",
                            "yes" if row["eligible"] else "no",
                            row["status"],
                            fmt_seconds(row["p95"]),
                            f"{row['current_success_rate']:.0%}",
                            f"{row['context_length']:,}",
                            (
                                f"{inp:.4f}"
                                if inp is not None
                                else "-"
                            ),
                            (
                                f"{out:.4f}"
                                if out is not None
                                else "-"
                            ),
                            "; ".join(row["reasons"]) or "—",
                        ]
                    )
                    + " |"
                )

            lines.append("")

    MODEL_RANKINGS_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    # Backward-compatible path.
    RANKINGS_PATH.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_phase2_recommendations_yaml(
    rankings_by_pool: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    lines = [
        f'generated_at: "{NOW_ISO}"',
        'source: "openrouter-live-model-qualification"',
        "tiers:",
    ]

    for tier_name in TIERS:
        lines.append(f"  {tier_name}:")

        for pool, count in (("free", 5), ("paid", 5)):
            rows = (
                rankings_by_pool
                .get(pool, {})
                .get(tier_name, [])
            )

            eligible = [
                row
                for row in rows
                if row["eligible"]
            ][:count]

            lines.append(f"    {pool}:")

            if not eligible:
                lines.append("      candidates: []")
                continue

            lines.append("      candidates:")

            for row in eligible:
                pricing = row.get("pricing_per_million") or {}

                lines.extend(
                    [
                        f'        - model: "{row["model"]}"',
                        f'          score: {row["score"]:.2f}',
                        (
                            "          success_rate: "
                            f"{row['current_success_rate']:.4f}"
                        ),
                        (
                            "          p95_seconds: "
                            f"{row['p95'] if row['p95'] is not None else 'null'}"
                        ),
                        (
                            "          context_length: "
                            f"{row['context_length']}"
                        ),
                        (
                            "          input_per_million: "
                            f"{pricing.get('prompt_per_million') if pricing.get('prompt_per_million') is not None else 'null'}"
                        ),
                        (
                            "          output_per_million: "
                            f"{pricing.get('completion_per_million') if pricing.get('completion_per_million') is not None else 'null'}"
                        ),
                    ]
                )

    RECOMMENDATIONS_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_recommended_routing_yaml(
    rankings_by_pool: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    lines = [
        f'generated_at: "{NOW_ISO}"',
        'source: "openrouter-live-model-qualification"',
        "policy:",
        '  normal: "free -> free backups -> paid -> paid backup -> auto-low"',
        '  free_exhausted: "skip free -> paid -> paid backup -> auto-low"',
        "tiers:",
    ]

    for tier_name in TIERS:
        free_rows = [
            row
            for row in (
                rankings_by_pool
                .get("free", {})
                .get(tier_name, [])
            )
            if row["eligible"]
        ][:3]

        paid_rows = [
            row
            for row in (
                rankings_by_pool
                .get("paid", {})
                .get(tier_name, [])
            )
            if row["eligible"]
        ][:2]

        lines.extend(
            [
                f"  {tier_name}:",
                "    free:",
            ]
        )

        if free_rows:
            for row in free_rows:
                lines.append(
                    f'      - "{row["model"]}"'
                )
        else:
            lines.append("      []")

        lines.append("    paid:")

        if paid_rows:
            for row in paid_rows:
                lines.append(
                    f'      - "{row["model"]}"'
                )
        else:
            lines.append("      []")

        lines.extend(
            [
                "    emergency:",
                '      model: "openrouter/auto"',
                '      cost_tier: "low"',
            ]
        )

    ROUTING_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def print_phase2_rankings(
    rankings_by_pool: dict[str, dict[str, list[dict[str, Any]]]],
) -> None:
    print("\n" + "=" * 120)
    print("TOP MODEL CANDIDATES")
    print("=" * 120)

    for pool in ("free", "paid"):
        rankings = rankings_by_pool.get(pool) or {}

        print(f"\n{'=' * 20} {pool.upper()} {'=' * 20}")

        if not rankings:
            print("  Not tested in this run.")
            continue

        for tier_name, rows in rankings.items():
            eligible = [
                row
                for row in rows
                if row["eligible"]
            ][:3]

            print(f"\n{tier_name}")

            if not eligible:
                print("  No model passed the current contract.")
                continue

            for index, row in enumerate(eligible, start=1):
                pricing = row.get("pricing_per_million") or {}
                cost = ""

                if pool == "paid":
                    cost = (
                        f" $/M={pricing.get('prompt_per_million')}/"
                        f"{pricing.get('completion_per_million')}"
                    )

                print(
                    f"  {index}. "
                    f"{row['model']:<55} "
                    f"score={row['score']:>6.2f} "
                    f"p95={fmt_seconds(row['p95']):>7} "
                    f"success={row['current_success_rate']:.0%}"
                    f"{cost}"
                )


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    global MAX_PAID_INPUT_PER_M
    global MAX_PAID_OUTPUT_PER_M

    args = parse_args()

    MAX_PAID_INPUT_PER_M = max(
        0.0,
        float(args.max_paid_input_per_m),
    )
    MAX_PAID_OUTPUT_PER_M = max(
        0.0,
        float(args.max_paid_output_per_m),
    )

    PAID_REQUEST_PACER.requests_per_minute = max(
        1.0,
        float(args.paid_rpm),
    )
    PAID_REQUEST_PACER.interval_seconds = (
        60.0 / PAID_REQUEST_PACER.requests_per_minute
    )

    mode = (
        "paid-only"
        if args.no_free
        else (
            "free-only"
            if args.no_paid
            else "free+paid"
        )
    )

    headers = {
        "Authorization": (
            f"Bearer {API_KEY}"
        ),
        "Content-Type": (
            "application/json"
        ),
        "HTTP-Referer": (
            "https://localhost"
        ),
        "X-Title": (
            "Hermes OpenRouter Model Qualification"
        ),
    }

    print(
        "OpenRouter FREE + PAID sibling model qualification"
    )
    print("=" * 120)
    print(
        f"mode={mode} "
        f"runs/model={RUNS} "
        f"free_rpm={DISCOVERY_RPM:.1f} "
        f"paid_rpm={PAID_REQUEST_PACER.requests_per_minute:.1f} "
        f"timeout={TIMEOUT:.1f}s"
    )
    print(
        f"free_interval="
        f"{FREE_REQUEST_PACER.interval_seconds:.2f}s "
        f"paid_interval="
        f"{PAID_REQUEST_PACER.interval_seconds:.2f}s"
    )
    print(
        f"paid_price_ceiling="
        f"input=${MAX_PAID_INPUT_PER_M:.3f}/M "
        f"output=${MAX_PAID_OUTPUT_PER_M:.3f}/M "
        f"(0 = disabled)"
    )
    print(f"output={OUTPUT_DIR}")

    history = load_history()

    quota_info: dict[str, Any] | None = None

    with httpx.Client(
        headers=headers,
    ) as client:
        catalog = get_catalog(client)

        free_models = [
            model
            for model in catalog
            if is_chat_candidate(model)
        ]

        free_models.sort(
            key=lambda model: (
                safe_int(model.get("created")),
                str(model.get("id", "")),
            ),
            reverse=True,
        )

        max_models = max(
            0,
            int(args.max_models),
        )

        if max_models:
            free_models = free_models[
                :max_models
            ]

        paid_models, sibling_rows = build_paid_sibling_map(
            free_models,
            catalog,
        )

        write_paid_siblings_yaml(
            sibling_rows
        )

        print(
            f"catalog={len(catalog)} "
            f"free_chat_candidates={len(free_models)} "
            f"exact_paid_siblings={len(paid_models)}"
        )

        test_free = not args.no_free
        test_paid = not args.no_paid

        if test_free:
            try:
                quota_info = get_key_info(client)

                print(
                    "free_quota="
                    f"{quota_info.get('free_used')}/"
                    f"{quota_info.get('free_limit')} "
                    f"remaining="
                    f"{quota_info.get('free_remaining')}"
                )

            except Exception as exc:
                print(
                    "WARNING: could not query /api/v1/key: "
                    f"{type(exc).__name__}: {exc}"
                )

        estimated_free_calls = sum(
            estimate_requests_for_model(model)
            for model in free_models
        )

        if test_free and quota_info:
            remaining = quota_info.get(
                "free_remaining",
                -1,
            )

            if remaining == 0:
                print(
                    "FREE POOL SKIPPED: daily :free quota is exhausted. "
                    "Paid sibling qualification will continue."
                )
                test_free = False

            elif (
                remaining >= 0
                and remaining < estimated_free_calls
                and not args.force_partial_free
            ):
                print(
                    "FREE POOL SKIPPED: remaining free quota is too small for "
                    "an unbiased full run."
                )
                print(
                    f"  estimated calls needed <= {estimated_free_calls}, "
                    f"remaining={remaining}"
                )
                print(
                    "  Re-run after reset, or use --force-partial-free if you "
                    "explicitly want incomplete free results."
                )
                test_free = False

        summaries: list[dict[str, Any]] = []

        selected: list[dict[str, Any]] = []

        if test_free:
            selected.extend(free_models)

        if test_paid:
            selected.extend(paid_models)

        if not selected:
            print(
                "No inference candidates selected. Pairing artifacts were "
                "still generated."
            )

        for index, model in enumerate(
            selected,
            start=1,
        ):
            variant = model.get(
                "_discovery_variant",
                "?",
            )

            print(
                f"\n=== {index}/{len(selected)} "
                f"[{variant.upper()}] "
                f"{model.get('id')} ==="
            )

            summary = evaluate_model(
                client,
                model,
            )

            summaries.append(summary)

            if PROBE_DELAY > 0:
                time.sleep(PROBE_DELAY)

    free_summaries = [
        summary
        for summary in summaries
        if summary.get("variant") == "free"
    ]

    paid_summaries = [
        summary
        for summary in summaries
        if summary.get("variant") == "paid"
    ]

    rankings_by_pool: dict[
        str,
        dict[str, list[dict[str, Any]]],
    ] = {}

    if free_summaries:
        rankings_by_pool["free"] = rank_models(
            free_summaries,
            history,
        )

    if paid_summaries:
        rankings_by_pool["paid"] = rank_models(
            paid_summaries,
            history,
        )

    results = {
        "generated_at": NOW_ISO,
        "mode": mode,
        "runs_per_model": RUNS,
        "catalog_count": len(catalog),
        "free_catalog_count": len(free_models),
        "paid_sibling_count": len(paid_models),
        "models_tested": len(summaries),
        "free_models_tested": len(free_summaries),
        "paid_models_tested": len(paid_summaries),
        "quota_at_start": quota_info,
        "paid_price_ceilings": {
            "input_per_million": MAX_PAID_INPUT_PER_M,
            "output_per_million": MAX_PAID_OUTPUT_PER_M,
        },
        "paid_siblings": sibling_rows,
        "models": summaries,
        "rankings": rankings_by_pool,
    }

    json_dump(
        MODEL_RESULTS_PATH,
        results,
    )

    # Backward-compatible result path.
    json_dump(
        RESULTS_PATH,
        results,
    )

    json_dump(
        CAPABILITIES_PATH,
        {
            "generated_at": NOW_ISO,
            "models": summaries,
        },
    )

    write_phase2_rankings_markdown(
        summaries,
        rankings_by_pool,
        mode,
        quota_info,
    )

    write_phase2_recommendations_yaml(
        rankings_by_pool,
    )

    write_recommended_routing_yaml(
        rankings_by_pool,
    )

    save_history(
        history,
        summaries,
    )

    print_phase2_rankings(
        rankings_by_pool
    )

    print("\n" + "=" * 120)
    print("OUTPUT FILES")
    print("=" * 120)

    for path in (
        MODEL_RESULTS_PATH,
        MODEL_RANKINGS_PATH,
        RECOMMENDATIONS_PATH,
        PAID_SIBLINGS_PATH,
        CAPABILITIES_PATH,
        ROUTING_PATH,
        HISTORY_PATH,
    ):
        print(path)

    print(
        "OpenRouter inference requests sent: "
        f"free={FREE_REQUEST_PACER.request_count} "
        f"paid={PAID_REQUEST_PACER.request_count} "
        f"total="
        f"{FREE_REQUEST_PACER.request_count + PAID_REQUEST_PACER.request_count}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
