"""
External food / restaurant service adapter.

Originally named "MCPService" (we kept the name for back-compat), but
it's not actually Model Context Protocol — it's a generic adapter for
restaurant search / menu / order APIs.

Provider plug-in pattern: the actual implementations live under
``mcp_providers/`` (one module per upstream). ``MCPService`` itself is
a thin dispatcher that picks a provider based on
``settings.MCP_PROVIDER`` and forwards every call to it.

Available providers:

* ``mock`` (default) — bundled 12-dish catalog with explicit ingredients.
  Best for testing the allergy-safety flow.
* ``foursquare`` — real restaurant discovery via Foursquare Places v3.
  Requires ``FOURSQUARE_API_KEY``. Returns restaurant info only (no
  per-dish ingredients), so allergy filtering is weaker.

Adding another provider:

1. Create ``src/app/services/mcp_providers/<name>.py`` with the
   canonical coroutines (``search_restaurants``, ``get_menu_data``,
   ``place_order``).
2. Register the name in
   ``Settings._validate_mcp_provider``'s allowed set.
3. Add the dispatch branch in :py:meth:`MCPService._provider_module`.
"""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, Dict, List, Optional

from src.app.core.config import settings
from src.app.services.mcp_providers import foursquare as foursquare_provider
from src.app.services.mcp_providers import mock as mock_provider

logger = logging.getLogger(__name__)


class MCPService:
    """Provider-dispatching adapter. Singleton; import ``mcp_service``."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("service.mcp")

    # ------------------------------------------------- provider dispatch

    @property
    def provider(self) -> str:
        """Always read from settings so a runtime env-var override applies."""
        return (settings.MCP_PROVIDER or "mock").lower()

    def _provider_module(self) -> ModuleType:
        prov = self.provider
        if prov == "foursquare":
            return foursquare_provider
        if prov == "mock":
            return mock_provider
        # Settings validation should have caught this at boot; defensive
        # fallback so a misconfig doesn't 500 every food agent turn.
        self.logger.error(
            "MCP_PROVIDER=%s not implemented; falling back to mock", prov
        )
        return mock_provider

    # ----------------------------------------------------- read API

    async def search_restaurants(
        self,
        *,
        query: str,
        cuisine: Optional[str] = None,
        price_range: Optional[str] = None,
        limit: int = 10,
        near: Optional[str] = None,
        ll: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return up to ``limit`` recommendations matching the criteria."""
        return await self._provider_module().search_restaurants(
            query=query,
            cuisine=cuisine,
            price_range=price_range,
            limit=limit,
            near=near,
            ll=ll,
        )

    async def get_menu_data(self, restaurant_id: str) -> Dict[str, Any]:
        return await self._provider_module().get_menu_data(restaurant_id)

    # ----------------------------------------------------- write API

    async def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._provider_module().place_order(order_data)

    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Stubbed pending Phase 5 — payments aren't implemented in any provider."""
        return {"status": "deferred", "reason": "payments not implemented yet"}

    # ------------------------------------------------ legacy back-compat

    async def check_restaurant_availability(
        self, restaurant_id: str
    ) -> Dict[str, Any]:
        """Legacy method retained for older callers; returns availability."""
        menu = await self.get_menu_data(restaurant_id)
        return {"available": bool(menu), "restaurant": restaurant_id}


# Module-level singleton — import this rather than instantiating yourself.
mcp_service = MCPService()
