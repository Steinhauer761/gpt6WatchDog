from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from rate_limit import FixedWindowRateLimiter, RateLimitResult


@dataclass(frozen=True)
class WindowLimit:
    name: str
    requests: int
    seconds: int


WORKER_RATE_LIMITER = FixedWindowRateLimiter()

ROUTE_LIMITS: dict[tuple[str, str], tuple[WindowLimit, ...]] = {
    ("GET", "/v1/capabilities"): (WindowLimit("worker-capabilities-minute", 60, 60),),
    ("POST", "/v1/triage/text"): (WindowLimit("worker-triage-minute", 120, 60),),
    ("POST", "/v1/crawl/site"): (WindowLimit("worker-crawl-hour", 20, 60 * 60), WindowLimit("worker-crawl-daily", 60, 24 * 60 * 60)),
    ("POST", "/v1/osint/search"): (WindowLimit("worker-osint-hour", 60, 60 * 60),),
    ("POST", "/v1/tor/search"): (WindowLimit("worker-tor-search-hour", 30, 60 * 60),),
    ("POST", "/v1/tor/fetch"): (WindowLimit("worker-tor-fetch-hour", 20, 60 * 60),),
    ("POST", "/v1/intel/ip"): (WindowLimit("worker-ip-hour", 120, 60 * 60),),
    ("POST", "/v1/probe/network"): (WindowLimit("worker-network-probe-hour", 30, 60 * 60),),
    ("POST", "/v1/probe/web-security"): (WindowLimit("worker-web-probe-hour", 60, 60 * 60),),
    ("POST", "/v1/jobs/validate"): (WindowLimit("worker-job-validation-minute", 120, 60),),
}


def _headers(result: RateLimitResult) -> dict[str, str]:
    return {
        "RateLimit-Limit": str(result.limit),
        "RateLimit-Remaining": str(result.remaining),
        "RateLimit-Reset": str(result.reset_at),
    }


async def worker_guardrail_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    limits = ROUTE_LIMITS.get((request.method.upper(), request.url.path), ())
    api_key = os.environ.get("WATCHDOG_WORKER_API_KEY", "").strip()
    expected = f"Bearer {api_key}" if api_key else ""
    authorization = request.headers.get("authorization", "")
    last_result: RateLimitResult | None = None

    # Invalid or missing credentials are rejected cheaply by the endpoint's auth
    # dependency. Only a valid key can consume the expensive-action allowance.
    if limits and expected and authorization == expected:
        for limit in limits:
            result = WORKER_RATE_LIMITER.consume(limit.name, "configured-worker-key", limit.requests, limit.seconds)
            if not result.allowed:
                headers = _headers(result)
                headers["Retry-After"] = str(result.retry_after)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Worker safety limit reached. Wait for the current window to reset.",
                        "error": "rate_limit_exceeded",
                    },
                    headers=headers,
                )
            if last_result is None or result.remaining < last_result.remaining:
                last_result = result

    response = await call_next(request)
    if last_result is not None:
        for key, value in _headers(last_result).items():
            response.headers[key] = value
    return response


def worker_guardrail_status() -> dict[str, object]:
    return {
        "enabled": True,
        "mode": "per-process fixed windows",
        "protected_actions": len(ROUTE_LIMITS),
        "note": "Invalid credentials are rejected before they can consume an action allowance.",
    }
