"""
ProfileAgent — the cross-cutting agent every other specialist reads from.

Role:
* **Owns the ``UserContextSnapshot`` shape**: every other agent obtains
  user context by calling ``profile_service.get_user_context(user_id, intent)``
  rather than poking at Neo4j or Graphiti directly.
* Wraps a tiny LangGraph (``load_profile -> load_graph -> snapshot``) so
  it follows the BaseAgent pattern and works with the shared
  ``AsyncRedisSaver`` checkpointer.

Read-API helpers exposed at the class level:

* ``await profile_agent.get_user_context(user_id, intent="food")``
  → ``UserContextSnapshot``

These delegate to the compiled graph so the same code path runs whether
called synchronously by other agents or through the supervisor's
``Send`` mechanism in Phase 4+.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph

from src.agents.base import BaseAgent

from .graph import compose_workflow
from .snapshot import UserContextSnapshot
from .state import ProfileAgentState

logger = logging.getLogger(__name__)


class ProfileAgent(BaseAgent[ProfileAgentState]):
    name = "profile"
    state_cls = ProfileAgentState
    relevant_entity_types = [
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "FoodPreference",
        "CulturalContext",
        "RestaurantVisit",
    ]
    llm_role = "profile"

    def build_graph(self, workflow: StateGraph) -> None:
        compose_workflow(workflow)

    # ----------------------------------------------- Public read API

    async def get_user_context(
        self,
        user_id: str,
        *,
        intent: str = "profile",
        thread_id: Optional[str] = None,
    ) -> UserContextSnapshot:
        """Build a ``UserContextSnapshot`` for ``user_id`` filtered by intent.

        This is the function every other agent calls (via
        ``profile_service.get_user_context``) to fetch personalization
        data before responding. It runs the agent's tiny graph end-to-end
        and reconstructs the typed dataclass from the resulting state.

        Args:
            user_id: ``User.uid``. Used as both the Neo4j lookup key and
                the Graphiti ``group_id``.
            intent: drives Graphiti kind filtering and snapshot shape
                (``food`` / ``travel`` / ``social`` / ``profile``).
            thread_id: optional override. By default each call gets its
                own short-lived checkpoint thread (``profile:{uid}:{intent}``)
                so concurrent reads for different intents don't clobber
                each other.

        Returns:
            A ``UserContextSnapshot``. Always returns a snapshot — on
            internal errors the snapshot is empty (callers can rely on
            the shape, but should check ``snapshot.is_onboarded`` and
            other flags before using the data).
        """
        if not user_id:
            return UserContextSnapshot.empty(user_id="", intent=intent)

        thread = thread_id or self.thread_id_for(user_id, suffix=intent)
        initial: ProfileAgentState = {
            "user_id": user_id,
            "group_id": user_id,
            "thread_id": thread,
            "agent_name": self.name,
            "intent": intent,
            "status": "pending_info",
        }

        try:
            final_state: Dict[str, Any] = await self.ainvoke(initial, thread_id=thread)
        except Exception:
            logger.exception(
                "profile_agent.get_user_context failed user=%s intent=%s",
                user_id,
                intent,
            )
            return UserContextSnapshot.empty(user_id=user_id, intent=intent)

        snap_dict = final_state.get("snapshot")
        if not snap_dict:
            return UserContextSnapshot.empty(user_id=user_id, intent=intent)

        # Reconstruct the dataclass from the dict.
        snap = UserContextSnapshot(
            user_id=snap_dict.get("user_id", user_id),
            intent=snap_dict.get("intent", intent),
            profile=snap_dict.get("profile") or {},
            graph_context=snap_dict.get("graph_context") or {},
            allergies=list(snap_dict.get("allergies") or []),
            dietary_restrictions=list(snap_dict.get("dietary_restrictions") or []),
            cuisines_liked=list(snap_dict.get("cuisines_liked") or []),
            cultural_background=list(snap_dict.get("cultural_background") or []),
            health_conditions=list(snap_dict.get("health_conditions") or []),
            recent_visits=list(snap_dict.get("recent_visits") or []),
            is_onboarded=bool(snap_dict.get("is_onboarded", False)),
        )
        return snap


# Module-level singleton.
profile_agent = ProfileAgent()
