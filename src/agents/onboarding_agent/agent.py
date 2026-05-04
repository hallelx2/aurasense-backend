"""
OnboardingAgent — voice-first conversational onboarding wrapped in the
:class:`BaseAgent` chassis.

The graph is built once per process in :meth:`build_graph` and compiled
with the shared :class:`AsyncRedisSaver`, so multi-turn state survives
backend restarts and scales across workers.

Audio transcription is the responsibility of the **caller** (the WS
route, or the future supervisor's transcribe node). This agent only
operates on text — its state never carries raw bytes, which keeps every
checkpoint round-trip clean through Redis.

Phase-2 wiring: the graph runs as a sandwich:

    context  (read Graphiti for prior facts about this user)
       ↓
    transcription → info_extraction → ...   (existing onboarding wiring)
       ↓
    record   (write this turn's utterance + extracted facts to Graphiti)
       ↓
    END

So every turn pulls memory before responding and persists facts after,
which is what makes onboarding actually personalize across sessions.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.base import BaseAgent
from src.app.services.graphiti import contract

from .state import OnboardingAgentState


class OnboardingAgent(BaseAgent[OnboardingAgentState]):
    name = "onboarding"
    state_cls = OnboardingAgentState
    relevant_entity_types = [
        "FoodPreference",
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "CulturalContext",
    ]
    llm_role = "onboarding"

    def build_graph(self, workflow: StateGraph) -> None:
        from .graph import _compose_workflow

        # Add the read + write sandwich nodes first.
        workflow.add_node("context", self._context_node_for_onboarding)
        workflow.add_node("record", self._record_node_for_onboarding)

        # Compose the existing onboarding wiring, but redirect the leaf
        # nodes (`generate_response`, `end_interaction`) at the record
        # node instead of straight at END.
        _compose_workflow(workflow, set_entry=False, leaf_target="record")

        # Stitch context in front; record terminates the turn.
        workflow.set_entry_point("context")
        workflow.add_edge("context", "transcription")
        workflow.add_edge("record", END)

    # ----------------------------------------------- node implementations

    async def _context_node_for_onboarding(
        self, state: OnboardingAgentState
    ) -> OnboardingAgentState:
        """Pull prior knowledge from Graphiti.

        Delegates to :meth:`BaseAgent.context_node`, which stores the
        result as a JSON-safe dict under ``state["retrieved_context"]``.
        """
        return await self.context_node(state)

    async def _record_node_for_onboarding(
        self, state: OnboardingAgentState
    ) -> OnboardingAgentState:
        """Persist this turn into Graphiti — utterance + structured facts.

        Two episodes per turn:
          * ``record_user_utterance``: the post-STT text. Stored as a
            ``message`` episode so Graphiti's entity extractor picks up
            casually-mentioned allergies / cuisines / etc.
          * ``record_extracted_facts``: the structured ``UserInformation``
            dict from the extractor. JSON episode → typed entities lift
            cleanly when the LLM sees the schema explicitly.

        Both writes are best-effort — :mod:`contract` swallows + logs
        Graphiti errors so the user-facing flow always returns a response.
        """
        user_id = state.get("user_id")
        if not user_id:
            return state

        utterance = state.get("transcribed_text") or state.get("user_input") or ""
        if isinstance(utterance, str) and utterance.strip():
            await contract.record_user_utterance(
                user_id=user_id,
                transcript=utterance,
                agent_name=self.name,
            )

        facts = state.get("extracted_information") or {}
        if facts:
            await contract.record_extracted_facts(
                user_id=user_id,
                facts=facts,
                agent_name=self.name,
            )

        return state


# Module-level singleton so callers can do `onboarding_agent.ainvoke(...)`.
onboarding_agent = OnboardingAgent()
