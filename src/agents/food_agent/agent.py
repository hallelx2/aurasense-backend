"""
FoodAgent — the first specialist agent that delivers product value.

Extends :class:`BaseAgent`. Reads from the Profile agent via
``profile_service`` (channel #1 of cross-agent collaboration), writes
recommendations / visits to Graphiti via ``contract`` (channel #3),
and exposes a stable WebSocket interface through the supervisor (channel
#2 lands here in Phase 4 too).

The graph runs ``intent → context → health_screen → search → recommend
→ confirm_or_order → (place_order →) record``. The deterministic
allergy filter inside ``recommend_node`` is the safety boundary; the
LLM is never trusted to be the final filter.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph

from src.agents.base import BaseAgent

from .graph import compose_workflow
from .state import FoodAgentState

logger = logging.getLogger(__name__)


class FoodAgent(BaseAgent[FoodAgentState]):
    name = "food"
    state_cls = FoodAgentState
    relevant_entity_types = [
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "FoodPreference",
        "CulturalContext",
        "RestaurantVisit",
    ]
    llm_role = "food"

    def build_graph(self, workflow: StateGraph) -> None:
        compose_workflow(workflow, llm=self.llm)


# Module-level singleton.
food_agent = FoodAgent()
