"""Cross-cutting middleware.

- Request ID: attach an ``X-Request-ID`` to every response and bind it
  into the structured-log context so logs correlate.
- Security headers: HSTS (prod only), Referrer-Policy, X-Content-Type-Options,
  X-Frame-Options, Permissions-Policy, Cross-Origin isolation, CSP.
- Rate limiter: sliding-window per-IP with in-memory fallback when Redis
  is unavailable.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    HEADER = "x-request-id"

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get(self.HEADER) or uuid.uuid4().hex[:16]
        # Bind for the duration of this request
        structlog.contextvars.bind_contextvars(request_id=rid)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[self.HEADER] = rid
        return response


_SECURITY_HEADERS_BASE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # Deliberately restrictive default CSP for the JSON API surface.
    # The Next.js app sets its own CSP via next.config.
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in _SECURITY_HEADERS_BASE.items():
            response.headers.setdefault(k, v)
        settings = get_settings()
        if settings.app_env == "production":
            # 6 months HSTS + subdomains + preload — only in prod so local
            # HTTP dev isn't broken.
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=15552000; includeSubDomains; preload",
            )
        return response


class _InMemoryLimiter:
    """Fixed-window counter per key. Coarse but bounded — used as a
    fallback when Redis isn't configured (e.g. tests). Not fit for
    multi-process production, which uses the Redis path below.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def hit(self, key: str, *, limit: int, window_s: float) -> bool:
        now = time.time()
        bucket = self._buckets[key]
        # Drop old entries
        cutoff = now - window_s
        self._buckets[key] = [t for t in bucket if t >= cutoff]
        if len(self._buckets[key]) >= limit:
            return False
        self._buckets[key].append(now)
        return True


class RateLimiter:
    """Public interface. Uses Redis when available, in-memory otherwise."""

    def __init__(self, *, limit: int, window_s: float, redis_url: str | None) -> None:
        self.limit = limit
        self.window_s = window_s
        self._mem = _InMemoryLimiter()
        self._redis = None
        if redis_url:
            try:
                import redis.asyncio as redis_async
                self._redis = redis_async.from_url(redis_url, decode_responses=True)
            except Exception as e:  # noqa: BLE001
                log.warning("rate_limiter_redis_init_failed", err=str(e))
                self._redis = None

    async def allow(self, key: str) -> bool:
        if self._redis is None:
            return self._mem.hit(key, limit=self.limit, window_s=self.window_s)
        # Redis: INCR with EXPIRE window
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key, 1)
            pipe.expire(key, int(self.window_s))
            count, _ = await pipe.execute()
            return int(count) <= self.limit
        except Exception as e:  # noqa: BLE001
            # Disable Redis permanently after the first failure so we don't
            # burn a connect-timeout on every subsequent request.
            log.warning("rate_limiter_redis_failed_permanent_fallback", err=str(e))
            self._redis = None
            return self._mem.hit(key, limit=self.limit, window_s=self.window_s)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies rate limits to state-changing methods by default.

    Config-driven: hard-coded conservative defaults for the MVP; a
    per-route override system is a Phase 5.1 backlog item.
    """

    #                       limit, window_s
    _RULES: dict[str, tuple[int, float]] = {
        # method + path prefix → bucket
        "POST /api/v1/agent/chat": (10, 60.0),      # 10 turns / min per user
        "POST /api/v1/backtests": (20, 60.0),
        "POST /api/v1/signals": (60, 60.0),
        "POST /api/v1/portfolios": (60, 60.0),
        "*": (300, 60.0),                            # global write bucket
    }

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        settings = get_settings()
        self._limiters: dict[str, RateLimiter] = {}
        for rule, (limit, window) in self._RULES.items():
            self._limiters[rule] = RateLimiter(
                limit=limit, window_s=window, redis_url=settings.redis_url,
            )

    async def dispatch(self, request: Request, call_next):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        # find first matching rule
        path = request.url.path
        method = request.method
        rule_key = None
        for key in self._RULES:
            if key == "*":
                continue
            if key.startswith(f"{method} ") and path.startswith(key.split(" ", 1)[1]):
                rule_key = key
                break
        if rule_key is None:
            rule_key = "*"
        client_id = _client_id(request)
        limiter = self._limiters[rule_key]
        bucket_key = f"rl:{rule_key}:{client_id}"
        allowed = await limiter.allow(bucket_key)
        if not allowed:
            log.warning("rate_limited", rule=rule_key, client=client_id, path=path)
            return JSONResponse(
                {"detail": "rate limited", "rule": rule_key,
                 "limit": limiter.limit, "window_seconds": limiter.window_s},
                status_code=429,
                headers={"Retry-After": str(int(limiter.window_s))},
            )
        return await call_next(request)


def _client_id(request: Request) -> str:
    # Prefer the demo_user cookie so shared IPs (offices, mobile carriers)
    # don't share a bucket. Falls back to the client IP.
    cookie_user = request.cookies.get("demo_user")
    if cookie_user:
        return f"cookie:{cookie_user}"
    return f"ip:{request.client.host if request.client else 'unknown'}"
