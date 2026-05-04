"""
Travel service facade (interface stub).

The Travel agent itself is deferred to a later phase — this module
exists so the food agent (Phase 4) can call into a stable shape
(``travel_service.get_current_travel_context``) rather than reaching
into the Travel agent's internals when it lands.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class TravelService:
    """Placeholder. Real implementation lands with the Travel agent."""

    async def get_current_travel_context(
        self, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the user's current travel context (city, dates, purpose).

        Stubbed — returns None to signal "no active travel". Food agent
        (Phase 4) will use this to decide whether to apply local geo
        filters for restaurant search.
        """
        return None

    async def get_recent_visits(
        self, user_id: str, *, limit: int = 5
    ) -> list[Dict[str, Any]]:
        """Return recent travel destinations the user has visited. Stubbed."""
        return []


travel_service = TravelService()
