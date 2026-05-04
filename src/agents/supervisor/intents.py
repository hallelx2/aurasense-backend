"""
Supervisor intent classification.

Single LLM call per turn (via the gateway) returns a structured choice
of which specialist agent should handle the message. The supervisor's
``classify_node`` writes the result onto state, then a conditional edge
routes to the matching sub-graph.

Onboarding gate is enforced *before* classification: if the user
hasn't completed onboarding, every message routes to the onboarding
agent regardless of what was said.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .state import SupervisorIntent


class IntentChoice(BaseModel):
    """LLM-classified routing decision."""

    intent: Literal[
        "onboarding",
        "food",
        "profile",
        "off_topic",
    ] = Field(
        description=(
            "Which specialist agent should handle this turn. "
            "'onboarding' = the user is still being set up (rarely picked "
            "directly — the onboarding gate handles that case). "
            "'food' = anything about meals, restaurants, ordering, recipes, "
            "dietary stuff. "
            "'profile' = the user is updating their preferences ('I'm "
            "actually allergic to shellfish too', 'change my budget'). "
            "'off_topic' = none of the above (greetings, weather, jokes); "
            "the supervisor will return a polite redirect."
        )
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Self-assessed confidence in the chosen intent on [0, 1]. "
            "Below 0.5 the supervisor will hand back a clarifying question."
        ),
    )
    reasoning: str = Field(
        default="",
        description="One short sentence explaining the choice. Logs only.",
    )


# System prompt used for the classification call. Kept terse so the
# LLM sees the user message clearly.
INTENT_SYSTEM_PROMPT = """
You route a single user utterance to one of the specialist agents
listed below. Pick the closest match.

- onboarding: setting up the user's profile (allergies, preferences,
  age, etc.). Mostly handled automatically by the onboarding gate.
- food: anything food / restaurant / dietary / cuisine / ordering.
- profile: the user wants to update what we know about them ("I'm
  vegetarian now", "change my budget to premium").
- off_topic: small talk, weather, jokes, anything else.

Return your choice with the confidence and a one-sentence reason.
""".strip()


def build_intent_prompt(user_text: str) -> str:
    return f"{INTENT_SYSTEM_PROMPT}\n\nUser said: {user_text!r}"


# Confidence threshold below which the supervisor falls through to a
# clarification response instead of routing to a specialist.
MIN_CONFIDENCE = 0.5
