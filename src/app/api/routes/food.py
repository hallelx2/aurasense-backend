"""
Food REST routes — CRUD only.

Anything *conversational* (recommendation, ordering via voice) goes
through the WebSocket at ``/ws/agent``. This module exposes the
read-only resource endpoints a frontend uses to render menus, restaurant
details, and order history.

Every endpoint requires authentication via ``Depends(get_current_user)``
— this is a hard rule for any non-public route, and the audit flagged
the previous food.py for being open by default.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.app.api.dependencies.auth import get_current_user
from src.app.core.database import run_in_thread
from src.app.models.user import User
from src.app.services.mcp_service import mcp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/food", tags=["food"])


# --------------------------------------------------- read-only endpoints


@router.get("/restaurants")
async def list_restaurants(
    cuisine: Optional[str] = Query(None, description="Filter by cuisine."),
    price_range: Optional[str] = Query(
        None, description="One of: budget, mid-range, premium, luxury."
    ),
    q: Optional[str] = Query(None, description="Free-text search."),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List restaurants / dishes matching the filters."""
    return await mcp_service.search_restaurants(
        query=q or "",
        cuisine=cuisine,
        price_range=price_range,
        limit=limit,
    )


@router.get("/restaurants/{restaurant_id}")
async def get_restaurant_details(
    restaurant_id: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a restaurant's menu/details."""
    data = await mcp_service.get_menu_data(restaurant_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant not found: {restaurant_id}",
        )
    return data


@router.get("/orders")
async def list_my_orders(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Return the authenticated user's recent orders."""
    return await run_in_thread(_list_orders_for_user, user, limit)


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a specific order belonging to the authenticated user."""
    order = await run_in_thread(_get_order_for_user, user, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return order


# --------------------------------------------------- helpers (sync neomodel)


def _list_orders_for_user(user: User, limit: int) -> List[Dict[str, Any]]:
    """Pull the user's connected Order nodes via neomodel."""
    try:
        orders = list(user.orders.all())
    except Exception:
        logger.exception("food.list_orders failed for user=%s", user.uid)
        return []
    out: List[Dict[str, Any]] = []
    for o in orders[:limit]:
        out.append(_order_to_dict(o))
    return out


def _get_order_for_user(user: User, order_id: str) -> Optional[Dict[str, Any]]:
    try:
        for o in user.orders.all():
            if getattr(o, "uid", None) == order_id:
                return _order_to_dict(o)
    except Exception:
        logger.exception(
            "food.get_order failed for user=%s order=%s", user.uid, order_id
        )
    return None


def _order_to_dict(order: Any) -> Dict[str, Any]:
    return {
        "uid": getattr(order, "uid", None),
        "restaurant_name": getattr(order, "restaurant_name", None),
        "dish_name": getattr(order, "dish_name", None),
        "status": getattr(order, "status", None),
        "total_amount": getattr(order, "total_amount", None),
        "ordered_at": (
            order.ordered_at.isoformat()
            if getattr(order, "ordered_at", None) is not None
            else None
        ),
    }
