"""Unit tests for the Redis-backed rate limiter dependency."""

from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
from starlette.testclient import TestClient

from src.app.api.middleware.rate_limit import RateLimit


class _FakeRedisClient:
    """Tiny in-memory stand-in. Only `incr` and `expire` are exercised."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedisClient:
    """Patch `redis_cache.redis_client` to a no-network fake."""
    fake = _FakeRedisClient()
    from src.app.core import database as db_mod

    monkeypatch.setattr(db_mod.redis_cache, "redis_client", fake, raising=False)
    return fake


def _request_for(client_host: str = "1.2.3.4") -> Request:
    """Build a minimal `Request` with the given client host."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": (client_host, 12345),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "raw_path": b"/",
    }
    return Request(scope)


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_under_limit_passes(self, fake_redis: _FakeRedisClient) -> None:
        limiter = RateLimit("auth:login", limit=3, window_seconds=60)
        request = _request_for()
        for _ in range(3):
            await limiter(request)  # no exception

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self, fake_redis: _FakeRedisClient) -> None:
        limiter = RateLimit("auth:login", limit=2, window_seconds=60)
        request = _request_for()
        await limiter(request)
        await limiter(request)
        with pytest.raises(HTTPException) as exc:
            await limiter(request)
        assert exc.value.status_code == 429
        assert "Retry-After" in exc.value.headers

    @pytest.mark.asyncio
    async def test_first_hit_sets_ttl(self, fake_redis: _FakeRedisClient) -> None:
        limiter = RateLimit("auth:register", limit=10, window_seconds=120)
        await limiter(_request_for())
        # Exactly one TTL set, equal to the configured window.
        keys = [k for k in fake_redis.ttls if k.startswith("ratelimit:auth:register")]
        assert len(keys) == 1
        assert fake_redis.ttls[keys[0]] == 120

    @pytest.mark.asyncio
    async def test_separate_clients_separate_buckets(
        self, fake_redis: _FakeRedisClient
    ) -> None:
        limiter = RateLimit("auth:login", limit=1, window_seconds=60)
        await limiter(_request_for("1.1.1.1"))
        await limiter(_request_for("2.2.2.2"))  # different IP, should pass

    @pytest.mark.asyncio
    async def test_xforwarded_for_used_when_present(
        self, fake_redis: _FakeRedisClient
    ) -> None:
        limiter = RateLimit("auth:login", limit=1, window_seconds=60)
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"5.6.7.8, 1.1.1.1")],
            "client": ("100.100.100.100", 0),
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "raw_path": b"/",
        }
        request = Request(scope)
        await limiter(request)
        # Bucket key should reflect the X-Forwarded-For first hop, not 100.*.
        assert any(
            k.endswith(":ip:5.6.7.8") for k in fake_redis.counts
        ), fake_redis.counts

    @pytest.mark.asyncio
    async def test_authed_user_uid_overrides_ip(
        self, fake_redis: _FakeRedisClient
    ) -> None:
        limiter = RateLimit("auth:login", limit=1, window_seconds=60)
        # Build a request and stash a fake user on `request.state`.
        request = _request_for()
        fake_user = MagicMock()
        fake_user.uid = "abc-uid"
        request.state.user = fake_user
        await limiter(request)
        assert any(
            k.endswith(":user:abc-uid") for k in fake_redis.counts
        ), fake_redis.counts

    @pytest.mark.asyncio
    async def test_redis_unavailable_dev_fails_open(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In dev, no Redis = no rate limiting (unblock local work)."""
        from src.app.core import database as db_mod

        monkeypatch.setattr(db_mod.redis_cache, "redis_client", None, raising=False)
        limiter = RateLimit("auth:login", limit=1, window_seconds=60)
        # Multiple calls should all succeed.
        for _ in range(5):
            await limiter(_request_for())

    @pytest.mark.asyncio
    async def test_redis_unavailable_prod_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In prod, no Redis = 503 (better than letting abuse through)."""
        from src.app.core import database as db_mod
        from src.app.core import config as config_mod

        monkeypatch.setattr(db_mod.redis_cache, "redis_client", None, raising=False)
        monkeypatch.setattr(config_mod.settings, "ENVIRONMENT", "production")

        limiter = RateLimit("auth:login", limit=1, window_seconds=60)
        with pytest.raises(HTTPException) as exc:
            await limiter(_request_for())
        assert exc.value.status_code == 503

    def test_invalid_construction_rejected(self) -> None:
        with pytest.raises(ValueError):
            RateLimit("x", limit=0, window_seconds=60)
        with pytest.raises(ValueError):
            RateLimit("x", limit=10, window_seconds=0)
