"""Base agent abstractions.

Every specialist agent (onboarding, food, travel, social, profile) extends
:class:`BaseAgent` and operates on a state that extends
:class:`BaseAgentState`. State is checkpointed in Redis via the shared
:func:`get_redis_saver`, and cross-agent collaboration goes through the
helpers in :mod:`collaboration`.
"""

from .agent import BaseAgent
from .checkpointer import (
    get_async_redis_saver,
    get_redis_saver,
    reset_checkpointer_cache,
    setup_checkpointer_indexes,
)
from .collaboration import (
    MAX_HANDOFFS_PER_TURN,
    handoff_trail,
    request_handoff,
)
from .state import BaseAgentState

__all__ = [
    "BaseAgent",
    "BaseAgentState",
    "MAX_HANDOFFS_PER_TURN",
    "get_async_redis_saver",
    "get_redis_saver",
    "handoff_trail",
    "request_handoff",
    "reset_checkpointer_cache",
    "setup_checkpointer_indexes",
]
