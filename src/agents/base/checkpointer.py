"""
LangGraph checkpointer factory.

Every compiled graph in the system uses the same Redis-backed checkpointer
so conversations survive restarts and scale across workers.

``langgraph-checkpoint-redis`` exposes both ``RedisSaver`` and
``AsyncRedisSaver``. ``from_conn_string`` returns a context manager (for
auto-cleanup); we instead construct the savers directly via their
``__init__(redis_url=...)`` so we can share a single instance across the
process and own its lifecycle in the FastAPI lifespan.

Index/key creation is one-shot: call :func:`setup_checkpointer_indexes`
once at app startup (from the lifespan handler).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.checkpoint.redis import AsyncRedisSaver, RedisSaver

from src.app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_redis_saver() -> RedisSaver:
    """Return the shared sync :class:`RedisSaver` (constructed lazily)."""
    return RedisSaver(redis_url=settings.REDIS_URL)


@lru_cache(maxsize=1)
def get_async_redis_saver() -> AsyncRedisSaver:
    """Return the shared :class:`AsyncRedisSaver` (constructed lazily)."""
    return AsyncRedisSaver(redis_url=settings.REDIS_URL)


async def setup_checkpointer_indexes() -> None:
    """One-time index creation for the Redis-backed checkpointer.

    Safe to call repeatedly — Redis index creation is idempotent. Call
    from the FastAPI lifespan startup hook.
    """
    saver = get_async_redis_saver()
    if hasattr(saver, "asetup"):
        try:
            await saver.asetup()
            logger.info("AsyncRedisSaver indexes created/verified")
        except Exception:  # pragma: no cover  - logged but non-fatal at boot
            logger.exception("AsyncRedisSaver setup failed")
    elif hasattr(saver, "create_indexes"):
        try:
            saver.create_indexes()
            logger.info("RedisSaver indexes created/verified")
        except Exception:  # pragma: no cover
            logger.exception("RedisSaver index setup failed")


def reset_checkpointer_cache() -> None:
    """Drop cached savers (for tests that swap REDIS_URL via monkeypatch)."""
    get_redis_saver.cache_clear()
    get_async_redis_saver.cache_clear()
