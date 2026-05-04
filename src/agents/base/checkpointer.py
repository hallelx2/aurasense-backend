"""
LangGraph checkpointer factory.

Every compiled graph in the system uses the same Redis-backed checkpointer
so conversations survive restarts and scale across workers. The async
variant is the default; the sync ``RedisSaver`` is exposed for code paths
(e.g. unit tests, scripts) that don't run inside an event loop.

Both factories are ``lru_cache``-d so the underlying connection pool is
shared rather than rebuilt per agent.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.redis import AsyncRedisSaver, RedisSaver

from src.app.core.config import settings


@lru_cache(maxsize=1)
def get_redis_saver() -> RedisSaver:
    """Return the shared sync RedisSaver instance."""
    saver = RedisSaver.from_conn_string(settings.REDIS_URL)
    # `RedisSaver.from_conn_string` returns a context manager in some
    # versions; normalize to the saver itself.
    if hasattr(saver, "__enter__") and not hasattr(saver, "put"):
        saver = saver.__enter__()
    return saver


@lru_cache(maxsize=1)
def get_async_redis_saver() -> AsyncRedisSaver:
    """Return the shared async AsyncRedisSaver instance."""
    saver = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
    if hasattr(saver, "__aenter__") and not hasattr(saver, "aput"):
        # Defer entering the context to the caller; we just return the
        # raw AsyncRedisSaver. Most LangGraph code paths accept it as-is.
        pass
    return saver


def reset_checkpointer_cache() -> None:
    """Drop cached savers (for tests that swap REDIS_URL via monkeypatch)."""
    get_redis_saver.cache_clear()
    get_async_redis_saver.cache_clear()
