"""Unit tests for the deterministic allergy post-filter.

The LLM is not the safety boundary — this filter is. Test it like
your life depends on it (because someone else's might).
"""

from __future__ import annotations

import pytest

from src.agents.food_agent.allergy_filter import (
    ALLERGEN_SYNONYMS,
    filter_recommendations,
    is_safe,
    matched_allergens,
)


class TestIsSafe:
    def test_no_allergens_means_safe(self) -> None:
        assert is_safe("anything goes here", []) is True

    def test_empty_text_means_safe(self) -> None:
        assert is_safe("", ["peanut"]) is True

    def test_exact_word_match(self) -> None:
        assert is_safe("pad thai with peanuts", ["peanut"]) is False
        assert is_safe("pad thai with peanuts", ["peanuts"]) is False

    def test_synonym_match_groundnut(self) -> None:
        # "groundnut" is a peanut synonym; user typed canonical "peanut".
        assert is_safe("nigerian dish with groundnut sauce", ["peanut"]) is False

    def test_synonym_match_shellfish(self) -> None:
        assert is_safe("paella with shrimp and clams", ["shellfish"]) is False

    def test_word_boundary_avoids_false_match(self) -> None:
        # "almondian" should NOT match "almond" (word-boundary protects).
        assert is_safe("almondian temple ruins", ["almond"]) is True

    def test_user_specified_substring_still_works(self) -> None:
        # Even an unusual user allergen lookup falls back to literal match.
        assert is_safe("vegan jellyfish stew", ["jellyfish"]) is False

    def test_case_insensitive(self) -> None:
        assert is_safe("WITH PEANUTS!", ["peanut"]) is False
        assert is_safe("with peanuts", ["PEANUT"]) is False

    def test_dairy_synonyms(self) -> None:
        assert is_safe("creamy cheese sauce", ["milk"]) is False
        assert is_safe("creamy CHEESE sauce", ["dairy"]) is False

    def test_egg_in_mayo(self) -> None:
        # mayo contains egg; people sometimes forget.
        assert is_safe("turkey sandwich with mayo", ["egg"]) is False


class TestMatchedAllergens:
    def test_returns_only_triggering_allergens(self) -> None:
        text = "shrimp pad thai with peanuts and lime"
        hits = matched_allergens(text, ["peanut", "shellfish", "milk"])
        assert "peanut" in hits
        assert "shellfish" in hits
        assert "milk" not in hits


class TestFilterRecommendations:
    def test_empty_allergen_list_passes_everything(self) -> None:
        recs = [
            {"name": "Pad Thai", "ingredients": ["peanuts", "shrimp"]},
            {"name": "Margherita", "ingredients": ["wheat", "cheese"]},
        ]
        safe, rejected = filter_recommendations(recs, [])
        assert len(safe) == 2
        assert rejected == []

    def test_filters_by_ingredient_list(self) -> None:
        recs = [
            {"name": "Pad Thai", "description": "noodles with sauce", "ingredients": ["peanuts", "shrimp"]},
            {"name": "Pad See Ew", "description": "noodles with broccoli", "ingredients": ["broccoli", "soy sauce"]},
        ]
        safe, rejected = filter_recommendations(recs, ["peanut"])
        assert len(safe) == 1
        assert safe[0]["name"] == "Pad See Ew"
        assert len(rejected) == 1
        assert "peanut" in rejected[0]["rejection_reason"]

    def test_filters_by_description_when_ingredients_absent(self) -> None:
        recs = [
            {"name": "Mystery Dish", "description": "A creamy peanut-based curry."},
        ]
        safe, rejected = filter_recommendations(recs, ["peanut"])
        assert safe == []
        assert len(rejected) == 1

    def test_multiple_allergens_combine(self) -> None:
        recs = [
            {"name": "Phad Thai", "ingredients": ["shrimp", "peanut", "lime"]},
        ]
        safe, rejected = filter_recommendations(recs, ["peanut", "shellfish"])
        assert safe == []
        # Both allergens should appear in the rejection reason.
        reason = rejected[0]["rejection_reason"]
        assert "peanut" in reason
        assert "shellfish" in reason

    def test_empty_recs_returns_empty_lists(self) -> None:
        safe, rejected = filter_recommendations([], ["peanut"])
        assert safe == []
        assert rejected == []

    def test_non_string_allergen_skipped_safely(self) -> None:
        # Defensive — None/int/etc. shouldn't crash the filter.
        recs = [{"name": "rice bowl", "ingredients": ["rice"]}]
        safe, rejected = filter_recommendations(recs, [None, 0, "", "wheat"])  # type: ignore[list-item]
        assert len(safe) == 1
        assert rejected == []


class TestSynonymCoverage:
    def test_reverse_lookup_finds_each_canonical(self) -> None:
        """Every canonical allergen key must trigger via the reverse map."""
        from src.agents.food_agent.allergy_filter import _REVERSE_SYNONYMS

        for canonical in ALLERGEN_SYNONYMS:
            assert canonical.lower() in _REVERSE_SYNONYMS, (
                f"canonical {canonical!r} missing from reverse synonym map"
            )

    def test_synonym_lookup_resolves_to_full_equivalence(self) -> None:
        """A user typing any synonym should find all the others."""
        # User typed "dairy" — should find "cheese" via equivalence.
        assert is_safe("creamy cheese", ["dairy"]) is False
        # User typed "groundnut" — should find "peanut" via equivalence.
        assert is_safe("peanut sauce", ["groundnut"]) is False
