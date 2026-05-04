"""
Profile service facade — the import every other agent uses.

Other agents must NEVER import :mod:`src.agents.profile_agent` directly.
They depend on this module's surface (``profile_service.get_user_context``)
so the agent implementation can be swapped, A/B tested, or split out
into its own service later without touching every consumer.

This is the cleanest example of channel #1 of the cross-agent
collaboration design (sync service calls; see
``src/agents/base/collaboration.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid circular import in the agents package at import time
    from src.agents.profile_agent.snapshot import UserContextSnapshot


class ProfileService:
    """Thin DI wrapper around the profile agent's read API."""

    async def get_user_context(
        self, user_id: str, *, intent: str = "profile"
    ) -> "UserContextSnapshot":
        """Return a :class:`UserContextSnapshot` for ``user_id`` + ``intent``.

        See :meth:`ProfileAgent.get_user_context` for the contract.
        """
        # Imported lazily so the rest of the codebase can import
        # `profile_service` without paying agent-package import cost.
        from src.agents.profile_agent import profile_agent

        return await profile_agent.get_user_context(user_id, intent=intent)


# Module-level singleton — import this rather than instantiating yourself.
profile_service = ProfileService()
