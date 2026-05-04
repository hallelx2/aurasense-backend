"""
Database connections — Neo4j (sync driver bootstrap) + Redis (async).

Phase 1.5 polish notes:

* The Redis ``set`` / ``get`` previously called ``await self.is_connected()``
  on every operation, doubling the round-trip count (PING then the real
  command). That's gone — a sync attribute check is enough; if Redis
  dies between calls, the operation itself fails fast and the caller
  handles it. The blacklist / rate-limit code already wraps these calls
  in try/except.
* :func:`run_in_thread` exposes a small helper for places where sync
  ``neomodel`` queries are unavoidable: ``await run_in_thread(User.nodes.filter(...).first)``.
  This keeps blocking DB calls out of the asyncio event loop without
  forcing every model call site to use ``asyncio.to_thread`` directly.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar

from neo4j import GraphDatabase
import redis.asyncio as redis

from .config import settings

logger = logging.getLogger(__name__)


P = ParamSpec("P")
T = TypeVar("T")


async def run_in_thread(
    fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Run a blocking callable in a thread pool from async code.

    Convenience wrapper around :func:`asyncio.to_thread`. Use it
    around sync neomodel queries (which still don't expose an async API
    in 5.x) so they don't stall the event loop::

        user = await run_in_thread(User.nodes.filter(uid=uid).first)

    The wrapped function should be self-contained — closures over
    request-scoped state are fine; closures over event-loop state are
    not (they'll error inside the worker thread).
    """
    if kwargs:
        bound = partial(fn, *args, **kwargs)
        return await asyncio.to_thread(bound)
    return await asyncio.to_thread(fn, *args)  # type: ignore[arg-type]


class Neo4jDatabase:
    """Bootstrap Neo4j driver and surface a basic health check.

    Most application code doesn't talk to this class directly — it goes
    through ``neomodel`` (which manages its own connection via
    ``neomodel.config.DATABASE_URL``). This wrapper exists so the
    FastAPI lifespan can fail fast if Neo4j is unreachable at startup.
    """

    def __init__(self) -> None:
        self.driver = None
        self.logger = logging.getLogger("database.neo4j")

    async def connect(self) -> None:
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            # Verify the driver can actually reach Neo4j once at startup.
            ok = await self.is_connected()
            if not ok:
                raise RuntimeError("Neo4j ping failed at startup")
            self.logger.info("Connected to Neo4j database")
        except Exception as e:
            self.logger.error("Failed to connect to Neo4j: %s", e)
            raise

    async def close(self) -> None:
        if self.driver:
            try:
                # Driver.close is sync; push to a thread so we don't block.
                await run_in_thread(self.driver.close)
            except Exception:
                self.logger.exception("Error closing Neo4j driver")
            self.logger.info("Neo4j connection closed")

    async def is_connected(self) -> bool:
        """Run a trivial query to confirm Neo4j accepts connections."""
        if not self.driver:
            return False

        def _check() -> bool:
            try:
                with self.driver.session() as session:
                    result = session.run("RETURN 1")
                    return result.single() is not None
            except Exception:
                return False

        try:
            return await run_in_thread(_check)
        except Exception as e:
            self.logger.error("Neo4j connection check failed: %s", e)
            return False

    async def execute_query(
        self, query: str, parameters: Optional[dict] = None
    ):
        """Execute a Cypher query (sync driver, run in thread).

        Use sparingly — most reads/writes should go through neomodel.
        Provided for ad-hoc admin queries.
        """
        if not self.driver:
            raise RuntimeError("Neo4j driver not initialized")

        def _run() -> list[dict]:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]

        return await run_in_thread(_run)


class RedisCache:
    """Thin wrapper around `redis.asyncio` with set/get helpers.

    Avoids the double-ping pattern that used to live here. The
    rate-limiter and JWT-blacklist callers already handle Redis errors
    themselves; we don't need an extra ``is_connected()`` round-trip
    before every ``set`` / ``get``.
    """

    def __init__(self) -> None:
        self.redis_client: Optional[redis.Redis] = None
        self.logger = logging.getLogger("database.redis")

    async def connect(self) -> None:
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            if not await self.is_connected():
                raise RuntimeError("Failed to connect to Redis")
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error("Failed to connect to Redis: %s", e)
            raise

    async def close(self) -> None:
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception:
                self.logger.exception("Error closing Redis client")
            self.logger.info("Redis connection closed")

    async def is_connected(self) -> bool:
        """One-shot health check (PING). Use at startup, NOT per request."""
        if not self.redis_client:
            return False
        try:
            return bool(await self.redis_client.ping())
        except Exception as e:
            self.logger.error("Redis connection check failed: %s", e)
            return False

    # ------------------------------------------------------- Operations
    # No `await self.is_connected()` here — that double-ping pattern is
    # gone. If Redis dies between requests, the actual command will
    # raise and the caller (already wrapped in try/except in
    # security.py / rate_limit.py) handles it.

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if self.redis_client is None:
            raise RuntimeError("Redis is not connected")
        await self.redis_client.set(key, value, ex=ttl)

    async def get(self, key: str) -> Optional[str]:
        if self.redis_client is None:
            raise RuntimeError("Redis is not connected")
        return await self.redis_client.get(key)


# Global database instances
neo4j_db = Neo4jDatabase()
redis_cache = RedisCache()
