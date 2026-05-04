"""
LangGraph for the profile / context manager agent.

Most of the value of the profile agent is its synchronous read API
(``get_user_context``), called from other agents' ``context_node``s.
The graph itself is small — it exists so the agent fits the BaseAgent
pattern and so background events (e.g. "food agent observed a new
visit, please normalize and persist") have a path through the same
chassis other agents use.

Nodes:

* ``load_profile`` — pull canonical fields from Neo4j ``User``.
* ``load_graph``   — pull intent-relevant ContextBundle from Graphiti.
* ``snapshot``     — merge the two layers into a ``UserContextSnapshot``,
                     stash it on state as a dict.
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.graph import END, StateGraph

from src.app.core.database import run_in_thread
from src.app.models.user import User
from src.app.services.graphiti import retriever
from src.app.services.graphiti.entity_types import RELEVANT_BY_INTENT

from .snapshot import UserContextSnapshot
from .state import ProfileAgentState

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- nodes


async def load_profile_node(state: ProfileAgentState) -> ProfileAgentState:
    """Fetch the User neomodel node off the event loop."""
    user_id = state.get("user_id")
    if not user_id:
        return state

    try:
        user = await run_in_thread(User.nodes.filter(uid=user_id).first)
    except Exception:
        logger.exception("profile_agent.load_profile failed for user_id=%s", user_id)
        user = None

    # Stash the live neomodel object on state for the snapshot node;
    # the underscore prefix flags it as transient (snapshot_node strips
    # it before letting state be checkpointed).
    state["_user_node"] = user  # type: ignore[typeddict-item]
    return state


async def load_graph_node(state: ProfileAgentState) -> ProfileAgentState:
    """Pull intent-relevant Graphiti facts."""
    user_id = state.get("user_id")
    if not user_id:
        state["retrieved_context"] = {}
        return state

    intent = state.get("intent") or "profile"
    kinds = RELEVANT_BY_INTENT.get(intent)

    bundle = await retriever.get_relevant_context(
        user_id=user_id,
        query=_query_for_intent(intent),
        kinds=kinds,
        intent=intent,
    )
    state["retrieved_context"] = bundle.to_dict()
    return state


async def snapshot_node(state: ProfileAgentState) -> ProfileAgentState:
    """Merge profile + graph context into a UserContextSnapshot dict."""
    user_id = state.get("user_id") or ""
    intent = state.get("intent") or "profile"
    user = state.get("_user_node")  # type: ignore[typeddict-item]

    snapshot = UserContextSnapshot.from_user_and_graph(
        user_id=user_id,
        intent=intent,
        user=user,
        graph_context=state.get("retrieved_context") or {},
        recent_visits=[],  # populated when the food agent starts writing visits (Phase 4)
    )
    state["snapshot"] = snapshot.to_dict()
    state["status"] = "ready"

    # Strip the live neomodel reference — not JSON-serializable, would
    # break RedisSaver round-trip.
    state.pop("_user_node", None)  # type: ignore[arg-type]
    return state


# ----------------------------------------------------------- builder


def compose_workflow(
    workflow: StateGraph,
    *,
    set_entry: bool = True,
    leaf_target: Optional[str] = None,
) -> None:
    """Register the profile-agent graph onto ``workflow``.

    Args:
        workflow: an empty ``StateGraph`` to populate.
        set_entry: if True, sets ``load_profile`` as the entry point.
        leaf_target: where ``snapshot`` should route to. Defaults to ``END``.
    """
    workflow.add_node("load_profile", load_profile_node)
    workflow.add_node("load_graph", load_graph_node)
    workflow.add_node("snapshot", snapshot_node)

    if set_entry:
        workflow.set_entry_point("load_profile")
    workflow.add_edge("load_profile", "load_graph")
    workflow.add_edge("load_graph", "snapshot")
    workflow.add_edge("snapshot", leaf_target or END)


# ------------------------------------------------------------- helpers


def _query_for_intent(intent: str) -> str:
    """Pick a search query string the retriever can use as the seed."""
    if intent == "food":
        return "dietary preferences allergies cuisine restaurant history"
    if intent == "travel":
        return "travel destinations cultural context recent location"
    if intent == "social":
        return "social connections shared interests cultural background"
    return "user profile preferences allergies cuisine cultural"
