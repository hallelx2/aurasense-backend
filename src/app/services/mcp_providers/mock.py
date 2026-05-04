"""
Mock provider — bundled in-memory catalog of 12 dishes across 5 cuisines.

This is the *default* MCP provider and it's *better* than real data for
testing the allergy-safety flow because every dish has an explicit
``ingredients`` list. The deterministic allergy filter has signal here
that no public restaurant API exposes.

Keep canonical fields in sync with the foursquare provider:
  name (str), restaurant (str), cuisine (str), description (str),
  ingredients (list[str]), price_range (str), estimated_price (float).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_CATALOG: List[Dict[str, Any]] = [
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


def _matches_query(q: str, item: Dict[str, Any]) -> bool:
    haystack = " ".join(
        str(item.get(k, ""))
        for k in ("name", "description", "cuisine", "restaurant")
    ).lower()
    tokens = [t for t in q.split() if t]
    if not tokens:
        return True
    return any(t in haystack for t in tokens)


# ------------------------------------------------------------ public API


async def search_restaurants(
    *,
    query: str,
    cuisine: Optional[str] = None,
    price_range: Optional[str] = None,
    limit: int = 10,
    **_ignored: Any,
) -> List[Dict[str, Any]]:
    q = (query or "").strip().lower()
    c = (cuisine or "").strip().lower() if cuisine else None
    pr = (price_range or "").strip().lower() if price_range else None

    results: List[Dict[str, Any]] = []
    for item in _CATALOG:
        if c and item["cuisine"].lower() != c:
            continue
        if pr and item.get("price_range", "").lower() != pr:
            continue
        if q and not _matches_query(q, item):
            continue
        results.append(dict(item))
    return results[:limit]


async def get_menu_data(restaurant_id: str) -> Dict[str, Any]:
    rid = (restaurant_id or "").strip().lower()
    if not rid:
        return {}
    dishes = [
        dict(item)
        for item in _CATALOG
        if item["restaurant"].lower() == rid
    ]
    if not dishes:
        return {}
    return {
        "restaurant": dishes[0]["restaurant"],
        "cuisine": dishes[0]["cuisine"],
        "dishes": dishes,
    }


async def place_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "mock",
        "provider_order_id": f"mock-{uuid.uuid4().hex[:8]}",
        "status": "pending_payment",
        **order_data,
    }
