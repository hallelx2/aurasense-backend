"""
Foursquare Places provider.

Real restaurant discovery via the Foursquare Places API v3. Returns
restaurants matching the search criteria; the food agent then presents
them as recommendations. Foursquare does NOT expose per-dish ingredient
information, so the allergy filter only operates on restaurant name +
cuisine description in this mode (weaker safety than the mock provider
which has explicit ingredient lists).

Auth: Bearer ``FOURSQUARE_API_KEY``.
Free tier: ~5k requests/day, 99.5k/month at the time of writing.
Docs: https://docs.foursquare.com/developer/reference/place-search

Output is normalized to the same canonical shape the mock provider
returns:
  {name, restaurant, cuisine, description, ingredients (empty),
   price_range, estimated_price}

so MCPService callers and the food agent's downstream nodes don't care
which provider is live.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from src.app.core.config import settings

logger = logging.getLogger(__name__)


# Foursquare's Places API "search" endpoint relative path.
_SEARCH_PATH = "/places/search"

# Foursquare returns category objects with a numeric id + a name. We
# want to filter to "Restaurant" and food-related places. The umbrella
# category id 13000 covers "Dining and Drinking".
_DINING_CATEGORY_ID = "13000"

# Foursquare's price tier is 1-4 dollar signs. We map that to our
# canonical price_range labels so the food agent's downstream price
# filters keep working.
_PRICE_TIER_TO_RANGE: Dict[int, str] = {
    1: "budget",
    2: "mid-range",
    3: "premium",
    4: "luxury",
}

# Reverse mapping for query-time price_range filtering.
_RANGE_TO_PRICE_TIER: Dict[str, int] = {
    "budget": 1,
    "mid-range": 2,
    "premium": 3,
    "luxury": 4,
}

# Approximate per-person price for each tier. Foursquare doesn't return
# real prices, so we use these as the placeholder estimated_price.
_TIER_TO_ESTIMATED_PRICE: Dict[int, float] = {
    1: 12.0,
    2: 22.0,
    3: 45.0,
    4: 90.0,
}


def _normalize_place(place: Dict[str, Any]) -> Dict[str, Any]:
    """Map a single Foursquare place result to our canonical shape."""
    name = place.get("name") or "Unknown"
    categories = place.get("categories") or []
    cuisine = (
        categories[0].get("name", "").replace("Restaurant", "").strip().lower()
        if categories
        else "restaurant"
    ) or "restaurant"
    location = place.get("location") or {}
    address = (
        location.get("formatted_address")
        or location.get("address")
        or location.get("locality")
        or ""
    )
    price_tier = place.get("price")  # int 1-4 or None
    price_range = _PRICE_TIER_TO_RANGE.get(price_tier, "mid-range") if price_tier else None
    estimated_price = _TIER_TO_ESTIMATED_PRICE.get(price_tier, 18.0) if price_tier else None

    description_parts: List[str] = []
    if cuisine:
        description_parts.append(cuisine.title() + " restaurant")
    if address:
        description_parts.append(f"at {address}")
    rating = place.get("rating")
    if rating is not None:
        description_parts.append(f"(rating: {rating}/10)")
    description = " ".join(description_parts)

    return {
        # Canonical "dish-shaped" fields downstream code expects:
        "name": name,
        "restaurant": name,           # in foursquare mode, rec == restaurant
        "cuisine": cuisine,
        "description": description,
        "ingredients": [],            # Foursquare does NOT provide ingredients
        "price_range": price_range,
        "estimated_price": estimated_price,
        # Pass through provider-specific data for the frontend / future:
        "fsq_id": place.get("fsq_id"),
        "address": address,
        "rating": rating,
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
    }


def _build_search_params(
    *,
    query: str,
    cuisine: Optional[str],
    price_range: Optional[str],
    limit: int,
    near: Optional[str],
    ll: Optional[str],
) -> Dict[str, Any]:
    """Build the Foursquare /places/search query string."""
    params: Dict[str, Any] = {
        "limit": max(1, min(int(limit), 50)),
        "categories": _DINING_CATEGORY_ID,
        "fields": "fsq_id,name,categories,location,price,rating,distance",
    }
    # Combine the user query with a cuisine hint as free-text. The
    # `query` param does fuzzy substring matching across name/category.
    text = " ".join([s for s in (query, cuisine) if s and s.strip()]).strip()
    if text:
        params["query"] = text

    if price_range:
        tier = _RANGE_TO_PRICE_TIER.get(price_range.lower())
        if tier is not None:
            params["min_price"] = tier
            params["max_price"] = tier

    # Geographic scope. Prefer lat/lng, fall back to a city name string,
    # default to a neutral US-wide search if nothing was provided. (The
    # food agent doesn't have user location yet — that's a Phase 5
    # travel-agent integration.)
    if ll:
        params["ll"] = ll
    elif near:
        params["near"] = near
    else:
        params["near"] = "United States"
    return params


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.FOURSQUARE_API_KEY}",
        "Accept": "application/json",
    }


# ------------------------------------------------------------ public API


async def search_restaurants(
    *,
    query: str,
    cuisine: Optional[str] = None,
    price_range: Optional[str] = None,
    limit: int = 10,
    near: Optional[str] = None,
    ll: Optional[str] = None,
    **_ignored: Any,
) -> List[Dict[str, Any]]:
    """Search Foursquare Places for restaurants matching the criteria.

    Args:
        query: free-text search.
        cuisine: cuisine hint (gets folded into the query string).
        price_range: budget|mid-range|premium|luxury — mapped to
            Foursquare's 1-4 price tier filter.
        limit: max results (Foursquare caps at 50).
        near: city or place string ("Lagos, Nigeria"). Used when ``ll``
            is not provided.
        ll: ``"lat,lng"`` string. Preferred over ``near`` when known.

    Returns:
        List of normalized dish-shaped dicts (see module docstring for
        the canonical fields).
    """
    if not settings.FOURSQUARE_API_KEY:
        logger.error("foursquare.search called but FOURSQUARE_API_KEY is empty")
        return []

    params = _build_search_params(
        query=query,
        cuisine=cuisine,
        price_range=price_range,
        limit=limit,
        near=near,
        ll=ll,
    )
    url = f"{settings.FOURSQUARE_BASE_URL.rstrip('/')}{_SEARCH_PATH}"

    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=_headers()) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(
                        "foursquare.search non-200: status=%d body=%s",
                        resp.status,
                        body[:300],
                    )
                    return []
                data = await resp.json()
    except Exception:
        logger.exception("foursquare.search request failed")
        return []

    places = data.get("results") or []
    return [_normalize_place(p) for p in places]


async def get_menu_data(restaurant_id: str) -> Dict[str, Any]:
    """Foursquare doesn't expose menu data; return restaurant metadata only.

    For real menu data we'd need a separate provider (a curated DB,
    or a TinyFish-style enrichment pipeline scraping each restaurant's
    own menu page).
    """
    if not restaurant_id or not settings.FOURSQUARE_API_KEY:
        return {}

    url = f"{settings.FOURSQUARE_BASE_URL.rstrip('/')}/places/{restaurant_id}"
    params = {
        "fields": "fsq_id,name,categories,location,price,rating,description,website,tel,hours"
    }
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=_headers()) as resp:
                if resp.status != 200:
                    return {}
                place = await resp.json()
    except Exception:
        logger.exception("foursquare.get_menu_data failed for id=%s", restaurant_id)
        return {}

    normalized = _normalize_place(place)
    return {
        "restaurant": normalized["name"],
        "cuisine": normalized["cuisine"],
        "address": normalized.get("address"),
        "rating": normalized.get("rating"),
        "price_range": normalized.get("price_range"),
        "lat": normalized.get("lat"),
        "lng": normalized.get("lng"),
        # No per-dish menu in foursquare-only mode.
        "dishes": [],
        "menu_disclaimer": (
            "Foursquare does not expose per-dish menu data. "
            "Menu and ingredient information are not available."
        ),
    }


async def place_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Foursquare is read-only for restaurant data. We don't place real
    orders here — the food agent persists the Order to Neo4j and
    returns a synthetic provider id, same shape as the mock provider.
    """
    import uuid

    return {
        "provider": "foursquare",
        "provider_order_id": f"fsq-mock-{uuid.uuid4().hex[:8]}",
        "status": "pending_payment",
        "note": (
            "Foursquare provides restaurant discovery only. Real order "
            "placement requires a delivery / commerce partner integration."
        ),
        **order_data,
    }
