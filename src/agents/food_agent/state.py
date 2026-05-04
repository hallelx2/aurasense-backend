"""FoodAgentState — extends BaseAgentState for the food agent's graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.agents.base.state import BaseAgentState


class FoodAgentState(BaseAgentState, total=False):
    """State carried through the food agent's LangGraph.

    Lives in Redis via the shared AsyncRedisSaver — every value below
    must be JSON-serializable for clean round-trip.
    """

    # The classified intent this turn (recommend / reorder / followup / etc.).
    food_intent: str

    # When the user is selecting from a previous list of recs, the index
    # they pointed at. Set by the intent_node, read by place_order_node.
    selected_index: Optional[int]

    # The UserContextSnapshot.to_dict() pulled from profile_service —
    # used by health_screen + recommend nodes.
    user_context: Dict[str, Any]

    # Hard filters built from allergies + dietary restrictions. The
    # search node prepends them to the LLM context; the post-filter
    # uses them as the deterministic safety check.
    allergens: List[str]
    dietary_restrictions: List[str]

    # The cuisine / location filters the search node passed to the
    # external food service.
    search_query: str
    search_results: List[Dict[str, Any]]

    # The ranked recommendations produced this turn (after allergy
    # post-filter). Each item is a FoodRecommendation.model_dump().
    recommendations: List[Dict[str, Any]]

    # The recommendations that were rejected by the allergy filter.
    # Surfaced to logs / observability; never sent to the user verbatim
    # so they don't see a "we considered peanut chicken but rejected
    # it" line which is just unnerving.
    rejected_recommendations: List[Dict[str, Any]]

    # If the user confirmed an order, the resulting Order dict (uid,
    # restaurant_name, dish_name, status, ...).
    placed_order: Optional[Dict[str, Any]]
