"""
Onboarding agent graph definition.

The canonical entry point is :class:`OnboardingAgent` (in ``agent.py``),
which compiles this graph with the shared async Redis checkpointer.

The legacy module-level functions ``run_onboarding_agent`` and
``continue_onboarding_conversation`` are kept as thin compatibility shims
so callers that still import them (currently the WS route, until its
own migration lands) keep working. Both now delegate to the agent class
and honor the same checkpointed thread.
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.graph import END, StateGraph

from .nodes import (
    end_interaction_node,
    generate_response_node,
    information_extraction_node,
    is_onboarded,
    needs_more_info,
    onboarding_complete_node,
    transcription_node,
)
from .state import OnboardingAgentState

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Graph composition (used by both the legacy factory and OnboardingAgent)
# --------------------------------------------------------------------------


def _compose_workflow(workflow: StateGraph) -> None:
    """Register the onboarding nodes + edges on ``workflow``.

    Pulled out so :class:`OnboardingAgent` can reuse the wiring without
    re-creating the StateGraph itself.
    """
    workflow.add_node("transcription", transcription_node)
    workflow.add_node("info_extraction", information_extraction_node)
    workflow.add_node("onboarding_complete", onboarding_complete_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("end_interaction", end_interaction_node)

    workflow.set_entry_point("transcription")
    workflow.add_edge("transcription", "info_extraction")

    workflow.add_conditional_edges(
        "info_extraction",
        lambda state: (
            "generate_response" if needs_more_info(state) else "onboarding_complete"
        ),
        {
            "generate_response": "generate_response",
            "onboarding_complete": "onboarding_complete",
        },
    )

    workflow.add_conditional_edges(
        "onboarding_complete",
        lambda state: (
            "end_interaction" if is_onboarded(state) else "generate_response"
        ),
        {
            "end_interaction": "end_interaction",
            "generate_response": "generate_response",
        },
    )

    workflow.add_edge("generate_response", END)
    workflow.add_edge("end_interaction", END)


def create_onboarding_agent_graph():
    """Legacy in-memory graph factory (no checkpointer).

    Kept for tests and ad-hoc scripts that want a stateless graph; the
    production WS path uses :class:`OnboardingAgent`'s checkpointed
    compilation instead.
    """
    workflow = StateGraph(OnboardingAgentState)
    _compose_workflow(workflow)
    return workflow.compile()


# --------------------------------------------------------------------------
# Legacy entry-point shims — delegate to OnboardingAgent so behaviour is
# identical between the old module-level callers and the new class API.
# --------------------------------------------------------------------------


async def run_onboarding_agent(
    user_input: str,
    existing_user_data: Optional[dict] = None,
    *,
    thread_id: Optional[str] = None,
) -> OnboardingAgentState:
    """Run the onboarding agent for a fresh conversation turn.

    ``user_input`` MUST be text. Audio transcription happens upstream in
    the WS handler (or, after Phase 1c, in the supervisor's transcribe
    node). The graph state is checkpointed in Redis under ``thread_id``;
    when omitted, a temporary uncheckpointed graph is used so this
    function still works in scripts that don't care about persistence.
    """
    from .agent import onboarding_agent

    initial_state = OnboardingAgentState(
        user_input=user_input,
        extracted_information=existing_user_data or {},
        onboarding_status="pending_info",
        messages=[],
    )

    if thread_id is None:
        # Stateless invocation (tests, CLI). Compile a fresh in-memory graph.
        graph = create_onboarding_agent_graph()
        try:
            return await graph.ainvoke(initial_state)
        except Exception as e:
            logger.exception("stateless onboarding graph failed")
            return OnboardingAgentState(
                error=str(e),
                system_response="An error occurred during onboarding. Please try again.",
            )

    try:
        return await onboarding_agent.ainvoke(initial_state, thread_id=thread_id)
    except Exception as e:
        logger.exception("checkpointed onboarding graph failed")
        return OnboardingAgentState(
            error=str(e),
            system_response="An error occurred during onboarding. Please try again.",
        )


async def continue_onboarding_conversation(
    current_state: OnboardingAgentState,
    new_input: str,
    *,
    thread_id: Optional[str] = None,
) -> OnboardingAgentState:
    """Continue an in-flight conversation with a new text input.

    With ``thread_id`` set, checkpointed state is restored from Redis (so
    ``current_state`` is essentially a hint — RedisSaver is the source of
    truth). Without ``thread_id``, falls back to passing ``current_state``
    explicitly through a stateless graph.
    """
    from .agent import onboarding_agent

    new_state: OnboardingAgentState = {**current_state, "user_input": new_input}

    if thread_id is None:
        graph = create_onboarding_agent_graph()
        return await graph.ainvoke(new_state)

    return await onboarding_agent.ainvoke(new_state, thread_id=thread_id)
