"""
Typed entities Graphiti will extract from user utterances.

Each Pydantic class becomes a node type in the temporal knowledge graph:
when an episode is added with ``entity_types={"Allergy": Allergy, ...}``,
the LLM is prompted to recognize and emit instances of these types,
which Graphiti persists with full edge / time semantics.

Adding a new entity:
1. Define a Pydantic class here with descriptive field names + ``Field(description=...)``
   (Graphiti uses the descriptions in the extraction prompt — write them well).
2. Add the class to ``ENTITY_TYPES`` below.
3. Optional: add it to ``RELEVANT_BY_INTENT`` in ``retriever.py`` so the
   right intent-aware reads pull it back.

Keep these classes intent-shape-stable: renaming a field forces the
extraction LLM to relearn it, and changes how older episodes are
queried.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Health & dietary
# --------------------------------------------------------------------------


class Allergy(BaseModel):
    """A food the user is allergic or intolerant to."""

    allergen: str = Field(
        description="The specific food, ingredient, or substance the user reacts "
        "to (e.g. 'peanuts', 'shellfish', 'gluten', 'lactose'). Lowercase, "
        "singular noun where possible."
    )
    severity: Literal["mild", "moderate", "severe"] = Field(
        default="moderate",
        description="How serious the reaction is. 'severe' = anaphylaxis or "
        "ER-level; 'moderate' = uncomfortable but not life-threatening; "
        "'mild' = minor irritation. If the user only says 'I'm allergic to X' "
        "without specifying severity, default to 'moderate'.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Any free-text qualifier the user mentioned: e.g. "
        "'only raw, cooked is fine', 'cross-contamination matters'.",
    )


class DietaryRestriction(BaseModel):
    """A diet the user follows by choice or need (not an allergy)."""

    kind: Literal[
        "vegetarian",
        "vegan",
        "halal",
        "kosher",
        "pescatarian",
        "keto",
        "paleo",
        "low-carb",
        "low-sodium",
        "gluten-free",
        "dairy-free",
        "other",
    ] = Field(description="The type of dietary restriction.")
    reason: Optional[str] = Field(
        default=None,
        description="Why the user follows this diet — religious, medical, "
        "ethical, lifestyle. Only set if the user actually said.",
    )


class HealthCondition(BaseModel):
    """A chronic medical condition that affects food/lifestyle decisions."""

    name: str = Field(
        description="The condition name as the user described it (e.g. "
        "'type 2 diabetes', 'high blood pressure', 'IBS', 'GERD'). "
        "Don't medicalize beyond what the user said."
    )
    dietary_implications: Optional[str] = Field(
        default=None,
        description="What the condition means for food choices (e.g. "
        "'must monitor carbs', 'low-sodium only'). Free text.",
    )


# --------------------------------------------------------------------------
# Preferences & culture
# --------------------------------------------------------------------------


class FoodPreference(BaseModel):
    """A cuisine, dish, or flavor profile the user prefers."""

    cuisine: str = Field(
        description="The cuisine, dish category, or flavor profile (e.g. "
        "'Thai', 'sushi', 'spicy', 'Mediterranean'). Lowercase preferred."
    )
    liking_strength: Literal["love", "like", "neutral", "dislike", "avoid"] = Field(
        default="like",
        description="How strongly the user feels. 'love' / 'avoid' are the "
        "extremes; 'neutral' means they mentioned it without enthusiasm.",
    )
    source: Literal["declared", "observed"] = Field(
        default="declared",
        description="'declared' = user said it explicitly; 'observed' = "
        "inferred from past order/visit episodes. Default 'declared'.",
    )


class CulturalContext(BaseModel):
    """The user's cultural / regional background."""

    origin: str = Field(
        description="The user's cultural or regional origin (e.g. 'Nigerian', "
        "'Italian-American', 'Punjabi'). Use the user's own framing."
    )
    traditions: Optional[str] = Field(
        default=None,
        description="Specific food traditions or rituals the user mentioned "
        "(e.g. 'Sunday family pasta', 'Iftar during Ramadan').",
    )


# --------------------------------------------------------------------------
# Behavioural / temporal
# --------------------------------------------------------------------------


class RestaurantVisit(BaseModel):
    """A specific visit or order the user mentioned."""

    restaurant_name: str = Field(
        description="The restaurant name as mentioned. Capitalize as the user did."
    )
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        default="neutral",
        description="How the user felt about the visit overall.",
    )
    would_return: Optional[bool] = Field(
        default=None,
        description="Whether the user said they'd go back. Leave None if "
        "they didn't say either way.",
    )
    notable_dish: Optional[str] = Field(
        default=None,
        description="Any specific dish the user called out (e.g. 'the pad thai').",
    )


# --------------------------------------------------------------------------
# Registry — passed to graphiti.add_episode(entity_types=...)
# --------------------------------------------------------------------------


ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Allergy": Allergy,
    "DietaryRestriction": DietaryRestriction,
    "HealthCondition": HealthCondition,
    "FoodPreference": FoodPreference,
    "CulturalContext": CulturalContext,
    "RestaurantVisit": RestaurantVisit,
}


# Convenience tuples for callers that want a subset filtered by intent.
# Adding more intents (e.g. "travel") expands what each agent's
# context_node retrieves before responding.
RELEVANT_BY_INTENT: dict[str, tuple[str, ...]] = {
    "onboarding": (
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "FoodPreference",
        "CulturalContext",
    ),
    "food": (
        "Allergy",
        "DietaryRestriction",
        "HealthCondition",
        "FoodPreference",
        "CulturalContext",
        "RestaurantVisit",
    ),
    "profile": tuple(ENTITY_TYPES.keys()),
}
