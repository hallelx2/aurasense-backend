"""
Social service facade (interface stub).

The Social agent itself is deferred to a later phase — this module
exists so the food agent (Phase 4) can be written against the future
contract without churning import paths when the agent lands.

The methods declared here will be the cross-agent read surface; the
actual implementation will be a thin wrapper around
``social_agent.get_*`` once that agent ships.
"""

from __future__ import annotations

from typing import Any, Dict, List


class SocialService:
    """Placeholder. Real implementation lands with the Social agent."""

    async def get_connections_in_city(
        self, user_id: str, city: str, *, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return up to ``limit`` social connections currently in ``city``.

        Stubbed — returns an empty list. The food / travel agents are
        already coded against this signature so they keep working when
        the real implementation arrives.
        """
        return []

    async def get_match_suggestions(
        self, user_id: str, *, intent: str = "general", limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Return user-match suggestions ranked for ``intent``. Stubbed."""
        return []


social_service = SocialService()
