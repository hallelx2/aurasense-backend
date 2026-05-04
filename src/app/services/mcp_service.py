"""
External food / restaurant service adapter.

Originally named "MCPService" (the file kept that name for back-compat),
but it's not actually Model Context Protocol — it's a generic adapter
for restaurant search / menu / order APIs.

Phase 4 ships a **mock backend** with a small built-in catalog of dishes
across cuisines, complete with realistic ingredient lists so the
deterministic allergy filter has something to work against. This lets
the food agent work end-to-end *today* with no Foursquare / Places API
key required.

Switching to a real provider (Foursquare, Google Places, ...) is a
later-phase concern: implement ``_search_restaurants_<provider>`` and
flip ``MCP_PROVIDER`` in settings. The agent code never changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.app.core.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- catalog

# Inline catalog used when MCP_PROVIDER=mock (the default until a real
# provider is wired in Phase 4.x). The dishes are intentionally varied
# across cuisines and include explicit ingredient lists so the allergy
# filter has signal.

_MOCK_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "Phad Thai",
        "restaurant": "Bangkok Street Kitchen",
        "cuisine": "thai",
        "description": "Stir-fried rice noodles with shrimp, tofu, peanuts, and lime.",
        "ingredients": ["rice noodles", "shrimp", "tofu", "peanuts", "egg", "fish sauce", "lime", "bean sprouts"],
        "price_range": "mid-range",
        "estimated_price": 14.0,
    },
    {
        "name": "Vegan Pad See Ew",
        "restaurant": "Bangkok Street Kitchen",
        "cuisine": "thai",
        "description": "Wide rice noodles in dark soy sauce with broccoli and tofu. No peanuts.",
        "ingredients": ["wide rice noodles", "dark soy sauce", "broccoli", "tofu", "garlic"],
        "price_range": "mid-range",
        "estimated_price": 13.0,
    },
    {
        "name": "Green Papaya Salad (Som Tum)",
        "restaurant": "Bangkok Street Kitchen",
        "cuisine": "thai",
        "description": "Spicy salad of green papaya with peanuts, tomato, lime, and chili.",
        "ingredients": ["green papaya", "peanuts", "tomato", "lime", "chili", "fish sauce"],
        "price_range": "budget",
        "estimated_price": 9.0,
    },
    {
        "name": "Tom Kha Gai",
        "restaurant": "Bangkok Street Kitchen",
        "cuisine": "thai",
        "description": "Coconut milk soup with chicken, lemongrass, and galangal. No peanuts, no shellfish.",
        "ingredients": ["chicken", "coconut milk", "lemongrass", "galangal", "lime leaves", "mushrooms"],
        "price_range": "mid-range",
        "estimated_price": 12.0,
    },
    {
        "name": "Margherita Pizza",
        "restaurant": "Trattoria Roma",
        "cuisine": "italian",
        "description": "Wood-fired pizza with tomato, fresh mozzarella, and basil.",
        "ingredients": ["wheat flour", "tomato", "mozzarella cheese", "basil", "olive oil"],
        "price_range": "mid-range",
        "estimated_price": 16.0,
    },
    {
        "name": "Spaghetti Aglio e Olio",
        "restaurant": "Trattoria Roma",
        "cuisine": "italian",
        "description": "Spaghetti with garlic, olive oil, parsley, and chili flakes.",
        "ingredients": ["wheat pasta", "garlic", "olive oil", "parsley", "chili flakes"],
        "price_range": "budget",
        "estimated_price": 12.0,
    },
    {
        "name": "Jollof Rice with Grilled Chicken",
        "restaurant": "Lagos Local",
        "cuisine": "nigerian",
        "description": "Spicy tomato-based rice with grilled chicken thighs.",
        "ingredients": ["rice", "chicken", "tomato", "scotch bonnet pepper", "onion", "vegetable oil"],
        "price_range": "mid-range",
        "estimated_price": 13.0,
    },
    {
        "name": "Egusi Soup with Pounded Yam",
        "restaurant": "Lagos Local",
        "cuisine": "nigerian",
        "description": "Melon-seed soup with leafy greens, served with pounded yam.",
        "ingredients": ["egusi (melon seeds)", "spinach", "yam", "palm oil", "stockfish"],
        "price_range": "mid-range",
        "estimated_price": 15.0,
    },
    {
        "name": "Falafel Plate",
        "restaurant": "Mezze",
        "cuisine": "mediterranean",
        "description": "Crispy chickpea fritters with hummus, tabbouleh, and pita.",
        "ingredients": ["chickpeas", "wheat pita", "tahini", "parsley", "tomato", "cucumber"],
        "price_range": "budget",
        "estimated_price": 11.0,
    },
    {
        "name": "Grilled Salmon Bowl",
        "restaurant": "Mezze",
        "cuisine": "mediterranean",
        "description": "Grilled salmon over quinoa with roasted vegetables and tahini drizzle.",
        "ingredients": ["salmon", "quinoa", "zucchini", "bell pepper", "tahini", "olive oil"],
        "price_range": "premium",
        "estimated_price": 22.0,
    },
    {
        "name": "Vegan Buddha Bowl",
        "restaurant": "Greens & Grains",
        "cuisine": "international",
        "description": "Brown rice, roasted sweet potato, kale, chickpeas, avocado, and lemon-tahini.",
        "ingredients": ["brown rice", "sweet potato", "kale", "chickpeas", "avocado", "tahini", "lemon"],
        "price_range": "mid-range",
        "estimated_price": 14.0,
    },
    {
        "name": "Quinoa Salad",
        "restaurant": "Greens & Grains",
        "cuisine": "international",
        "description": "Quinoa with cherry tomato, cucumber, mint, and lemon vinaigrette. Gluten-free, vegan.",
        "ingredients": ["quinoa", "cherry tomato", "cucumber", "mint", "lemon", "olive oil"],
        "price_range": "budget",
        "estimated_price": 11.0,
    },
]


# --------------------------------------------------------------- service


class MCPService:
    """Adapter for restaurant / dish search and order placement.

    The class name is kept for back-compat; nothing in here is actually
    Model Context Protocol. Callers should treat this as a stable
    surface the real provider integration plugs in behind.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("service.mcp")
        self.provider = (
            getattr(settings, "MCP_PROVIDER", "mock") or "mock"
        ).lower()

    # ----------------------------------------------------- read API

    async def search_restaurants(
        self,
        *,
        query: str,
        cuisine: Optional[str] = None,
        price_range: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return up to ``limit`` dishes / restaurants matching the criteria.

        The mock implementation does a case-insensitive substring match
        against the inline catalog. A real implementation would call
        Foursquare / Places / etc.
        """
        if self.provider != "mock":
            self.logger.warning(
                "MCP_PROVIDER=%s not implemented; falling back to mock.",
                self.provider,
            )

        q = (query or "").strip().lower()
        c = (cuisine or "").strip().lower() if cuisine else None
        pr = (price_range or "").strip().lower() if price_range else None

        results: List[Dict[str, Any]] = []
        for item in _MOCK_CATALOG:
            if c and item["cuisine"].lower() != c:
                continue
            if pr and item.get("price_range", "").lower() != pr:
                continue
            if q and not _matches_query(q, item):
                continue
            results.append(dict(item))
        return results[:limit]

    async def get_menu_data(self, restaurant_id: str) -> Dict[str, Any]:
        """Return the menu for a restaurant. Mock returns matching dishes."""
        rid = (restaurant_id or "").strip().lower()
        if not rid:
            return {}
        dishes = [
            dict(item)
            for item in _MOCK_CATALOG
            if item["restaurant"].lower() == rid
        ]
        if not dishes:
            return {}
        return {
            "restaurant": dishes[0]["restaurant"],
            "cuisine": dishes[0]["cuisine"],
            "dishes": dishes,
        }

    # ----------------------------------------------------- write API

    async def place_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Place an order via the external provider.

        The mock provider just echoes the order back with a synthetic
        ``provider_order_id`` and ``status='pending_payment'``. The
        food agent's ``place_order_node`` writes the corresponding
        Neo4j ``Order`` node — this method just simulates the external
        side of the transaction.
        """
        import uuid

        return {
            "provider": self.provider,
            "provider_order_id": f"mock-{uuid.uuid4().hex[:8]}",
            "status": "pending_payment",
            **order_data,
        }

    async def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment via the external provider. Stubbed pending Phase 5."""
        return {"status": "deferred", "reason": "payments not implemented yet"}

    # ------------------------------------------------ legacy back-compat

    async def check_restaurant_availability(
        self, restaurant_id: str
    ) -> Dict[str, Any]:
        """Legacy method retained for older callers; returns availability."""
        if self.provider == "mock":
            menu = await self.get_menu_data(restaurant_id)
            return {"available": bool(menu), "restaurant": restaurant_id}
        return {}


# Module-level singleton — import this rather than instantiating yourself.
mcp_service = MCPService()


# ---------------------------------------------------------- helpers


def _matches_query(q: str, item: Dict[str, Any]) -> bool:
    """Fuzzy substring match against name + description + cuisine."""
    haystack = " ".join(
        [
            str(item.get("name", "")),
            str(item.get("description", "")),
            str(item.get("cuisine", "")),
            str(item.get("restaurant", "")),
        ]
    ).lower()
    # Match if any whitespace-split token from the query appears in the
    # haystack — gives "thai" / "vegan" / "spicy" reasonable hits.
    tokens = [t for t in q.split() if t]
    if not tokens:
        return True
    return any(t in haystack for t in tokens)
