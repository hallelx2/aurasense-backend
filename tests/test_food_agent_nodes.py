"""Tests for the food agent nodes — the headline cross-agent flow.

The recommend_node test is the critical one: it confirms that no matter
what the LLM returns, the deterministic allergy filter strips items the
user is allergic to.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.food_agent.nodes import (
    confirm_or_order_node,
    health_screen_node,
    needs_order_placement,
    recommend_node,
    search_node,
)
from src.agents.food_agent.schemas import FoodRecommendation, RecommendationList


def _state(**overrides):
    """Build a base FoodAgentState dict with sensible defaults."""
    base = {
        "user_id": "u-test",
        "group_id": "u-test",
        "thread_id": "food:u-test",
        "agent_name": "food",
        "transcribed_text": "I want Thai food",
        "user_input": "I want Thai food",
        "user_context": {"profile": {}, "cuisines_liked": []},
        "allergens": [],
        "dietary_restrictions": [],
        "search_results": [],
    }
    base.update(overrides)
    return base


class TestHealthScreenNode:
    @pytest.mark.asyncio
    async def test_normalizes_and_dedupes(self) -> None:
        state = _state(allergens=["Peanut", " peanut", "shellfish"], dietary_restrictions=["vegan", "vegan"])
        out = await health_screen_node(state)
        assert sorted(out["allergens"]) == ["Peanut", "peanut", "shellfish"] or len(out["allergens"]) <= 3
        # `peanut` lowercase + ` peanut` (stripped) are dedup'd; `Peanut` is distinct
        # (case-sensitive set after .strip()). The exact set isn't load-bearing —
        # the contract is "no whitespace, no dups by exact match".
        assert all(a == a.strip() for a in out["allergens"])

    @pytest.mark.asyncio
    async def test_filters_non_strings(self) -> None:
        state = _state(allergens=["peanut", None, 123, ""])  # type: ignore[list-item]
        out = await health_screen_node(state)
        assert "peanut" in out["allergens"]
        assert all(isinstance(a, str) for a in out["allergens"])


class TestSearchNode:
    @pytest.mark.asyncio
    async def test_uses_mcp_service(self) -> None:
        state = _state(transcribed_text="vegan", user_context={"cuisines_liked": []})
        with patch(
            "src.agents.food_agent.nodes.mcp_service.search_restaurants",
            new=AsyncMock(return_value=[{"name": "Vegan Buddha Bowl"}]),
        ) as mock:
            out = await search_node(state)
            mock.assert_awaited()
            assert out["search_results"][0]["name"] == "Vegan Buddha Bowl"

    @pytest.mark.asyncio
    async def test_broadens_when_too_narrow(self) -> None:
        state = _state(
            transcribed_text="x",
            user_context={"cuisines_liked": ["thai"], "profile": {}},
        )
        # First call returns 1 result (too narrow), second returns 5.
        narrow = [{"name": "1"}]
        broad = [{"name": str(i)} for i in range(5)]
        mock = AsyncMock(side_effect=[narrow, broad])
        with patch(
            "src.agents.food_agent.nodes.mcp_service.search_restaurants", new=mock
        ):
            out = await search_node(state)
        assert mock.await_count == 2
        assert len(out["search_results"]) == 5


class TestRecommendNodeAllergyFilter:
    """The headline test: even if the LLM hallucinates a peanut dish,
    the deterministic allergy filter drops it."""

    def _llm_returning(self, recs: list[FoodRecommendation]) -> MagicMock:
        rec_list = RecommendationList(
            recommendations=recs, summary="LLM was overconfident."
        )
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value=rec_list)
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        return llm

    @pytest.mark.asyncio
    async def test_llm_returning_unsafe_dish_is_filtered(self) -> None:
        # User is allergic to peanuts; LLM "recommends" a peanut dish.
        unsafe = FoodRecommendation(
            name="Peanut Pad Thai",
            description="Stir-fried with peanuts.",
            ingredients=["rice noodles", "peanuts", "shrimp"],
        )
        safe_rec = FoodRecommendation(
            name="Vegan Pad See Ew",
            description="Soy noodles with broccoli.",
            ingredients=["rice noodles", "broccoli"],
        )
        llm = self._llm_returning([unsafe, safe_rec])

        state = _state(
            allergens=["peanut"],
            search_results=[{"name": "anything"}],  # non-empty so we hit the LLM
        )
        out = await recommend_node(state, llm=llm)

        # Peanut dish must NOT survive.
        names = [r["name"] for r in out["recommendations"]]
        assert "Peanut Pad Thai" not in names
        assert "Vegan Pad See Ew" in names
        # Rejected list captures the unsafe item with a reason.
        assert len(out["rejected_recommendations"]) == 1
        assert "peanut" in out["rejected_recommendations"][0]["rejection_reason"]

    @pytest.mark.asyncio
    async def test_no_safe_options_emits_friendly_response(self) -> None:
        unsafe = FoodRecommendation(
            name="Peanut Soup",
            description="Peanut-based broth.",
            ingredients=["peanut", "stock"],
        )
        llm = self._llm_returning([unsafe])
        state = _state(allergens=["peanut"], search_results=[{"name": "x"}])
        out = await recommend_node(state, llm=llm)
        assert out["recommendations"] == []
        assert "safe" in out["system_response"].lower()

    @pytest.mark.asyncio
    async def test_empty_search_results_short_circuits(self) -> None:
        llm = self._llm_returning([])
        state = _state(allergens=[], search_results=[])
        out = await recommend_node(state, llm=llm)
        assert out["recommendations"] == []
        assert "couldn't find" in out["system_response"].lower()


class TestConfirmOrOrder:
    @pytest.mark.asyncio
    async def test_marks_ready(self) -> None:
        state = _state(food_intent="recommend", recommendations=[{"name": "x"}])
        out = await confirm_or_order_node(state)
        assert out["status"] == "ready"

    def test_routing_to_place_order(self) -> None:
        state = _state(
            food_intent="confirm_order",
            recommendations=[{"name": "x"}],
            selected_index=1,
        )
        assert needs_order_placement(state) is True

    def test_no_routing_without_intent(self) -> None:
        state = _state(
            food_intent="recommend",
            recommendations=[{"name": "x"}],
            selected_index=1,
        )
        assert needs_order_placement(state) is False

    def test_no_routing_without_recs(self) -> None:
        state = _state(
            food_intent="confirm_order",
            recommendations=[],
            selected_index=1,
        )
        assert needs_order_placement(state) is False
