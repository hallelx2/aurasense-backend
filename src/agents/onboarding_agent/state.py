from typing import Any, Dict, Literal, Optional

from src.agents.base.state import BaseAgentState


class OnboardingAgentState(BaseAgentState, total=False):
    """Onboarding-specific state — extends BaseAgentState.

    Audio bytes never live in this state: the WS handler transcribes the
    audio upstream and passes ``user_input: str`` (the transcript) into the
    agent. This keeps the state RedisSaver-serializable.
    """

    # Structured information extracted from the conversation so far.
    extracted_information: Dict[str, Any]

    # Current status of the onboarding process. Mirrors BaseAgentState.status
    # for back-compat with existing nodes; node functions read this one.
    onboarding_status: Literal[
        "pending_info", "ready", "pending_verification", "onboarded", "failed"
    ]

    # Voice-biometric verification (deferred to a later phase; kept for
    # node-function compatibility).
    verification_sentence: Optional[str]
    verification_attempt: Optional[str]

    # Indicates if the agent is waiting for a specific user action.
    awaiting_user_action: Optional[str]
