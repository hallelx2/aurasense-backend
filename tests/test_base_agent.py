"""Unit tests for BaseAgent + collaboration helpers.

These tests deliberately avoid spinning up Redis — they exercise the
class machinery (subclass contract, handoff helper, thread-id policy,
gateway-backed `llm` property) without compiling any graph.
"""

from __future__ import annotations

import pytest
from langgraph.graph import StateGraph

from src.agents.base import (
    MAX_HANDOFFS_PER_TURN,
    BaseAgent,
    BaseAgentState,
    handoff_trail,
    request_handoff,
)


class _ToyAgent(BaseAgent[BaseAgentState]):
    name = "toy"
    state_cls = BaseAgentState
    relevant_entity_types = []
    llm_role = "agent"

    def build_graph(self, workflow: StateGraph) -> None:
        async def passthrough(state: BaseAgentState) -> BaseAgentState:
            return state

        workflow.add_node("n", passthrough)
        workflow.set_entry_point("n")
        workflow.set_finish_point("n")


class TestBaseAgent:
    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_subclass_instantiates(self) -> None:
        a = _ToyAgent()
        assert a.name == "toy"

    def test_thread_id_pattern(self) -> None:
        a = _ToyAgent()
        assert a.thread_id_for("user-abc") == "toy:user-abc"

    def test_thread_id_with_suffix(self) -> None:
        a = _ToyAgent()
        assert a.thread_id_for("user-abc", "session-1") == "toy:user-abc:session-1"

    def test_llm_uses_gateway(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("LLM_PROFILE_DEFAULT", "groq:llama-3.3-70b-versatile")

        # Ensure the gateway picks up the new env: clear its cache.
        from src.app.services.llm_gateway import gateway

        gateway.reset_cache()

        a = _ToyAgent()
        from langchain_core.language_models import BaseChatModel

        assert isinstance(a.llm, BaseChatModel)


class TestHandoff:
    def test_request_handoff_sets_status_and_target(self) -> None:
        state: BaseAgentState = {}
        out = request_handoff(state, target="food", reason="user wants food", source="travel")
        assert out["status"] == "needs_handoff"
        assert out["handoff_to"] == "food"
        assert out["handoff_trail"] == [
            {"from": "travel", "to": "food", "reason": "user wants food"}
        ]

    def test_request_handoff_appends_to_existing_trail(self) -> None:
        state: BaseAgentState = {
            "handoff_trail": [{"from": "supervisor", "to": "travel", "reason": "geo"}]
        }
        request_handoff(state, target="food", reason="dietary", source="travel")
        assert len(state["handoff_trail"]) == 2
        assert state["handoff_trail"][-1]["to"] == "food"

    def test_handoff_trail_returns_copy(self) -> None:
        state: BaseAgentState = {"handoff_trail": [{"from": "a", "to": "b", "reason": ""}]}
        trail = handoff_trail(state)
        trail.append({"from": "b", "to": "c", "reason": ""})
        # Original state unchanged because handoff_trail returns a list copy.
        assert len(state["handoff_trail"]) == 1

    def test_handoff_trail_handles_missing_field(self) -> None:
        assert handoff_trail({}) == []

    def test_agent_hand_off_to(self) -> None:
        a = _ToyAgent()
        state: BaseAgentState = {}
        out = a.hand_off_to(state, "food", reason="user asked for food")
        assert out["handoff_to"] == "food"
        assert out["handoff_trail"][0]["from"] == "toy"

    def test_max_handoffs_constant_is_sane(self) -> None:
        assert isinstance(MAX_HANDOFFS_PER_TURN, int)
        assert 1 <= MAX_HANDOFFS_PER_TURN <= 10
