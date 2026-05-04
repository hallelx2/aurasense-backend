"""Unit tests for the Graphiti write contract.

We mock the underlying Graphiti SDK so these run without Neo4j or any
network. The goal is to lock in the *shape* of episode payloads
(group_id scoping, entity_types attached, JSON body for structured
writes) so future Graphiti SDK upgrades don't silently break the
contract.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.services.graphiti import contract


@pytest.fixture
def fake_graphiti(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `get_graphiti()` with a mock whose `add_episode` records calls."""
    fake = MagicMock()
    fake.add_episode = AsyncMock(return_value=MagicMock(name="AddEpisodeResults"))
    monkeypatch.setattr(contract, "get_graphiti", lambda: fake)
    return fake


class TestRecordUserUtterance:
    @pytest.mark.asyncio
    async def test_writes_message_episode(self, fake_graphiti: MagicMock) -> None:
        await contract.record_user_utterance(
            user_id="user-uid-1",
            transcript="I'm allergic to peanuts",
            agent_name="onboarding",
        )
        fake_graphiti.add_episode.assert_awaited_once()
        kwargs = fake_graphiti.add_episode.await_args.kwargs
        assert kwargs["group_id"] == "user-uid-1"
        assert kwargs["episode_body"] == "I'm allergic to peanuts"
        assert kwargs["name"] == "onboarding-utterance"
        # Default entity_types attached (the typed-extraction registry).
        assert "Allergy" in kwargs["entity_types"]

    @pytest.mark.asyncio
    async def test_empty_transcript_is_no_op(self, fake_graphiti: MagicMock) -> None:
        await contract.record_user_utterance(
            user_id="u", transcript="", agent_name="onboarding"
        )
        fake_graphiti.add_episode.assert_not_awaited()


class TestRecordExtractedFacts:
    @pytest.mark.asyncio
    async def test_writes_json_episode_with_facts(
        self, fake_graphiti: MagicMock
    ) -> None:
        await contract.record_extracted_facts(
            user_id="u-2",
            facts={"food_allergies": ["peanuts"], "age": 30},
            agent_name="onboarding",
        )
        fake_graphiti.add_episode.assert_awaited_once()
        kwargs = fake_graphiti.add_episode.await_args.kwargs
        assert kwargs["group_id"] == "u-2"
        body = json.loads(kwargs["episode_body"])
        assert body["extracted"] == {"food_allergies": ["peanuts"], "age": 30}

    @pytest.mark.asyncio
    async def test_empty_facts_is_no_op(self, fake_graphiti: MagicMock) -> None:
        await contract.record_extracted_facts(
            user_id="u", facts={}, agent_name="onboarding"
        )
        fake_graphiti.add_episode.assert_not_awaited()


class TestRecordRecommendation:
    @pytest.mark.asyncio
    async def test_writes_recommendation_with_acceptance(
        self, fake_graphiti: MagicMock
    ) -> None:
        await contract.record_recommendation(
            user_id="u-3",
            agent_name="food",
            recommendation={"restaurant": "Pad Thai Place", "dish": "drunken noodles"},
            accepted=True,
        )
        fake_graphiti.add_episode.assert_awaited_once()
        kwargs = fake_graphiti.add_episode.await_args.kwargs
        body = json.loads(kwargs["episode_body"])
        assert body["accepted"] is True
        assert body["recommendation"]["restaurant"] == "Pad Thai Place"
        assert kwargs["name"] == "food-recommendation"


class TestRecordVisit:
    @pytest.mark.asyncio
    async def test_writes_visit_episode(self, fake_graphiti: MagicMock) -> None:
        await contract.record_visit(
            user_id="u-4",
            restaurant="Chez Pierre",
            visit_data={"sentiment": "positive", "dish": "duck confit"},
        )
        fake_graphiti.add_episode.assert_awaited_once()
        kwargs = fake_graphiti.add_episode.await_args.kwargs
        body = json.loads(kwargs["episode_body"])
        assert body["restaurant"] == "Chez Pierre"
        assert body["data"]["sentiment"] == "positive"


class TestErrorSwallow:
    @pytest.mark.asyncio
    async def test_graphiti_error_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Memory write failures must NOT break the user-facing flow."""
        fake = MagicMock()
        fake.add_episode = AsyncMock(side_effect=RuntimeError("graphiti is down"))
        monkeypatch.setattr(contract, "get_graphiti", lambda: fake)

        result = await contract.record_user_utterance(
            user_id="u", transcript="hello", agent_name="onboarding"
        )
        assert result is None  # swallowed, not raised
