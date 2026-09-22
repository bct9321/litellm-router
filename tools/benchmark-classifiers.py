#!/usr/bin/env python3

"""
benchmark-classifiers.py

Benchmark routing classifiers for the Hermes/LiteLLM 8-tier router.

Measures:
    - Classification accuracy
    - Average latency
    - Median latency
    - P95 latency
    - Min / max latency
    - Error rate
    - API-reported cost when available

Each test case is executed RUNS times per classifier.

Default:
    RUNS=3

Requires:
    OPENROUTER_API_KEY
    OPENAI_API_KEY

Run inside LiteLLM container:
    docker exec LiteLLM python /tmp/benchmark-classifiers.py

Optional:
    CLASSIFIER_BENCH_RUNS=5
    CLASSIFIER_FREE_RPM=18

Rate limiting:
    Direct OpenRouter models ending in :free and LiteLLM aliases beginning
    with free- share one global free-model pacer. Current non-free classifier
    models are not artificially slowed.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx


# =============================================================================
# CONFIG
# =============================================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
LITELLM_URL = os.getenv(
    "LITELLM_URL",
    "http://127.0.0.1:4000",
).rstrip("/")

if not OPENROUTER_API_KEY:
    print("ERROR: OPENROUTER_API_KEY is not set.")
    print("It is used only for the direct Jev Decisions API benchmark.")
    sys.exit(2)

if not LITELLM_API_KEY:
    print("ERROR: LITELLM_API_KEY is not set.")
    sys.exit(2)


RUNS = int(os.getenv("CLASSIFIER_BENCH_RUNS", "3"))

TIMEOUT = float(os.getenv("CLASSIFIER_BENCH_TIMEOUT", "30"))

# Used only for concrete OpenRouter :free classifier models or obvious LiteLLM
# free aliases. This does not pace Jev Decisions or paid/non-free classifiers.
FREE_RPM = min(
    19.0,
    max(
        1.0,
        float(
            os.getenv(
                "CLASSIFIER_FREE_RPM",
                "18",
            )
        ),
    ),
)

JEV_MODEL = os.getenv(
    "JEV_MODEL",
    "typesafe/jev-1.13",
)


OPENAI_LUNA_MODEL = os.getenv(
    "OPENAI_LUNA_MODEL",
    "openai/gpt-5.6-luna",
)

OPENROUTER_LUNA_MODEL = os.getenv(
    "OPENROUTER_LUNA_MODEL",
    "openrouter/openai/gpt-5.6-luna",
)


# =============================================================================
# MODELS TO TEST
# =============================================================================
#
# Jev uses the Decisions API.
#
# Everything else uses normal OpenRouter chat completion with the SAME
# classification rubric.
#
# Add/remove models freely.
# =============================================================================

CHAT_MODELS = [
    "openrouter/google/gemini-3.1-flash-lite",
    "openrouter/qwen/qwen3.5-9b",

    # Luna through OpenRouter via LiteLLM:
    "openrouter/openai/gpt-5.6-luna",
]


# =============================================================================
# ROUTING TIERS
# =============================================================================

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


TIER_DESCRIPTIONS = {
    "GENERAL_EFFICIENT":
        "Routine general-purpose work: simple writing, summarization, "
        "questions, formatting, extraction, or uncomplicated research.",

    "GENERAL_CAPABLE":
        "Difficult general-purpose work requiring stronger understanding, "
        "synthesis, ambiguity handling, or nuanced responses.",

    "REASONING_EFFICIENT":
        "Straightforward reasoning, review, analysis, planning, comparison, "
        "or diagnosis that does not require implementation.",

    "REASONING_CAPABLE":
        "Deep reasoning, architecture, difficult planning, high uncertainty, "
        "complex tradeoffs, or substantial analytical depth.",

    "AGENTIC_EFFICIENT":
        "Short and obvious workflows involving tools, MCP, external actions, "
        "or a small number of predictable steps.",

    "AGENTIC_CAPABLE":
        "Complex orchestration, delegation, branching workflows, multi-agent "
        "coordination, Kanban/project execution, or long tool chains.",

    "CODING_EFFICIENT":
        "Localized software implementation, small bug fixes, tests, edits, "
        "bounded refactors, or simple repository changes.",

    "CODING_CAPABLE":
        "Hard debugging, architecture-level implementation, distributed "
        "systems, cross-file changes, difficult refactors, concurrency, "
        "or major engineering work.",
}


# =============================================================================
# TEST DATA
# =============================================================================
#
# Two cases for each tier = 16 cases.
#
# These are deliberately closer to actual Hermes tasks than generic
# classification benchmark prompts.
# =============================================================================


@dataclass
class TestCase:
    name: str
    expected: str
    system: str
    user: str


TESTS = [

    # =========================================================================
    # GENERAL_EFFICIENT
    # =========================================================================

    TestCase(
        name="rewrite_short",
        expected="GENERAL_EFFICIENT",
        system="You are a general-purpose assistant.",
        user=(
            "Rewrite this sentence to sound more professional: "
            "'hey just checking if you got the file'"
        ),
    ),

    TestCase(
        name="summarize_short",
        expected="GENERAL_EFFICIENT",
        system="You are a general-purpose assistant.",
        user=(
            "Summarize this in one sentence: "
            "The deployment succeeded Monday. Monitoring showed no errors. "
            "CPU utilization remained below 40 percent."
        ),
    ),

    # =========================================================================
    # GENERAL_CAPABLE
    # =========================================================================

    TestCase(
        name="synthesis_ambiguous",
        expected="GENERAL_CAPABLE",
        system="You are a senior technical assistant.",
        user=(
            "I have conflicting feedback from engineering, product, and "
            "support about whether to delay a launch. Synthesize the concerns "
            "into a neutral decision memo identifying agreements, conflicts, "
            "unknowns, and what evidence would resolve them."
        ),
    ),

    TestCase(
        name="complex_research_summary",
        expected="GENERAL_CAPABLE",
        system="You are a research assistant.",
        user=(
            "Compare three competing approaches to enterprise knowledge "
            "management and synthesize their tradeoffs for an executive "
            "audience. Account for security, adoption, maintenance, and cost."
        ),
    ),

    # =========================================================================
    # REASONING_EFFICIENT
    # =========================================================================

    TestCase(
        name="simple_tradeoff",
        expected="REASONING_EFFICIENT",
        system="You are a software architecture advisor.",
        user=(
            "Compare REST and GraphQL for a small internal CRUD application "
            "with five developers. Explain the tradeoffs and recommend what "
            "factors the team should evaluate. Do not implement anything."
        ),
    ),

    TestCase(
        name="review_design",
        expected="REASONING_EFFICIENT",
        system="You review technical designs but do not write code.",
        user=(
            "Review this design: API -> Redis cache -> PostgreSQL. "
            "Traffic is low and data changes hourly. Identify obvious risks "
            "and unnecessary complexity."
        ),
    ),

    # =========================================================================
    # REASONING_CAPABLE
    # =========================================================================

    TestCase(
        name="distributed_architecture",
        expected="REASONING_CAPABLE",
        system="You are a senior software architect.",
        user=(
            "Design the architecture for an event-driven multi-region system "
            "that must tolerate regional failure while preserving ordering "
            "for individual entities. Analyze consistency, availability, "
            "partitioning, replay semantics, and failure recovery. "
            "Do not write implementation code."
        ),
    ),

    TestCase(
        name="migration_strategy",
        expected="REASONING_CAPABLE",
        system="You are the Hermes Planner profile.",
        user=(
            "Develop a migration strategy from a tightly coupled monolith to "
            "event-driven services without downtime. Identify dependency "
            "boundaries, sequencing constraints, rollback points, dual-write "
            "risks, observability requirements, and verification gates."
        ),
    ),

    # =========================================================================
    # AGENTIC_EFFICIENT
    # =========================================================================

    TestCase(
        name="simple_tool_workflow",
        expected="AGENTIC_EFFICIENT",
        system=(
            "You are an agent that can use GitHub and terminal tools."
        ),
        user=(
            "Open issue #142, read the latest comment, then check whether "
            "the referenced file exists in the repository."
        ),
    ),

    TestCase(
        name="simple_mcp",
        expected="AGENTIC_EFFICIENT",
        system=(
            "You are an assistant with MCP tools for documentation search."
        ),
        user=(
            "Use the documentation MCP to find the current configuration "
            "option for enabling JSON logging and report its name."
        ),
    ),

    # =========================================================================
    # AGENTIC_CAPABLE
    # =========================================================================

    TestCase(
        name="kanban_orchestration",
        expected="AGENTIC_CAPABLE",
        system="You are the Hermes Orchestrator profile.",
        user=(
            "Review the Kanban board, identify blocked and stale work, "
            "prioritize the remaining cards, delegate appropriate tasks to "
            "Planner, Worker, Researcher, and Reviewer agents, monitor their "
            "results, handle failures, and continue until the release goal "
            "is complete."
        ),
    ),

    TestCase(
        name="multi_agent_research",
        expected="AGENTIC_CAPABLE",
        system=(
            "You orchestrate multiple specialized agents and external tools."
        ),
        user=(
            "Coordinate researcher, planner, implementation, and reviewer "
            "agents to investigate three competing libraries, inspect our "
            "repository, choose an integration strategy, implement it, run "
            "tests, review the change, and correct failures before finishing."
        ),
    ),

    # =========================================================================
    # CODING_EFFICIENT
    # =========================================================================

    TestCase(
        name="small_bugfix",
        expected="CODING_EFFICIENT",
        system=(
            "You are the Hermes Worker profile. "
            "You perform software implementation."
        ),
        user=(
            "Fix the Python validation function so it rejects empty email "
            "addresses, and add two unit tests covering empty and valid input."
        ),
    ),

    TestCase(
        name="bounded_refactor",
        expected="CODING_EFFICIENT",
        system="You are a software implementation agent.",
        user=(
            "Refactor this single module to extract the duplicated date "
            "formatting logic into one helper function and update its tests."
        ),
    ),

    # =========================================================================
    # CODING_CAPABLE
    # =========================================================================

    TestCase(
        name="distributed_race",
        expected="CODING_CAPABLE",
        system=(
            "You are the Hermes Worker profile. You perform software "
            "implementation, repository edits, debugging, TDD, tests, "
            "and terminal engineering tasks."
        ),
        user=(
            "Debug and implement a robust fix for an intermittent distributed "
            "race involving Kafka duplicate delivery, Redis locks, PostgreSQL "
            "transactions, and multiple workers. Include tests."
        ),
    ),

    TestCase(
        name="cross_file_architecture_change",
        expected="CODING_CAPABLE",
        system="You are a senior implementation agent.",
        user=(
            "Implement a new transactional outbox architecture across the "
            "repository. Update persistence models, migrations, service "
            "boundaries, event publishing, retry handling, integration tests, "
            "and existing callers without breaking backward compatibility."
        ),
    ),
]


# =============================================================================
# PROMPT
# =============================================================================


def classifier_prompt(system_text: str, user_text: str) -> str:

    tier_text = "\n".join(
        f"- {tier}: {TIER_DESCRIPTIONS[tier]}"
        for tier in TIERS
    )

    return f"""
Classify the following request into exactly ONE routing tier.

ROUTING RULES

CODING:
Use CODING when software must be implemented, modified, debugged,
tested, refactored, or changed in a repository.

AGENTIC:
Use AGENTIC when the primary task involves tools, MCP, orchestration,
delegation, multi-agent coordination, Kanban execution, or workflows.

REASONING:
Use REASONING for planning, architecture, review, diagnosis, or
analysis when implementation is not the primary task.

GENERAL:
Use GENERAL for conversation, writing, summarization, extraction,
research synthesis, and other general-purpose work.

STRENGTH

EFFICIENT:
Routine, bounded, obvious, low-risk work.

CAPABLE:
Complex, ambiguous, multi-step, high-risk, cross-system, or deep work.

IMPORTANT:
If actual software implementation or modification is requested,
CODING wins over REASONING.

TIERS

{tier_text}

SYSTEM / PROFILE CONTEXT:
{system_text}

USER REQUEST:
{user_text}

Return ONLY one exact tier name.
""".strip()


# =============================================================================
# HELPERS
# =============================================================================


def percentile(values: list[float], pct: float) -> float:

    if not values:
        return 0.0

    ordered = sorted(values)

    index = (len(ordered) - 1) * pct

    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)

    fraction = index - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def normalize_tier(value: Any) -> str | None:

    if value is None:
        return None

    text = str(value).strip().upper()

    # Exact match
    if text in TIERS:
        return text

    # Some models wrap answer in punctuation / JSON / prose.
    for tier in TIERS:
        if tier in text:
            return tier

    return None


def get_cost(data: dict[str, Any]) -> float | None:

    usage = data.get("usage") or {}

    cost = usage.get("cost") if isinstance(usage, dict) else None

    if cost is None or isinstance(cost, bool):
        return None

    try:
        value = float(cost)
        return value if math.isfinite(value) and value >= 0 else None
    except (TypeError, ValueError):
        return None


def response_cost(response: httpx.Response) -> float | None:
    try:
        data = response.json()
        provider_cost = get_cost(data) if isinstance(data, dict) else None
        if provider_cost is not None:
            return provider_cost
    except ValueError:
        pass
    return get_cost({'usage': {'cost': response.headers.get('x-litellm-response-cost')}})


# =============================================================================
# OPTIONAL FREE-MODEL PACER
# =============================================================================

class GlobalRequestPacer:
    """
    Shared pacer for OpenRouter free-model classifier requests.

    The current benchmark defaults are paid/non-free chat classifiers, so they
    are not paced. If a future CHAT_MODELS entry contains ':free', or a
    LiteLLM classifier alias starts with 'free-', the request uses this pacer.
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
        self.next_request_at = (
            now + self.interval_seconds
        )
        self.request_count += 1


FREE_REQUEST_PACER = GlobalRequestPacer(
    FREE_RPM
)


def is_obvious_free_model(model: str) -> bool:
    """
    Detect models/aliases that clearly consume OpenRouter's :free quota.

    Concrete OpenRouter free slug:
        openrouter/foo/bar:free
        foo/bar:free

    LiteLLM free alias:
        free-something
    """
    value = model.lower().strip()

    return (
        value.endswith(":free")
        or ":free/" in value
        or value.startswith("free-")
    )


def pace_if_free(model: str) -> None:
    if is_obvious_free_model(model):
        FREE_REQUEST_PACER.wait()


# =============================================================================
# JEV
# =============================================================================


def classify_jev(client: httpx.Client, test: TestCase) -> dict[str, Any]:
    """Evaluate the production classifier including its transcript and failures."""
    import asyncio
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from router.jev_classifier import OpenRouterJevClassifier

    diagnostics: dict[str, Any] = {}
    started = time.perf_counter()
    prediction = asyncio.run(OpenRouterJevClassifier().classify(
        {"raw_messages": [{"role": "system", "content": test.system},
                          {"role": "user", "content": test.user}]},
        diagnostics=diagnostics,
    ))
    return {**diagnostics, "latency": time.perf_counter() - started,
            "prediction": prediction if diagnostics["ok"] else None,
            "error": None if diagnostics["ok"] else "production classifier fallback"}


# =============================================================================
# NORMAL CHAT MODEL
# =============================================================================


def classify_chat(
    client: httpx.Client,
    model: str,
    test: TestCase,
) -> dict[str, Any]:

    prompt = classifier_prompt(
        test.system,
        test.user,
    )

    payload = {
        "model": model,

        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],

        "temperature": 0,

        # Routing should not require a long completion.
        "max_tokens": 32,

        # Ask OpenRouter to return usage/cost data.
        "usage": {
            "include": True,
        },

        # Classification does not need reasoning-token generation.
        "reasoning": {
            "enabled": False,
        },
    }

    # Only :free classifiers need the OpenRouter free-model pacer.
    # Pace BEFORE latency timing so the benchmark measures classifier latency,
    # not test-infrastructure sleep.
    pace_if_free(model)

    started = time.perf_counter()

    response = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        timeout=TIMEOUT,
    )

    latency = time.perf_counter() - started

    if response.status_code != 200:

        return {
            "ok": False,
            "latency": latency,
            "prediction": None,
            "cost": response_cost(response),
            "error": (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            ),
        }

    data = response.json()

    try:
        content = (
            data["choices"][0]
            ["message"]
            .get("content")
        )
    except Exception:
        content = None

    prediction = normalize_tier(content)

    return {
        "ok": prediction is not None,
        "latency": latency,
        "prediction": prediction,
        "cost": get_cost(data),
        "provider": data.get("provider"),
        "error": None if prediction else str(content),
    }


# =============================================================================
# LUNA VIA LITELLM
# =============================================================================


def classify_litellm_chat(
    client: httpx.Client,
    model: str,
    test: TestCase,
) -> dict[str, Any]:
    """
    Classify with a normal chat model through LiteLLM.

    This is used for:
        - OpenAI Luna via LiteLLM/OpenAI
        - OpenRouter Luna via LiteLLM/OpenRouter
        - Gemini via LiteLLM/OpenRouter
        - Qwen via LiteLLM/OpenRouter

    Provider API keys remain inside LiteLLM.
    """

    prompt = classifier_prompt(
        test.system,
        test.user,
    )

    payload = {
        "model": model,

        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],

        "temperature": 0,
        "max_tokens": 32,

        # Luna supports no-reasoning classification mode.
        # LiteLLM's drop_params=true will remove unsupported params for
        # models/providers that do not accept this field.
        "reasoning_effort": "none",
    }

    # Pace obvious free aliases/models only. Current Luna/Gemini/Qwen
    # classifier defaults are non-free and remain unpaced.
    pace_if_free(model)

    started = time.perf_counter()

    response = client.post(
        f"{LITELLM_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {LITELLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=TIMEOUT,
    )

    latency = time.perf_counter() - started

    if response.status_code != 200:

        return {
            "ok": False,
            "latency": latency,
            "prediction": None,
            "cost": response_cost(response),
            "provider": None,
            "error": (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            ),
        }

    data = response.json()

    try:
        content = (
            data["choices"][0]
            ["message"]
            .get("content")
        )
    except Exception:
        content = None

    prediction = normalize_tier(
        content
    )

    # LiteLLM normally exposes computed request cost as a response header.
    cost = response.headers.get("x-litellm-response-cost")
    
    # Fall back to usage.cost if a provider happens to include it in the body.
    if cost is None:
        usage = data.get("usage") or {}
        cost = usage.get("cost")
    
    try:
        cost = (
            float(cost)
            if cost is not None
            else None
        )
    except (TypeError, ValueError):
        cost = None

    return {
        "ok": prediction is not None,
        "latency": latency,
        "prediction": prediction,
        "cost": cost,
        "provider": data.get("provider"),
        "error": (
            None
            if prediction
            else str(content)[:300]
        ),
    }


# =============================================================================
# BENCHMARK
# =============================================================================


def benchmark_classifier(
    client: httpx.Client,
    name: str,
    classifier_type: str,
) -> dict[str, Any]:

    print()
    print("=" * 100)
    print(name)
    print("=" * 100)

    results = []

    total_tests = len(TESTS) * RUNS

    current = 0

    for test in TESTS:

        for run in range(1, RUNS + 1):

            current += 1

            if classifier_type == "jev":

                result = classify_jev(
                    client,
                    test,
                )

            elif classifier_type == "litellm":

                result = classify_litellm_chat(
                    client,
                    name,
                    test,
                )

            else:

                result = classify_chat(
                    client,
                    name,
                    test,
                )

            correct = (
                result["prediction"]
                == test.expected
            )

            result.update({
                "test": test.name,
                "expected": test.expected,
                "correct": correct,
                "run": run,
            })

            results.append(result)

            prediction = (
                result["prediction"]
                or "ERROR"
            )

            symbol = (
                "✅"
                if correct
                else "❌"
            )

            print(
                f"{symbol} "
                f"{current:02}/{total_tests} "
                f"{test.name:<30} "
                f"run={run} "
                f"{result['latency']:>6.3f}s "
                f"expected={test.expected:<21} "
                f"got={prediction}"
            )

            if result.get("error"):

                print(
                    f"     error: "
                    f"{result['error']}"
                )

    return summarize(
        name,
        results,
    )


# =============================================================================
# SUMMARY
# =============================================================================


def summarize(
    name: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:

    successful = [
        x
        for x in results
        if x["ok"]
    ]

    correct = [
        x
        for x in results
        if x["correct"]
    ]

    latencies = [
        x["latency"]
        for x in successful
    ]

    costs = [
        x["cost"]
        for x in results
        if x.get("cost") is not None
        and isinstance(x["cost"], (int, float))
        and not isinstance(x["cost"], bool)
        and math.isfinite(x["cost"])
        and x["cost"] >= 0
    ]

    total = len(results)

    accuracy = (
        len(correct) / total
        if total
        else 0
    )

    error_count = (
        total - len(successful)
    )

    summary = {
        "name": name,
        "requests": total,
        "successful": len(successful),
        "errors": error_count,
        "accuracy": accuracy,

        "avg_latency": (
            statistics.mean(latencies)
            if latencies
            else 0
        ),

        "median_latency": (
            statistics.median(latencies)
            if latencies
            else 0
        ),

        "p95_latency": (
            percentile(latencies, 0.95)
            if latencies
            else 0
        ),

        "min_latency": (
            min(latencies)
            if latencies
            else 0
        ),

        "max_latency": (
            max(latencies)
            if latencies
            else 0
        ),

        "total_cost": (
            sum(costs)
            if costs and len(costs) == total
            else None
        ),

        "known_cost": sum(costs) if costs else None,
        "unknown_cost_requests": total - len(costs),
        "cost_coverage": len(costs) / total if total else None,

        "avg_cost": (
            statistics.mean(costs)
            if costs and len(costs) == total
            else None
        ),
    }

    return summary


# =============================================================================
# FINAL TABLE
# =============================================================================


def print_final_table(
    summaries: list[dict[str, Any]],
) -> None:

    print()
    print()
    print("=" * 125)
    print("FINAL RESULTS")
    print("=" * 125)

    print(
        f"{'CLASSIFIER':<38}"
        f"{'ACC':>8}"
        f"{'AVG':>10}"
        f"{'P50':>10}"
        f"{'P95':>10}"
        f"{'MIN':>10}"
        f"{'MAX':>10}"
        f"{'ERR':>7}"
        f"{'COST':>14}"
    )

    print("-" * 125)

    for s in summaries:

        cost = (
            f"${s['total_cost']:.6f}"
            if s["total_cost"] is not None
            else "n/a"
        )

        print(
            f"{s['name']:<38}"
            f"{s['accuracy'] * 100:>7.1f}%"
            f"{s['avg_latency']:>9.3f}s"
            f"{s['median_latency']:>9.3f}s"
            f"{s['p95_latency']:>9.3f}s"
            f"{s['min_latency']:>9.3f}s"
            f"{s['max_latency']:>9.3f}s"
            f"{s['errors']:>7}"
            f"{cost:>14}"
        )

    print("=" * 125)

    print()
    print(
        f"Runs per test:       {RUNS}"
    )

    print(
        f"Test cases:          {len(TESTS)}"
    )

    print(
        f"Requests/classifier: {len(TESTS) * RUNS}"
    )

    print()

    print(
        "NOTE: Jev's alpha Decisions API may not expose usage.cost. "
        "If COST shows n/a for Jev, check OpenRouter Activity for the "
        "exact spend generated by this benchmark."
    )

    if FREE_REQUEST_PACER.request_count:
        print(
            f"Free-model classifier requests paced: "
            f"{FREE_REQUEST_PACER.request_count} "
            f"at {FREE_RPM:.1f} RPM"
        )


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:

    print()
    print("Hermes Classifier Benchmark")
    print("===========================")

    print()
    print(
        f"Runs per case: {RUNS}"
    )

    print(
        f"Cases:         {len(TESTS)}"
    )

    print(
        f"Jev:           {JEV_MODEL}"
    )

    print(
        f"LiteLLM URL:    {LITELLM_URL}"
    )

    print(
        f"OpenAI Luna:    {OPENAI_LUNA_MODEL}"
    )

    print(
        f"OpenRouter Luna:{OPENROUTER_LUNA_MODEL}"
    )

    print(
        "Other OpenRouter models:"
    )

    for model in CHAT_MODELS:
        print(
            f"  - {model}"
        )

    headers = {
        "Authorization": (
            f"Bearer {OPENROUTER_API_KEY}"
        ),
        "Content-Type": "application/json",
    }

    summaries = []

    with httpx.Client(
        headers=headers,
    ) as client:

        # ---------------------------------------------------------------------
        # Jev
        # ---------------------------------------------------------------------

        summaries.append(
            benchmark_classifier(
                client,
                JEV_MODEL,
                "jev",
            )
        )

        # ---------------------------------------------------------------------
        # OpenAI Luna through LiteLLM -> OpenAI
        # ---------------------------------------------------------------------

        summaries.append(
            benchmark_classifier(
                client,
                OPENAI_LUNA_MODEL,
                "litellm",
            )
        )

        # ---------------------------------------------------------------------
        # OpenRouter-backed chat classifiers through LiteLLM
        # ---------------------------------------------------------------------

        for model in CHAT_MODELS:

            summaries.append(
                benchmark_classifier(
                    client,
                    model,
                    "litellm",
                )
            )

    print_final_table(
        summaries
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
