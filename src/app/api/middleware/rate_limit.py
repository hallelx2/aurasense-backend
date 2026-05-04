"""
Rate limiting via FastAPI dependency.

The previous module-level `RateLimitMiddleware` was a per-process dict
that never got registered in `main.py` and wouldn't survive multiple
workers anyway. This module replaces it with a Redis-backed sliding
window applied selectively as `Depends(RateLimit(...))` on the routes
that actually need it (login, register, anything else credential-spammable).

Usage::

    @router.post(
        "/login",
        dependencies=[Depends(RateLimit("auth:login", limit=5, window_seconds=60))],
    )
    async def login(...): ...

The key is built from ``"{key_prefix}:{client_id}"`` where ``client_id``
is the authenticated user's ID if available, otherwise the request IP.
That way an authed user behind shared NAT isn't punished by a noisy
neighbor.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from src.app.core.database import redis_cache

logger = logging.getLogger(__name__)


class RateLimit:
    """A FastAPI dependency that enforces a per-client request budget.

    On Redis outage the limiter **fails open** in development and
    **fails closed** in production (mirroring the JWT blacklist policy
    in `core/security.py`). This avoids a Redis blip from locking
    everyone out of dev while still preventing abuse-during-outage in prod.
    """

    def __init__(
        self,
        key_prefix: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.key_prefix = key_prefix
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        client_id = self._client_id(request)
        redis_key = f"ratelimit:{self.key_prefix}:{client_id}"

        client = redis_cache.redis_client
        if client is None:
            self._handle_redis_unavailable(redis_key)
            return

        try:
            count = await client.incr(redis_key)
            if count == 1:
                # First hit in this window; set TTL.
                await client.expire(redis_key, self.window_seconds)
        except Exception:
            logger.exception("rate limit Redis call failed for key=%s", redis_key)
            self._handle_redis_unavailable(redis_key)
            return

        if count > self.limit:
            logger.warning(
                "rate limit exceeded: key=%s count=%d limit=%d",
                redis_key,
                count,
                self.limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded for {self.key_prefix} "
                    f"({self.limit}/{self.window_seconds}s)"
                ),
                headers={"Retry-After": str(self.window_seconds)},
            )

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _client_id(request: Request) -> str:
        """Prefer authed user uid; fall back to client IP (X-Forwarded-For aware)."""
        # Auth dependency may have stashed the user on request.state; if not,
        # fall through to IP. We deliberately don't import get_current_user
        # here to avoid a hard dependency on the auth module.
        user = getattr(request.state, "user", None)
        if user is not None and getattr(user, "uid", None):
            return f"user:{user.uid}"

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        if request.client and request.client.host:
            return f"ip:{request.client.host}"
        return "ip:unknown"

    def _handle_redis_unavailable(self, key: str) -> None:
        """Fail open in dev, fail closed in prod."""
        from src.app.core.config import settings

        if settings.is_production:
            logger.error(
                "rate limiter: Redis unavailable, failing CLOSED (prod) on key=%s",
                key,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable; please retry shortly.",
            )
        # Dev: fail open silently.


# ---- Pre-configured limiters for common endpoints ------------------------

# Login: 5 attempts per minute per (user-or-IP). Tight to make credential
# stuffing costly without locking real users out on a typo storm.
auth_login_limiter = RateLimit("auth:login", limit=5, window_seconds=60)

# Registration: 3 per hour per IP. New-account abuse is the threat;
# legitimate users need this once.
auth_register_limiter = RateLimit("auth:register", limit=3, window_seconds=3600)
