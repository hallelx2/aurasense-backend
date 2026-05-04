"""
Pydantic schemas for the food agent.

These are the structured output shapes the recommend_node uses with
``llm.with_structured_output(...)``. Keeping them here (separate from
state) so other modules — tests, the food REST routes, and the future
supervisor — can import them without dragging in the whole agent.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FoodRecommendation(BaseModel):
    """A single dish or restaurant recommendation produced by the LLM."""

    name: str = Field(
        description="The dish or restaurant name. Use the user-visible "
        "title — what would appear on a menu or storefront."
    )
    description: str = Field(
        description="One or two sentence description of the dish, "
        "including key ingredients. Used by the deterministic allergy "
        "filter, so be explicit about ingredients."
    )
    cuisine: Optional[str] = Field(
        default=None,
        description="The cuisine label ('thai', 'italian', 'nigerian', ...).",
    )
    price_range: Optional[Literal["budget", "mid-range", "premium", "luxury"]] = Field(
        default=None,
        description="Approximate price tier, matching User.price_range.",
    )
    estimated_price: Optional[float] = Field(
        default=None,
        description="Approximate price in the local currency, if known.",
    )
    ingredients: List[str] = Field(
        default_factory=list,
        description="Top-level ingredients. The allergy filter checks "
        "this list against user allergens, so be explicit and inclusive.",
    )
    why_recommended: Optional[str] = Field(
        default=None,
        description="One short sentence explaining why this fits the "
        "user given their context (allergies / preferences / cuisine "
        "history). Surfaced to the user.",
    )


class RecommendationList(BaseModel):
    """Structured-output container the recommend node produces."""

    recommendations: List[FoodRecommendation] = Field(
        description="Ranked list of food recommendations, best first. "
        "Always exclude items the user is allergic to. Aim for 3-5 entries.",
        max_length=10,
    )
    summary: Optional[str] = Field(
        default=None,
        description="A 1-2 sentence summary the agent will speak/write "
        "above the list. Acknowledges the user's request and any "
        "personalization applied (e.g. 'I noticed you're allergic to "
        "peanuts so I excluded the pad thai').",
    )


class IntentClassification(BaseModel):
    """Result of the food intent_node — what kind of food turn is this?"""

    intent: Literal[
        "recommend",
        "reorder",
        "followup",
        "confirm_order",
        "decline",
        "off_topic",
    ] = Field(
        description="The user's intent. 'recommend' = new search; 'reorder' = "
        "repeat a previous order; 'followup' = clarify or ask for more "
        "options; 'confirm_order' = the user wants to place an order on a "
        "previously-shown recommendation; 'decline' = user wants to stop; "
        "'off_topic' = not food-related (route back to supervisor)."
    )
    selected_index: Optional[int] = Field(
        default=None,
        description="When intent='confirm_order', the 1-based index of "
        "the recommendation the user is referring to (e.g. 'order the "
        "second one' -> 2). None otherwise.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional free-text the LLM wants to flag — usage "
        "downstream is informational only.",
    )
