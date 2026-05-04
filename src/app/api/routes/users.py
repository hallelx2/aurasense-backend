"""
User-resource REST routes.

Currently exposes:

* ``GET /users/me`` — the canonical "who am I" endpoint (also lives on
  ``/auth/me`` for back-compat; this one returns the same shape).
* ``GET /users/me/context`` — the personalization snapshot a frontend
  uses to render context-aware UI without an agent round-trip.

Resource-style CRUD only. Anything conversational still goes through
the WebSocket; this file stays pure REST.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, Query

from src.app.api.dependencies.auth import get_current_user
from src.app.models.user import User
from src.app.services.profile_service import profile_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# Recognized intent values. Validated by FastAPI's Query type so an
# invalid intent returns 422 with a clear error.
Intent = Literal["profile", "food", "travel", "social"]


@router.get("/me/context")
async def get_me_context(
    intent: Intent = Query(
        "profile",
        description=(
            "Which intent to shape the snapshot for. "
            "'food' → allergy/dietary/cuisine focus; "
            "'travel' → location/cultural focus; "
            "'social' → connections/cultural focus; "
            "'profile' → all kinds (default)."
        ),
    ),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a UserContextSnapshot for the authenticated user.

    The frontend uses this to render personalization cards (allergies,
    cuisine preferences, recent visits, etc.) without going through a
    WS turn. Backend agents typically call
    ``profile_service.get_user_context`` directly instead of this REST
    endpoint.
    """
    snapshot = await profile_service.get_user_context(
        user_id=user.uid, intent=intent
    )
    return snapshot.to_dict()
