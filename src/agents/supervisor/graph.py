"""
Supervisor LangGraph build + module-level singleton.

Single graph for the ``/ws/agent`` route. Routes user messages to
``onboarding_agent`` / ``food_agent`` / ``profile_agent`` based on the
classified intent. After a specialist runs, ``route_after_specialist``
inspects ``state.handoff_to`` for cross-agent handoffs (capped by
``MAX_HANDOFFS_PER_TURN``).

Sub-graphs are inlined onto the same workflow by re-using each
specialist's ``compose_workflow`` helper, so the supervisor's
StateGraph carries the typed nodes directly. One shared
``AsyncRedisSaver`` checkpoints the whole flow under a single
thread per ``(supervisor, user)`` pair.

State note: at runtime LangGraph state is a plain dict, so each
specialist's domain-specific fields (e.g. food agent's ``allergens``,
``recommendations``) just live alongside ``SupervisorState`` fields on
the same dict. TypedDicts are type-check time only.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.base import get_async_redis_saver
from src.app.services.llm_gateway import gateway

from .nodes import (
    classify_node,
    finish_node,
    ingest_node,
    off_topic_node,
    onboarding_gate_node,
    route_after_specialist,
    route_to_specialist,
)
from .state import SupervisorState

logger = logging.getLogger(__name__)


# Each specialist's ``compose_workflow`` is invoked with set_entry=False
# (so the supervisor controls entry) and leaf_target="finish" (so the
# specialist's terminal nodes route back to the supervisor's finish).


def _wire_onboarding(workflow: StateGraph) -> None:
    from src.agents.onboarding_agent.graph import _compose_workflow

    _compose_workflow(workflow, set_entry=False, leaf_target="finish")


def _wire_food(workflow: StateGraph) -> None:
    from src.agents.food_agent.graph import compose_workflow

    compose_workflow(
        workflow,
        llm=gateway.get_llm("food"),
        set_entry=False,
        leaf_target="finish",
    )


def _wire_profile(workflow: StateGraph) -> None:
    from src.agents.profile_agent.graph import compose_workflow

    compose_workflow(workflow, set_entry=False, leaf_target="finish")


def build_supervisor() -> Any:
    """Compile and return the supervisor StateGraph (Redis-checkpointed)."""
    workflow = StateGraph(SupervisorState)

    # ---- Top-level supervisor nodes ----
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("onboarding_gate", onboarding_gate_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("off_topic_response", off_topic_node)
    workflow.add_node("finish", finish_node)

    # ---- Specialist sub-graphs inlined onto the same workflow ----
    _wire_onboarding(workflow)  # entry node: "transcription"
    _wire_food(workflow)         # entry node: "intent"
    _wire_profile(workflow)      # entry node: "load_profile"

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "onboarding_gate")
    workflow.add_edge("onboarding_gate", "classify")

    # Conditional routing: classify → specialist entry by intent label.
    workflow.add_conditional_edges(
        "classify",
        route_to_specialist,
        {
            "onboarding": "transcription",
            "food": "intent",
            "profile": "load_profile",
            "off_topic_response": "off_topic_response",
        },
    )

    workflow.add_edge("off_topic_response", "finish")
    workflow.add_edge("finish", END)

    return workflow.compile(checkpointer=get_async_redis_saver())


@lru_cache(maxsize=1)
def get_supervisor_graph() -> Any:
    """Process-shared supervisor graph (compiled once, checkpointed in Redis)."""
    return build_supervisor()


def reset_supervisor_cache() -> None:
    """Clear the cached supervisor graph (used in tests that swap settings)."""
    get_supervisor_graph.cache_clear()
