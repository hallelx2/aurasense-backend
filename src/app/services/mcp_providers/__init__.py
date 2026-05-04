"""
MCP provider plugins — one per upstream restaurant-data source.

Each provider exposes the same coroutine signatures
(``search_restaurants``, ``get_menu_data``, ``place_order``) so
``MCPService`` can dispatch by ``settings.MCP_PROVIDER`` without
agent code ever knowing which backend is live.

Adding a provider:

1. Create ``src/app/services/mcp_providers/<name>.py``.
2. Implement the three coroutines with the canonical return shapes
   (see ``mock.py`` for the reference implementation).
3. Register the name in ``Settings._validate_mcp_provider``'s allowed
   set and in ``MCPService._dispatch`` below.
"""

from . import foursquare, mock

__all__ = ["foursquare", "mock"]
