"""LangGraph wiring for the food agent."""

from __future__ import annotations

import functools
from typing import Optional

from langgraph.graph import END, StateGraph

from .nodes import (
    confirm_or_order_node,
    context_node,
    health_screen_node,
    intent_node,
    needs_order_placement,
    place_order_node,
    recommend_node,
    record_node,
    search_node,
)


def compose_workflow(
    workflow: StateGraph,
    *,
    llm,
    set_entry: bool = True,
    leaf_target: Optional[str] = None,
) -> None:
    """Register the food-agent nodes + branching edges.

    Args:
        workflow: StateGraph(FoodAgentState) to populate.
        llm: BaseChatModel passed into the LLM-using nodes
            (``intent_node``, ``recommend_node``).
        set_entry: if True, sets ``intent`` as the entry point.
        leaf_target: where the terminal nodes (``record``,
            ``confirm_or_order`` when not ordering) route to. Defaults
            to ``END``.
    """
    target = leaf_target or END

    # LLM-using nodes need their llm injected at graph-build time.
    intent_with_llm = functools.partial(intent_node, llm=llm)
    recommend_with_llm = functools.partial(recommend_node, llm=llm)

    workflow.add_node("intent", intent_with_llm)
    workflow.add_node("context", context_node)
    workflow.add_node("health_screen", health_screen_node)
    workflow.add_node("search", search_node)
    workflow.add_node("recommend", recommend_with_llm)
    workflow.add_node("confirm_or_order", confirm_or_order_node)
    workflow.add_node("place_order", place_order_node)
    workflow.add_node("record", record_node)

    if set_entry:
        workflow.set_entry_point("intent")

    workflow.add_edge("intent", "context")
    workflow.add_edge("context", "health_screen")
    workflow.add_edge("health_screen", "search")
    workflow.add_edge("search", "recommend")
    workflow.add_edge("recommend", "confirm_or_order")

    # Conditional routing after confirm_or_order: place an order or skip.
    workflow.add_conditional_edges(
        "confirm_or_order",
        lambda state: "place_order" if needs_order_placement(state) else "record",
        {"place_order": "place_order", "record": "record"},
    )

    workflow.add_edge("place_order", "record")
    workflow.add_edge("record", target)
