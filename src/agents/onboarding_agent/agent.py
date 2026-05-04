"""
OnboardingAgent — voice-first conversational onboarding wrapped in the
:class:`BaseAgent` chassis.

The graph is built once per process in :meth:`build_graph` (delegating to
:func:`onboarding_agent.graph._compose_workflow` which holds the existing
node wiring) and compiled with the shared :class:`AsyncRedisSaver`, so
multi-turn state survives backend restarts and scales across workers.

Audio transcription is the responsibility of the **caller** (the WS
route, or the future supervisor's transcribe node). This agent only
operates on text — its state never carries raw bytes, which keeps every
checkpoint round-trip clean through Redis.
"""

from __future__ import annotations

from langgraph.graph import StateGraph

from src.agents.base import BaseAgent

from .state import OnboardingAgentState


class OnboardingAgent(BaseAgent[OnboardingAgentState]):
    name = "onboarding"
    state_cls = OnboardingAgentState
    relevant_entity_types = [
        # Onboarding mainly *writes* facts. Reads come from the user's prior
        # session (if any). These types map to the Phase-2 Graphiti schema.
        "FoodPreference",
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "CulturalContext",
    ]
    llm_role = "onboarding"

    def build_graph(self, workflow: StateGraph) -> None:
        from .graph import _compose_workflow

        _compose_workflow(workflow)


# Module-level singleton so callers can do `onboarding_agent.ainvoke(...)`.
onboarding_agent = OnboardingAgent()
