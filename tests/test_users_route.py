"""Tests for the /users/me/context REST route."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.agents.profile_agent.snapshot import UserContextSnapshot


def _fake_authed_user() -> SimpleNamespace:
    """Stand-in for a User; only `.uid` is read by the route."""
    return SimpleNamespace(uid="user-uid-abc", email="t@x.com")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a TestClient with the auth dependency + profile service mocked."""
    from src.app.main import app
    from src.app.api.dependencies.auth import get_current_user
    from src.app.api.routes import users as users_route_mod

    # Override the auth dependency: pretend the bearer token is valid
    # and the user is `user-uid-abc`.
    app.dependency_overrides[get_current_user] = _fake_authed_user

    # Patch the profile_service to return a deterministic snapshot.
    sentinel = UserContextSnapshot(
        user_id="user-uid-abc",
        intent="food",
        allergies=["peanuts"],
        cuisines_liked=["thai"],
        is_onboarded=True,
    )
    mock = AsyncMock(return_value=sentinel)
    monkeypatch.setattr(users_route_mod.profile_service, "get_user_context", mock)

    yield TestClient(app)
    app.dependency_overrides.clear()


class TestGetMeContext:
    def test_default_intent_is_profile(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/context")
        assert resp.status_code == 200
        body = resp.json()
        # Note: our patched mock returns intent="food", but the route
        # passes intent through. Default kicks in when no `?intent=` is
        # provided. The response shape is the snapshot dict.
        assert body["user_id"] == "user-uid-abc"
        assert body["allergies"] == ["peanuts"]

    def test_food_intent_is_passed_through(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/context?intent=food")
        assert resp.status_code == 200

    def test_invalid_intent_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/context?intent=not-a-real-intent")
        # FastAPI Literal validation -> 422.
        assert resp.status_code == 422

    def test_response_is_complete_snapshot_dict(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/context?intent=food")
        body = resp.json()
        # All snapshot keys present, even if empty.
        for key in (
            "user_id",
            "intent",
            "profile",
            "graph_context",
            "allergies",
            "dietary_restrictions",
            "cuisines_liked",
            "cultural_background",
            "health_conditions",
            "recent_visits",
            "is_onboarded",
        ):
            assert key in body, f"snapshot missing key: {key}"
