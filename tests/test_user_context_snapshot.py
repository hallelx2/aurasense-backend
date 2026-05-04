"""Unit tests for the UserContextSnapshot dataclass."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.profile_agent.snapshot import UserContextSnapshot


def _fake_user(**overrides) -> SimpleNamespace:
    """Stand-in for a neomodel User node — exposes attributes via getattr."""
    defaults = {
        "first_name": "Test",
        "last_name": "User",
        "username": "testuser",
        "email": "test@example.com",
        "phone": None,
        "age": 30,
        "price_range": "mid-range",
        "is_tourist": False,
        "is_onboarded": True,
        "preferred_languages": ["en"],
        "spice_tolerance": 3,
        "food_allergies": ["peanuts"],
        "dietary_restrictions": ["vegetarian"],
        "cuisine_preferences": ["thai", "italian"],
        "cultural_background": ["nigerian"],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestEmptyAndDictRoundTrip:
    def test_empty_constructor(self) -> None:
        s = UserContextSnapshot.empty(user_id="u-1", intent="food")
        assert s.user_id == "u-1"
        assert s.intent == "food"
        assert s.allergies == []
        assert s.is_onboarded is False

    def test_to_dict_is_json_serializable(self) -> None:
        import json

        s = UserContextSnapshot.empty(user_id="u-1", intent="food")
        json.dumps(s.to_dict())  # no exception = JSON-clean

    def test_to_dict_round_trip_preserves_lists(self) -> None:
        s = UserContextSnapshot(
            user_id="u",
            intent="food",
            allergies=["peanuts", "shellfish"],
            cuisines_liked=["thai"],
            is_onboarded=True,
        )
        d = s.to_dict()
        assert d["allergies"] == ["peanuts", "shellfish"]
        assert d["cuisines_liked"] == ["thai"]
        assert d["is_onboarded"] is True


class TestFromUserAndGraph:
    def test_layer1_only_pulls_from_user_node(self) -> None:
        user = _fake_user(food_allergies=["peanuts"])
        s = UserContextSnapshot.from_user_and_graph(
            user_id="u-1",
            intent="food",
            user=user,
            graph_context={},
        )
        assert "peanuts" in s.allergies
        assert s.profile["age"] == 30
        assert s.is_onboarded is True

    def test_layer2_fills_what_user_lacks(self) -> None:
        # User node has no health conditions column — must come from graph.
        user = _fake_user()
        graph = {
            "by_kind": {
                "HealthCondition": ["type 2 diabetes"],
                "FoodPreference": ["sushi"],
            }
        }
        s = UserContextSnapshot.from_user_and_graph(
            user_id="u-1", intent="food", user=user, graph_context=graph
        )
        assert s.health_conditions == ["type 2 diabetes"]
        # User node had thai+italian; graph adds sushi without dup.
        assert "sushi" in s.cuisines_liked
        assert "thai" in s.cuisines_liked
        assert "italian" in s.cuisines_liked

    def test_layers_dedupe_case_insensitive(self) -> None:
        user = _fake_user(food_allergies=["Peanuts"])
        graph = {"by_kind": {"Allergy": ["PEANUTS", "shellfish"]}}
        s = UserContextSnapshot.from_user_and_graph(
            user_id="u-1", intent="food", user=user, graph_context=graph
        )
        # First-seen wins for ordering AND case; "Peanuts" survives.
        assert s.allergies[0] == "Peanuts"
        assert "shellfish" in s.allergies
        # No duplicate of peanuts in any case.
        lowered = [a.lower() for a in s.allergies]
        assert lowered.count("peanuts") == 1

    def test_user_none_yields_empty_profile_layer(self) -> None:
        graph = {"by_kind": {"Allergy": ["peanuts"]}}
        s = UserContextSnapshot.from_user_and_graph(
            user_id="u-1", intent="food", user=None, graph_context=graph
        )
        assert s.profile == {}
        assert s.is_onboarded is False
        # Graph layer still flows through.
        assert s.allergies == ["peanuts"]


class TestPromptRender:
    def test_empty_snapshot_renders_neutral_line(self) -> None:
        s = UserContextSnapshot.empty(user_id="u", intent="food")
        assert "No prior personalization" in s.to_prompt()

    def test_prompt_includes_each_populated_section(self) -> None:
        user = _fake_user()
        s = UserContextSnapshot.from_user_and_graph(
            user_id="u",
            intent="food",
            user=user,
            graph_context={
                "by_kind": {"HealthCondition": ["IBS"]}
            },
        )
        prompt = s.to_prompt()
        assert "Allergies" in prompt and "peanuts" in prompt
        assert "Dietary restrictions" in prompt and "vegetarian" in prompt
        assert "Health conditions" in prompt and "IBS" in prompt
        assert "Cuisine preferences" in prompt and "thai" in prompt
        assert "Cultural background" in prompt and "nigerian" in prompt
