from .nodes import (
    transcription_node,
    information_extraction_node,
    onboarding_complete_node,
    generate_response_node,
    end_interaction_node,
    is_onboarded,
    needs_more_info,
)
from .state import OnboardingAgentState
from langgraph.graph import StateGraph, END
from typing import Union
import logging


def create_onboarding_agent_graph():
    """Create and return the onboarding agent graph"""

    # Initialize the graph
    workflow = StateGraph(OnboardingAgentState)

    # Add nodes
    workflow.add_node("transcription", transcription_node)
    workflow.add_node("info_extraction", information_extraction_node)
    workflow.add_node("onboarding_complete", onboarding_complete_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("end_interaction", end_interaction_node)

    # Set entry point
    workflow.set_entry_point("transcription")

    # Add edges with conditions
    workflow.add_edge("transcription", "info_extraction")

    # From info_extraction
    workflow.add_conditional_edges(
        "info_extraction",
        lambda state: (
            "generate_response" if needs_more_info(state) else "onboarding_complete"
        ),
        {"generate_response": "generate_response", "onboarding_complete": "onboarding_complete"},
    )

    # From onboarding_complete
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

    # From generate_response - always END (wait for new user input)
    workflow.add_edge("generate_response", END)

    # End interaction leads to END
    workflow.add_edge("end_interaction", END)

    return workflow.compile()


# Usage example
async def run_onboarding_agent(user_input: Union[bytes, str], existing_user_data: dict = None) -> OnboardingAgentState:
    """Run the onboarding agent with user input and existing user data"""

    # Create the graph
    graph = create_onboarding_agent_graph()

    # Initial state with existing user data
    initial_state = OnboardingAgentState(
        user_input=user_input,
        extracted_information=existing_user_data or {},
        onboarding_status="pending_info",
        messages=[],
    )

    # Run the graph
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state
    except Exception as e:
        logging.error(f"Graph execution failed: {str(e)}")
        return OnboardingAgentState(
            error=str(e),
            system_response="An error occurred during onboarding. Please try again.",
        )


# For handling ongoing conversations (if needed)
async def continue_onboarding_conversation(
        current_state: OnboardingAgentState, new_input: Union[bytes, str]
) -> OnboardingAgentState:
    """Continue an ongoing onboarding conversation"""

    graph = create_onboarding_agent_graph()
    current_state["user_input"] = new_input
    final_state = await graph.ainvoke(current_state)
    return final_state
