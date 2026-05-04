"""Unit tests for the Graphiti read contract."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.services.graphiti import retriever
from src.app.services.graphiti.retriever import ContextBundle


def _fake_edge(fact: str, name: str = "RELATES_TO", attributes=None) -> MagicMock:
    """Build a stand-in for graphiti_core.edges.EntityEdge."""
    e = MagicMock()
    e.fact = fact
    e.name = name
    e.attributes = attributes or {}
    return e


class TestContextBundle:
    def test_empty_bundle_renders_neutral_prompt(self) -> None:
        b = ContextBundle.empty(user_id="u", intent="food")
        assert b.facts == []
        assert "No prior context" in b.to_prompt()

    def test_to_dict_round_trip_safe(self) -> None:
        b = ContextBundle(
            user_id="u",
            intent="food",
            facts=["allergic to peanuts"],
            by_kind={"Allergy": ["allergic to peanuts"]},
            raw_count=1,
        )
        # to_dict result must be JSON-shaped (dicts, lists, strings, ints).
        import json

        json.dumps(b.to_dict())  # would raise on non-serializable

    def test_kind_accessors(self) -> None:
        b = ContextBundle(
            user_id="u",
            intent="food",
            facts=["likes Thai", "allergic to peanuts"],
            by_kind={
                "FoodPreference": ["likes Thai"],
                "Allergy": ["allergic to peanuts"],
            },
        )
        assert b.allergies == ["allergic to peanuts"]
        assert b.cuisines == ["likes Thai"]
        assert b.health_conditions == []

    def test_from_edges_classifies_by_attribute(self) -> None:
        edges = [
            _fake_edge("user is allergic to peanuts", attributes={"entity_type": "Allergy"}),
            _fake_edge("user loves Thai food", attributes={"entity_type": "FoodPreference"}),
            _fake_edge("user is from Lagos", attributes={"entity_type": "CulturalContext"}),
        ]
        b = ContextBundle.from_edges(user_id="u", intent="food", edges=edges)
        assert "user is allergic to peanuts" in b.allergies
        assert "user loves Thai food" in b.cuisines
        assert "user is from Lagos" in b.cultural

    def test_from_edges_falls_back_to_other(self) -> None:
        edges = [_fake_edge("uncategorized fact", name="RELATES_TO")]
        b = ContextBundle.from_edges(user_id="u", intent="food", edges=edges)
        assert "uncategorized fact" in b.facts
        assert "uncategorized fact" in b.kind("Other")

    def test_to_prompt_lists_kinds_with_pretty_labels(self) -> None:
        edges = [
            _fake_edge("allergic to peanuts", attributes={"entity_type": "Allergy"}),
            _fake_edge("loves Thai", attributes={"entity_type": "FoodPreference"}),
        ]
        b = ContextBundle.from_edges(user_id="u", intent="food", edges=edges)
        prompt = b.to_prompt()
        assert "Allergies" in prompt
        assert "Food preferences" in prompt


class TestGetRelevantContext:
    @pytest.mark.asyncio
    async def test_passes_user_id_as_group_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = MagicMock()
        fake.search = AsyncMock(return_value=[])
        monkeypatch.setattr(retriever, "get_graphiti", lambda: fake)

        await retriever.get_relevant_context(
            user_id="user-abc", query="hello", intent="food"
        )
        fake.search.assert_awaited_once()
        kwargs = fake.search.await_args.kwargs
        assert kwargs["group_ids"] == ["user-abc"]

    @pytest.mark.asyncio
    async def test_empty_user_id_returns_empty_bundle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = MagicMock()
        fake.search = AsyncMock(return_value=[])
        monkeypatch.setattr(retriever, "get_graphiti", lambda: fake)

        bundle = await retriever.get_relevant_context(
            user_id="", query="hi", intent="food"
        )
        assert bundle.facts == []
        fake.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_graphiti_error_returns_empty_bundle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Search failures must not propagate — agents always get a bundle back."""
        fake = MagicMock()
        fake.search = AsyncMock(side_effect=RuntimeError("graphiti is down"))
        monkeypatch.setattr(retriever, "get_graphiti", lambda: fake)

        bundle = await retriever.get_relevant_context(
            user_id="u", query="anything", intent="food"
        )
        assert isinstance(bundle, ContextBundle)
        assert bundle.facts == []

    @pytest.mark.asyncio
    async def test_intent_filtering_drops_unrelated_kinds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        edges = [
            _fake_edge("allergic to peanuts", attributes={"entity_type": "Allergy"}),
            _fake_edge("visited Chez Pierre", attributes={"entity_type": "RestaurantVisit"}),
        ]
        fake = MagicMock()
        fake.search = AsyncMock(return_value=edges)
        monkeypatch.setattr(retriever, "get_graphiti", lambda: fake)

        # Onboarding doesn't include RestaurantVisit in its relevant kinds.
        bundle = await retriever.get_relevant_context(
            user_id="u", query="hi", intent="onboarding"
        )
        assert "Allergy" in bundle.by_kind
        assert "RestaurantVisit" not in bundle.by_kind
        # Raw facts list still has both for callers that want them.
        assert len(bundle.facts) == 2
