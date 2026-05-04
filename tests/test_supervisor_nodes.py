"""Tests for the supervisor's node-level logic (no graph compile required).

The compile path needs a live Redis, so we test routing decisions and
classification in isolation here. End-to-end supervisor smoke is in the
make smoke-phase-4 target.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.supervisor.intents import IntentChoice, MIN_CONFIDENCE
from src.agents.supervisor.nodes import (
    classify_node,
    ingest_node,
    onboarding_gate_node,
    route_after_specialist,
    route_to_specialist,
)


class TestIngest:
    @pytest.mark.asyncio
    async def test_copies_user_input_when_no_transcript(self) -> None:
        state = {"user_input": "hello"}
        out = await ingest_node(state)
        assert out["transcribed_text"] == "hello"

    @pytest.mark.asyncio
    async def test_keeps_existing_transcript(self) -> None:
        state = {"user_input": "hello", "transcribed_text": "already done"}
        out = await ingest_node(state)
        assert out["transcribed_text"] == "already done"


class TestOnboardingGate:
    @pytest.mark.asyncio
    async def test_unonboarded_user_forced_to_onboarding(self) -> None:
        fake_user = SimpleNamespace(uid="u-1", is_onboarded=False)
        with patch(
            "src.agents.supervisor.nodes.run_in_thread",
            new=AsyncMock(return_value=fake_user),
        ):
            out = await onboarding_gate_node({"user_id": "u-1"})
        assert out["intent"] == "onboarding"
        assert out["onboarding_gate_forced"] is True

    @pytest.mark.asyncio
    async def test_onboarded_user_passes_through(self) -> None:
        fake_user = SimpleNamespace(uid="u-1", is_onboarded=True)
        with patch(
            "src.agents.supervisor.nodes.run_in_thread",
            new=AsyncMock(return_value=fake_user),
        ):
            out = await onboarding_gate_node({"user_id": "u-1"})
        assert out.get("onboarding_gate_forced") is False
        # Intent NOT pre-set; classify will decide.
        assert "intent" not in out or out.get("intent") in (None, "")

    @pytest.mark.asyncio
    async def test_no_user_id_passes_through(self) -> None:
        out = await onboarding_gate_node({})
        assert out["onboarding_gate_forced"] is False


class TestClassifyNode:
    @pytest.mark.asyncio
    async def test_skipped_when_gate_forced(self) -> None:
        # If gate already pinned intent, classify must NOT call the LLM.
        state = {
            "user_id": "u-1",
            "transcribed_text": "anything",
            "onboarding_gate_forced": True,
            "intent": "onboarding",
        }
        # Patch gateway.get_llm to fail loudly if called.
        boom = MagicMock(side_effect=AssertionError("LLM should not run"))
        with patch("src.agents.supervisor.nodes.gateway.get_llm", boom):
            out = await classify_node(state)
        assert out["intent"] == "onboarding"

    @pytest.mark.asyncio
    async def test_low_confidence_falls_through_to_off_topic(self) -> None:
        choice = IntentChoice(intent="food", confidence=0.1, reasoning="iffy")
        structured = MagicMock(ainvoke=AsyncMock(return_value=choice))
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        with patch(
            "src.agents.supervisor.nodes.gateway.get_llm", return_value=llm
        ):
            out = await classify_node(
                {"user_id": "u-1", "transcribed_text": "weird"}
            )
        assert out["intent"] == "off_topic"

    @pytest.mark.asyncio
    async def test_high_confidence_uses_llm_intent(self) -> None:
        choice = IntentChoice(intent="food", confidence=0.95, reasoning="clear")
        structured = MagicMock(ainvoke=AsyncMock(return_value=choice))
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        with patch(
            "src.agents.supervisor.nodes.gateway.get_llm", return_value=llm
        ):
            out = await classify_node(
                {"user_id": "u-1", "transcribed_text": "I want sushi"}
            )
        assert out["intent"] == "food"

    @pytest.mark.asyncio
    async def test_llm_failure_defaults_to_off_topic(self) -> None:
        llm = MagicMock()
        llm.with_structured_output.return_value = MagicMock(
            ainvoke=AsyncMock(side_effect=RuntimeError("api down"))
        )
        with patch(
            "src.agents.supervisor.nodes.gateway.get_llm", return_value=llm
        ):
            out = await classify_node(
                {"user_id": "u-1", "transcribed_text": "I want sushi"}
            )
        assert out["intent"] == "off_topic"


class TestRouteToSpecialist:
    def test_routes_known_intents(self) -> None:
        for intent in ("onboarding", "food", "profile"):
            assert route_to_specialist({"intent": intent}) == intent

    def test_unknown_routes_to_off_topic(self) -> None:
        assert route_to_specialist({"intent": "weather"}) == "off_topic_response"
        assert route_to_specialist({}) == "off_topic_response"


class TestRouteAfterSpecialist:
    def test_no_handoff_finishes(self) -> None:
        state = {"status": "ready", "system_response": "ok"}
        assert route_after_specialist(state) == "finish"

    def test_handoff_to_food_routes_there(self) -> None:
        state = {
            "status": "needs_handoff",
            "handoff_to": "food",
            "handoff_trail": [{"from": "travel", "to": "food", "reason": ""}],
        }
        assert route_after_specialist(state) == "food"
        # Routing should clear the handoff flag.
        assert state["status"] == "ready"
        assert state["handoff_to"] is None

    def test_handoff_loop_capped(self) -> None:
        # Simulate a long trail that exceeds MAX_HANDOFFS_PER_TURN.
        state = {
            "status": "needs_handoff",
            "handoff_to": "food",
            "handoff_trail": [{"from": str(i), "to": "x", "reason": ""} for i in range(10)],
        }
        assert route_after_specialist(state) == "finish"
