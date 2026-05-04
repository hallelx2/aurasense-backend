from typing import TypedDict, Optional, Dict, Any, Literal, Union
from langchain_core.messages import BaseMessage


class OnboardingAgentState(TypedDict, total=False):
    # Raw user input (audio bytes or text)
    user_input: Union[bytes, str]
    # Transcribed text from audio (if input was audio)
    transcribed_text: Optional[str]
    # Structured information extracted from the conversation
    extracted_information: Dict[str, Any]
    # Current status of the onboarding process
    onboarding_status: Literal[
        "pending_info", "ready", "pending_verification", "onboarded", "failed"
    ]
    # The unique verification sentence the user must speak
    verification_sentence: Optional[str]
    # The user's spoken verification attempt (for comparison)
    verification_attempt: Optional[str]
    # System response to be sent to the user
    system_response: Optional[str]
    # Indicates if the agent is waiting for a specific user action
    awaiting_user_action: Optional[str]
    # Conversation history for context
    messages: list[BaseMessage]
    # Error information if any
    error: Optional[str]
