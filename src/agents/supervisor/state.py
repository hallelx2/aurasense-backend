"""SupervisorState — extends BaseAgentState with intent routing fields."""

from __future__ import annotations

from typing import Literal, Optional

from src.agents.base.state import BaseAgentState


# Recognized supervisor intents → routes to a specialist sub-graph.
SupervisorIntent = Literal[
    "onboarding",
    "food",
    "profile",
    "off_topic",
]


class SupervisorState(BaseAgentState, total=False):
    """State carried through the supervisor's routing graph."""

    # Classified intent for the current turn.
    intent: Optional[SupervisorIntent]

    # If ``True``, the supervisor's onboarding gate forced routing to
    # the onboarding agent regardless of what the classifier said
    # (because ``user.is_onboarded`` was False).
    onboarding_gate_forced: bool
