from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .auth import verify_scoped_token
from .rate_limit import FixedWindowRateLimiter, RateLimitResult


@dataclass(frozen=True)
class WindowLimit:
    name: str
    requests: int
    seconds: int


@dataclass(frozen=True)
class RouteRule:
    method: str
    path: str
    limits: tuple[WindowLimit, ...]
    prefix: bool = False


RATE_LIMITER = FixedWindowRateLimiter()

LOGIN_LIMITS = (
    WindowLimit("login-ip", 10, 15 * 60),
    WindowLimit("login-global", 50, 15 * 60),
)

# These limits are deliberately conservative for a private, single-operator
# console. They cap costly outbound work while leaving local triage responsive.
ROUTE_RULES = (
    RouteRule("POST", "/v1/assistant", (WindowLimit("assistant-burst", 5, 60), WindowLimit("assistant-daily", 30, 24 * 60 * 60))),
    RouteRule("POST", "/v1/media/render", (WindowLimit("media-render-hour", 3, 60 * 60), WindowLimit("media-render-daily", 10, 24 * 60 * 60))),
    RouteRule("POST", "/v1/crawl/site", (WindowLimit("site-crawl-hour", 10, 60 * 60), WindowLimit("site-crawl-daily", 30, 24 * 60 * 60))),
    RouteRule("POST", "/v1/research/onion/crawl", (WindowLimit("onion-crawl-hour", 5, 60 * 60), WindowLimit("onion-crawl-daily", 15, 24 * 60 * 60))),
    RouteRule("POST", "/v1/research/onion/fetch", (WindowLimit("onion-fetch-hour", 20, 60 * 60),)),
    RouteRule("POST", "/v1/research/onion/discover", (WindowLimit("onion-discovery-hour", 20, 60 * 60),)),
    RouteRule("POST", "/v1/research/search", (WindowLimit("research-search-hour", 30, 60 * 60),)),
    RouteRule("POST", "/v1/osint/search", (WindowLimit("osint-search-hour", 30, 60 * 60),)),
    RouteRule("POST", "/v1/probe/network", (WindowLimit("network-probe-hour", 30, 60 * 60),)),
    RouteRule("POST", "/v1/probe/web-security", (WindowLimit("web-probe-hour", 60, 60 * 60),)),
    RouteRule("POST", "/v1/media/inspect", (WindowLimit("media-inspect-hour", 30, 60 * 60),)),
    RouteRule("GET", "/v1/media/search", (WindowLimit("media-search-hour", 60, 60 * 60),)),
    RouteRule("POST", "/v1/intel/ip", (WindowLimit("ip-intel-hour", 60, 60 * 60),)),
    RouteRule("GET", "/v1/vehicle/vin/", (WindowLimit("vin-hour", 60, 60 * 60),), prefix=True),
    RouteRule("GET", "/v1/maps/geocode", (WindowLimit("geocode-hour", 60, 60 * 60),)),
)


def _client_identity(request: Request) -> str:
    # Hosting proxies normally replace these values. A global login limit remains
    # in force even if an untrusted upstream lets a caller vary the forwarded IP.
    for header in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
        value = request.headers.get(header, "").split(",", 1)[0].strip()
        if value:
            return value
    if request.client and request.client.host:
        return request.client.host
    return "unknown-client"


def _authenticated_identity(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        payload = verify_scoped_token(token, {"watchdog-admin", "watchdog-mobile"})
    except Exception:
        return None
    scope = str(payload.get("scope", "unknown"))
    if scope == "watchdog-mobile":
        return f"scope:{scope}:{payload.get('device_name', 'device')}"
    # WatchDog currently has one administrator. A stable identity keeps a fresh
    # login session from bypassing daily cost ceilings.
    return f"scope:{scope}"


def _route_limits(method: str, path: str) -> tuple[WindowLimit, ...]:
    for rule in ROUTE_RULES:
        if method != rule.method:
            continue
        if (rule.prefix and path.startswith(rule.path)) or (not rule.prefix and path == rule.path):
            return rule.limits
    return ()


def _headers(result: RateLimitResult) -> dict[str, str]:
    return {
        "RateLimit-Limit": str(result.limit),
        "RateLimit-Remaining": str(result.remaining),
        "RateLimit-Reset": str(result.reset_at),
    }


def _limited(result: RateLimitResult) -> JSONResponse:
    headers = _headers(result)
    headers["Retry-After"] = str(result.retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Wait for the current safety window to reset.",
            "error": "rate_limit_exceeded",
        },
        headers=headers,
    )


async def abuse_guardrail_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    method = request.method.upper()
    path = request.url.path
    last_result: RateLimitResult | None = None

    if method == "POST" and path == "/v1/auth/login":
        client_identity = _client_identity(request)
        for limit in LOGIN_LIMITS:
            identity = client_identity if limit.name == "login-ip" else "all-login-traffic"
            result = RATE_LIMITER.consume(limit.name, identity, limit.requests, limit.seconds)
            if not result.allowed:
                return _limited(result)
            last_result = result
    else:
        limits = _route_limits(method, path)
        if limits:
            identity = _authenticated_identity(request)
            if identity:
                for limit in limits:
                    result = RATE_LIMITER.consume(limit.name, identity, limit.requests, limit.seconds)
                    if not result.allowed:
                        return _limited(result)
                    if last_result is None or result.remaining < last_result.remaining:
                        last_result = result

    response = await call_next(request)
    if last_result is not None:
        for key, value in _headers(last_result).items():
            response.headers[key] = value
    return response


def guardrail_status() -> dict[str, object]:
    return {
        "enabled": True,
        "mode": "per-process fixed windows",
        "login_limit": "10 attempts per client per 15 minutes; 50 total per 15 minutes",
        "ai_limit": "5 requests per minute; 30 per day",
        "ai_switch": "WATCHDOG_AI_ENABLED must still be true before any OpenAI call",
    }
