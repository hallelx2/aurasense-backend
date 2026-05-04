"""Smoke tests for the typed entity Pydantic models passed to Graphiti."""

from __future__ import annotations

import pytest

from src.app.services.graphiti.entity_types import (
    ENTITY_TYPES,
    RELEVANT_BY_INTENT,
    Allergy,
    CulturalContext,
    DietaryRestriction,
    FoodPreference,
    HealthCondition,
    RestaurantVisit,
)


class TestEntityClasses:
    def test_allergy_minimal_construction(self) -> None:
        a = Allergy(allergen="peanuts")
        assert a.allergen == "peanuts"
        assert a.severity == "moderate"  # default

    def test_allergy_full_construction(self) -> None:
        a = Allergy(allergen="shellfish", severity="severe", notes="anaphylaxis")
        assert a.severity == "severe"

    def test_dietary_restriction_kind_validated(self) -> None:
        DietaryRestriction(kind="halal")
        DietaryRestriction(kind="vegan", reason="ethical")
        with pytest.raises(Exception):
            DietaryRestriction(kind="not-a-real-diet")  # type: ignore[arg-type]

    def test_food_preference_defaults(self) -> None:
        f = FoodPreference(cuisine="thai")
        assert f.liking_strength == "like"
        assert f.source == "declared"

    def test_food_preference_extreme_dislike(self) -> None:
        f = FoodPreference(cuisine="cilantro", liking_strength="avoid")
        assert f.liking_strength == "avoid"

    def test_health_condition(self) -> None:
        h = HealthCondition(name="type 2 diabetes")
        assert h.dietary_implications is None

    def test_cultural_context(self) -> None:
        c = CulturalContext(origin="Nigerian", traditions="Sunday jollof")
        assert c.origin == "Nigerian"

    def test_restaurant_visit(self) -> None:
        v = RestaurantVisit(
            restaurant_name="Chez Pierre",
            sentiment="positive",
            would_return=True,
            notable_dish="duck confit",
        )
        assert v.would_return is True

    def test_models_are_jsonable(self) -> None:
        a = Allergy(allergen="peanuts", severity="severe")
        assert a.model_dump() == {
            "allergen": "peanuts",
            "severity": "severe",
            "notes": None,
        }


class TestRegistry:
    def test_entity_types_registry_complete(self) -> None:
        # Every model defined above should be in the registry, in case
        # someone added a model and forgot to register it.
        registered = set(ENTITY_TYPES.keys())
        expected = {
            "Allergy",
            "DietaryRestriction",
            "HealthCondition",
            "FoodPreference",
            "CulturalContext",
            "RestaurantVisit",
        }
        assert registered == expected

    def test_relevant_by_intent_uses_known_kinds(self) -> None:
        for intent, kinds in RELEVANT_BY_INTENT.items():
            for kind in kinds:
                assert kind in ENTITY_TYPES, (
                    f"Intent {intent!r} references unknown kind {kind!r}"
                )

    def test_food_intent_includes_safety_kinds(self) -> None:
        # Allergies / dietary restrictions / health conditions are the
        # safety-critical ones the food agent must always pull.
        food_kinds = set(RELEVANT_BY_INTENT["food"])
        assert "Allergy" in food_kinds
        assert "DietaryRestriction" in food_kinds
        assert "HealthCondition" in food_kinds
