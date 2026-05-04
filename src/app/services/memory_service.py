"""
Back-compat shim for the legacy ``memory_service`` import sites.

The real Graphiti integration now lives in
:mod:`src.app.services.graphiti.contract` (writes) and
:mod:`src.app.services.graphiti.retriever` (reads). This module exists
only so existing call sites in :mod:`src.app.api.routes.auth` (and any
yet-to-be-migrated services) keep working without touching them in this
phase.

New code should import from ``services.graphiti.contract`` /
``services.graphiti.retriever`` directly. This module will be deleted
once the auth route migration lands.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.app.models.user import User

from .graphiti import contract, retriever

logger = logging.getLogger(__name__)


class MemoryService:
    """Thin pass-through over the Graphiti contract module."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("memory_service")

    async def cleanup(self) -> None:
        """No-op: the Graphiti SDK lifecycle is owned by ``services.graphiti.client``."""
        from .graphiti.client import close_graphiti

        await close_graphiti()

    # ------------------------------------------------------------- Writes

    async def store_user_memory(
        self, user_id: str, memory_data: Dict[str, Any]
    ) -> bool:
        """Generic write — used by callers that pass ad-hoc payloads."""
        metadata = memory_data.get("metadata", {}) if memory_data else {}
        event_type = metadata.get("event_type", "user_event")
        try:
            await contract.record_user_event(
                user_id=user_id,
                event_type=event_type,
                payload={
                    "content": memory_data.get("content"),
                    **metadata,
                },
            )
            return True
        except Exception:
            self.logger.exception("store_user_memory failed for user_id=%s", user_id)
            return False

    async def store_user_registration(self, user: User) -> bool:
        try:
            await contract.record_user_event(
                user_id=user.uid,
                event_type="user_registration",
                payload={
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": getattr(user, "username", None),
                    "registration_date": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                },
                agent_name="auth",
            )
            return True
        except Exception:
            self.logger.exception("store_user_registration failed for %s", user.uid)
            return False

    async def store_user_login(self, user: User) -> bool:
        try:
            await contract.record_user_event(
                user_id=user.uid,
                event_type="user_login",
                payload={
                    "email": user.email,
                    "login_timestamp": (
                        user.last_active.isoformat() if user.last_active else None
                    ),
                },
                agent_name="auth",
            )
            return True
        except Exception:
            self.logger.exception("store_user_login failed for %s", user.uid)
            return False

    async def store_user_logout(self, user_id: str) -> bool:
        try:
            await contract.record_user_event(
                user_id=user_id,
                event_type="user_logout",
                payload={},
                agent_name="auth",
            )
            return True
        except Exception:
            self.logger.exception("store_user_logout failed for %s", user_id)
            return False

    # -------------------------------------------------------------- Reads

    async def retrieve_user_memories(
        self,
        user_id: str,
        query: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Backwards-compatible read. New code should call retriever directly."""
        bundle = await retriever.get_relevant_context(
            user_id=user_id,
            query=query or "user profile",
            num_results=limit,
        )
        return [{"fact": f} for f in bundle.facts]

    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        bundle = await retriever.get_relevant_context(
            user_id=user_id,
            query="recent activity preferences profile",
            intent="profile",
        )
        return bundle.to_dict()


memory_service = MemoryService()
