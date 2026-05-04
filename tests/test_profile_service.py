"""Unit tests for the profile service facade.

We mock the underlying ``profile_agent`` so these run without Neo4j /
Redis / Graphiti — what we want to lock in is that the service is a
thin pass-through and that the agent surface's contract is honored.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.profile_agent.snapshot import UserContextSnapshot
from src.app.services import profile_service as profile_service_mod
from src.app.services.profile_service import ProfileService


@pytest.fixture
def patched_agent(monkeypatch: pytest.MonkeyPatch):
    """Replace `profile_agent.get_user_context` with a recorded mock."""
    sentinel = UserContextSnapshot(
        user_id="u-1",
        intent="food",
        allergies=["peanuts"],
        is_onboarded=True,
    )
    mock = AsyncMock(return_value=sentinel)

    # The facade does a lazy import. We reach into the agent module
    # *after* the facade does to set the attribute.
    from src.agents.profile_agent import agent as agent_mod

    monkeypatch.setattr(agent_mod.profile_agent, "get_user_context", mock)
    return mock


class TestProfileService:
    @pytest.mark.asyncio
    async def test_returns_snapshot_from_agent(self, patched_agent) -> None:
        service = ProfileService()
        snap = await service.get_user_context("u-1", intent="food")
        assert isinstance(snap, UserContextSnapshot)
        assert snap.allergies == ["peanuts"]

    @pytest.mark.asyncio
    async def test_passes_intent_through(self, patched_agent) -> None:
        service = ProfileService()
        await service.get_user_context("u-1", intent="travel")
        patched_agent.assert_awaited_once_with("u-1", intent="travel")

    @pytest.mark.asyncio
    async def test_default_intent_is_profile(self, patched_agent) -> None:
        service = ProfileService()
        await service.get_user_context("u-1")
        patched_agent.assert_awaited_once_with("u-1", intent="profile")

    @pytest.mark.asyncio
    async def test_singleton_exported(self) -> None:
        # The singleton should be the canonical import for consumers.
        assert profile_service_mod.profile_service is not None
        assert isinstance(profile_service_mod.profile_service, ProfileService)
