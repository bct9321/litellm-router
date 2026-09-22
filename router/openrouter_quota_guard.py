"""
openrouter_quota_guard.py

LiteLLM callback for OpenRouter free-model quota visibility + paid bypass.

Behavior
--------
AVAILABLE / WARNING / CRITICAL:
    Leave free-first aliases unchanged.

EXHAUSTED (or remaining <= OPENROUTER_QUOTA_BLOCK_REMAINING):
    Rewrite known free aliases to paid aliases BEFORE LiteLLM routing.\n    Community LiteLLM allows only one operator-defined auto-router, so\n    exhausted top-level `jev` traffic is routed to the universal paid\n    safety model `paid-general-capable` (DeepSeek V4 Flash).
    Example:
        jev -> paid-general-capable
        free-coding-capable -> paid-coding-capable
        fast -> paid-fast

Concrete :free model IDs with no explicit alias mapping are blocked rather than
blindly stripping ":free", because an exact paid sibling is not guaranteed.

Environment
-----------
OPENROUTER_API_KEY                         required
OPENROUTER_QUOTA_CACHE_SECONDS=30
OPENROUTER_QUOTA_WARN_PERCENT=80
OPENROUTER_QUOTA_CRITICAL_PERCENT=90
OPENROUTER_QUOTA_BLOCK_REMAINING=0
OPENROUTER_QUOTA_FAIL_OPEN=true
OPENROUTER_QUOTA_EXHAUSTED_ACTION=route    # route | block

If BLOCK_REMAINING=25, the final 25 free calls are effectively reserved and
normal traffic switches to paid early.

Response headers
----------------
x-openrouter-free-used
x-openrouter-free-limit
x-openrouter-free-remaining
x-openrouter-free-percent
x-openrouter-free-status
x-openrouter-quota-cache-age
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from litellm.integrations.custom_logger import CustomLogger


OPENROUTER_KEY_URL = os.getenv("OPENROUTER_KEY_URL", "https://openrouter.ai/api/v1/key")

DEFAULT_ROUTE_MAP = {
    "jev": "paid-general-capable",
    "free-general-efficient": "paid-general-efficient",
    "free-general-efficient-backup": "paid-general-efficient-backup",
    "free-general-capable": "paid-general-capable",
    "free-general-capable-backup": "paid-general-capable-backup",
    "free-reasoning-efficient": "paid-reasoning-efficient",
    "free-reasoning-efficient-backup": "paid-reasoning-efficient-backup",
    "free-reasoning-capable": "paid-reasoning-capable",
    "free-reasoning-capable-backup": "paid-reasoning-capable-backup",
    "free-agentic-efficient": "paid-agentic-efficient",
    "free-agentic-efficient-backup": "paid-agentic-efficient-backup",
    "free-agentic-capable": "paid-agentic-capable",
    "free-agentic-capable-backup": "paid-agentic-capable-backup",
    "free-coding-efficient": "paid-coding-efficient",
    "free-coding-efficient-backup": "paid-coding-efficient-backup",
    "free-coding-capable": "paid-coding-capable",
    "free-coding-capable-backup": "paid-coding-capable-backup",
    "fast": "paid-fast",
    "fast-backup": "paid-fast-backup",
    "vision": "paid-vision",
    "vision-backup": "paid-vision-backup",
    "compression": "paid-compression",
    "compression-backup": "paid-compression-backup",
    "free-emergency-capable": "paid-emergency",
    "openrouter/free": "paid-emergency"
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class QuotaSnapshot:
    # Plain class: avoids Python 3.13 dataclass/importlib callback-loader issue.
    def __init__(
        self,
        used: int,
        limit: int,
        remaining: int,
        fetched_at: float,
    ) -> None:
        self.used = used
        self.limit = limit
        self.remaining = remaining
        self.fetched_at = fetched_at

    @property
    def percent_used(self) -> float:
        if self.limit <= 0:
            return 0.0
        return min(
            100.0,
            max(0.0, (self.used / self.limit) * 100.0),
        )


class OpenRouterQuotaGuard(CustomLogger):

    def __init__(self) -> None:
        super().__init__()

        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.cache_seconds = max(
            5.0,
            _env_float("OPENROUTER_QUOTA_CACHE_SECONDS", 30.0),
        )
        self.warn_percent = _env_float(
            "OPENROUTER_QUOTA_WARN_PERCENT", 80.0
        )
        self.critical_percent = _env_float(
            "OPENROUTER_QUOTA_CRITICAL_PERCENT", 90.0
        )
        self.block_remaining = max(
            0,
            _env_int("OPENROUTER_QUOTA_BLOCK_REMAINING", 0),
        )
        self.fail_open = _env_bool(
            "OPENROUTER_QUOTA_FAIL_OPEN", True
        )
        self.exhausted_action = os.getenv(
            "OPENROUTER_QUOTA_EXHAUSTED_ACTION",
            "route",
        ).strip().lower()

        if self.exhausted_action not in {"route", "block"}:
            self.exhausted_action = "route"

        self.route_map = dict(DEFAULT_ROUTE_MAP)
        try:
            configured_routes = json.loads(os.getenv('OPENROUTER_QUOTA_ROUTE_MAP', '{}'))
            if isinstance(configured_routes, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in configured_routes.items()):
                self.route_map.update(configured_routes)
        except (TypeError, ValueError):
            pass
        self.free_aliases = set(self.route_map)

        self._snapshot: Optional[QuotaSnapshot] = None
        self._next_refresh_at = 0.0
        self._lock = asyncio.Lock()
        self._last_logged_status: Optional[str] = None

        print(
            "[OPENROUTER QUOTA] callback initialized "
            f"cache={self.cache_seconds:.0f}s "
            f"warn={self.warn_percent:.0f}% "
            f"critical={self.critical_percent:.0f}% "
            f"block_remaining={self.block_remaining} "
            f"action={self.exhausted_action} "
            f"routes={len(self.route_map)} "
            f"fail_open={self.fail_open}",
            flush=True,
        )

    def _is_free_request(self, data: dict[str, Any]) -> bool:
        model = str(data.get("model", "")).strip()

        if not model:
            return False

        return (
            model.endswith(":free")
            or model in self.free_aliases
        )

    def _snapshot_is_fresh(self) -> bool:
        if self._snapshot is None:
            return False

        return (
            time.monotonic() - self._snapshot.fetched_at
            < self.cache_seconds
        )

    async def _refresh_snapshot(self) -> Optional[QuotaSnapshot]:
        if not self.api_key:
            print(
                "[OPENROUTER QUOTA] OPENROUTER_API_KEY missing",
                flush=True,
            )
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                OPENROUTER_KEY_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
            )

        response.raise_for_status()

        data = response.json().get("data", {})
        quota = data.get("free_model_daily_requests")

        if not isinstance(quota, dict):
            print(
                "[OPENROUTER QUOTA] free_model_daily_requests missing",
                flush=True,
            )
            return None

        used = quota.get("used")
        limit = quota.get("limit")
        remaining = quota.get("remaining")

        if (any(type(value) is not int or value < 0 for value in (used, limit, remaining))
                or used > limit or remaining != limit - used):
            print(
                "[OPENROUTER QUOTA] invalid quota counts",
                flush=True,
            )
            return None

        snapshot = QuotaSnapshot(
            used=int(used),
            limit=int(limit),
            remaining=int(remaining),
            fetched_at=time.monotonic(),
        )

        self._snapshot = snapshot
        self._log_status_transition(snapshot)
        return snapshot

    async def _get_snapshot(
        self,
        force: bool = False,
    ) -> Optional[QuotaSnapshot]:
        if not force and self._snapshot_is_fresh():
            return self._snapshot

        async with self._lock:
            if not force and self._snapshot_is_fresh():
                return self._snapshot

            # Failed/missing refreshes are cached too. Never label stale values
            # as current or let repeated requests hammer an unavailable endpoint.
            if time.monotonic() < self._next_refresh_at:
                return None
            self._next_refresh_at = time.monotonic() + self.cache_seconds

            try:
                refreshed = await self._refresh_snapshot()
                if refreshed is not None:
                    return refreshed
            except Exception as exc:
                print(
                    "[OPENROUTER QUOTA] quota fetch failed: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            return None

    def _status(
        self,
        snapshot: Optional[QuotaSnapshot],
    ) -> str:
        if snapshot is None:
            return "unknown"

        if snapshot.remaining <= self.block_remaining:
            return "exhausted"

        if snapshot.percent_used >= self.critical_percent:
            return "critical"

        if snapshot.percent_used >= self.warn_percent:
            return "warning"

        return "ok"

    def _log_status_transition(
        self,
        snapshot: QuotaSnapshot,
    ) -> None:
        status = self._status(snapshot)

        if status == self._last_logged_status:
            return

        self._last_logged_status = status

        print(
            "[OPENROUTER QUOTA] "
            f"{status.upper()}: "
            f"used={snapshot.used}/{snapshot.limit} "
            f"remaining={snapshot.remaining} "
            f"percent={snapshot.percent_used:.1f}%",
            flush=True,
        )

    def _blocked_error(
        self,
        snapshot: QuotaSnapshot,
        model: str,
    ) -> HTTPException:
        return HTTPException(
            status_code=429,
            detail={
                "error": (
                    "OpenRouter free-model daily quota exhausted/reserved "
                    "and no paid alias rewrite is available."
                ),
                "model": model,
                "used": snapshot.used,
                "limit": snapshot.limit,
                "remaining": snapshot.remaining,
                "percent_used": round(snapshot.percent_used, 1),
                "quota_status": "exhausted",
            },
        )

    async def async_pre_call_hook(
        self,
        user_api_key_dict,
        cache,
        data: dict,
        call_type,
        **kwargs,
    ):
        if not self._is_free_request(data):
            return data

        snapshot = await self._get_snapshot()

        if snapshot is None:
            if self.fail_open:
                return data

            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Could not verify OpenRouter free quota.",
                    "quota_status": "unknown",
                },
            )

        if self._status(snapshot) != "exhausted":
            return data

        original_model = str(data.get("model", "")).strip()

        if self.exhausted_action == "route":
            paid_model = self.route_map.get(original_model)

            if paid_model:
                if os.getenv('COST_ROUTER_CONFIG'):
                    from router.cost_transport import mark_quota_unavailable
                    mark_quota_unavailable(data.get('metadata'))
                data["model"] = paid_model

                print(
                    "[OPENROUTER QUOTA] REROUTE "
                    f"{original_model} -> {paid_model} "
                    f"(remaining={snapshot.remaining})",
                    flush=True,
                )

                return data

        print(
            "[OPENROUTER QUOTA] BLOCKED "
            f"model={original_model} "
            f"remaining={snapshot.remaining}",
            flush=True,
        )

        raise self._blocked_error(snapshot, original_model)

    async def async_post_call_response_headers_hook(
        self,
        data: dict,
        user_api_key_dict,
        response: Any,
        request_headers=None,
        **kwargs,
    ):
        snapshot = await self._get_snapshot()

        if snapshot is None:
            return {
                "x-openrouter-free-status": "unknown",
            }

        age = max(
            0.0,
            time.monotonic() - snapshot.fetched_at,
        )

        return {
            "x-openrouter-free-used": str(snapshot.used),
            "x-openrouter-free-limit": str(snapshot.limit),
            "x-openrouter-free-remaining": str(snapshot.remaining),
            "x-openrouter-free-percent": f"{snapshot.percent_used:.1f}",
            "x-openrouter-free-status": self._status(snapshot),
            "x-openrouter-quota-cache-age": f"{age:.1f}",
        }


proxy_handler_instance = OpenRouterQuotaGuard()
