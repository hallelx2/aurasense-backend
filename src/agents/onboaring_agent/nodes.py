from .tools import transcribe_audio, extract_user_information, convert_text_to_speech, generate_dietary_question, validate_dietary_response
from .state import OnboardingAgentState

# Onboarding-specific required fields (sign-up fields are already collected)
ONBOARDING_REQUIRED_FIELDS = [
    "age",
    "dietary_restrictions",
    "cuisine_preferences",
    "price_range",
    "is_tourist",
    "cultural_background",
    "food_allergies",
    "spice_tolerance",
    "preferred_languages"
]


# Node Functions
async def transcription_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Transcribe audio input to text"""
    try:
        user_voice = state.get("user_input")
        if user_voice and isinstance(user_voice, bytes):
            transcribed = await transcribe_audio(user_voice)
            state["transcribed_text"] = (
                transcribed
                if isinstance(transcribed, str)
                else transcribed.get("text", "")
            )
        elif isinstance(user_voice, str):
            # If input is already text, use it directly
            state["transcribed_text"] = user_voice
        else:
            state["error"] = "No valid input provided"
            state["system_response"] = "I didn't receive any input. Please try again."
    except Exception as e:
        state["error"] = f"Transcription failed: {str(e)}"
        state["system_response"] = "I couldn't understand your audio. Please try again."

    return state


async def information_extraction_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Extract user information from transcribed text and synthesize next onboarding question"""
    try:
        text = state.get("transcribed_text")
        if text:
            extracted = extract_user_information(text)
            # Convert Pydantic model to dict if needed
            if hasattr(extracted, "dict"):
                extracted = extracted.dict()

            # Update extracted information
            current_info = state.get("extracted_information", {})
            current_info.update(extracted)
            state["extracted_information"] = current_info

            # Check for missing onboarding fields only
            missing_fields = [f for f in ONBOARDING_REQUIRED_FIELDS if not current_info.get(f)]

            if not missing_fields:
                state["onboarding_status"] = "ready"
                state["system_response"] = "Perfect! We have all the information we need to personalize your Aurasense experience."
            else:
                state["onboarding_status"] = "pending_info"
                # Use AI-powered question generation for better user experience
                next_field = missing_fields[0]
                try:
                    question = generate_dietary_question(next_field, current_info)
                    state["system_response"] = question
                except:
                    # Fallback to default questions if AI fails
                    onboarding_questions = {
                        "phone": "What's your phone number? This helps us send you important updates.",
                        "age": "How old are you? This helps us provide age-appropriate recommendations.",
                        "dietary_restrictions": "Do you have any dietary restrictions? For example, vegetarian, vegan, gluten-free, etc.",
                        "cuisine_preferences": "What are your favorite types of cuisine? Tell me about the foods you love!",
                        "price_range": "What's your preferred price range when dining out? Budget-friendly, mid-range, premium, or luxury?",
                        "is_tourist": "Are you visiting this area as a tourist, or do you live here?",
                        "cultural_background": "What's your cultural background? This helps us recommend authentic experiences.",
                        "food_allergies": "Do you have any food allergies I should know about?",
                        "spice_tolerance": "How much spice can you handle? Rate from 1 (mild) to 5 (very spicy).",
                        "preferred_languages": "What languages do you prefer to communicate in?"
                    }
                    question = onboarding_questions.get(next_field, f"Please tell me about your {next_field.replace('_', ' ')}.")
                    state["system_response"] = question
        else:
            state["error"] = "No text to extract information from"
            state["system_response"] = (
                "I couldn't process your input. Please try again."
            )
    except Exception as e:
        state["error"] = f"Information extraction failed: {str(e)}"
        state["system_response"] = (
            "I had trouble understanding your information. Please try again."
        )

    return state


async def onboarding_complete_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Complete onboarding and save user if all info is present"""
    try:
        info = state.get("extracted_information", {})
        # Only check onboarding fields, not sign-up fields
        if all(info.get(f) for f in ONBOARDING_REQUIRED_FIELDS):
            from .tools import save_user_to_graph_db
            save_result = await save_user_to_graph_db(info)
            if save_result.get("success"):
                state["onboarding_status"] = "onboarded"
                state["system_response"] = "Congratulations! Your personalization is complete. Welcome to your personalized Aurasense experience!"
            else:
                state["onboarding_status"] = "failed"
                state["system_response"] = f"Onboarding failed: {save_result.get('message', 'Unknown error')}"
        else:
            state["onboarding_status"] = "pending_info"
            state["system_response"] = "We still need a bit more information to personalize your experience."
    except Exception as e:
        state["error"] = f"Onboarding failed: {str(e)}"
        state["onboarding_status"] = "failed"
        state["system_response"] = "Onboarding error occurred. Please try again."

    return state


async def verification_initiation_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Initiate voice verification process"""
    try:
        # Generate verification sentence
        verification_sentences = [
            "The quick brown fox jumps over the lazy dog",
            "I love to eat pizza on sunny days",
            "Machine learning is transforming our world",
            "The ocean waves crash against the shore",
        ]

        import random

        sentence = random.choice(verification_sentences)
        state["verification_sentence"] = sentence
        state["system_response"] = (
            f"For security verification, please say exactly: '{sentence}'"
        )
        state["awaiting_user_action"] = "speak_verification"
    except Exception as e:
        state["error"] = f"Verification initiation failed: {str(e)}"
        state["system_response"] = "Verification setup failed. Please try again."

    return state


async def verification_check_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Check if verification attempt matches expected sentence"""
    try:
        attempt = state.get("verification_attempt", "").strip().lower()
        expected = state.get("verification_sentence", "").strip().lower()

        if attempt and expected and attempt == expected:
            state["onboarding_status"] = "authenticated"
            state["system_response"] = (
                "Voice verification successful! You are now authenticated."
            )
        else:
            state["onboarding_status"] = "failed"
            state["system_response"] = "Voice verification failed. Please try again."
    except Exception as e:
        state["error"] = f"Verification check failed: {str(e)}"
        state["onboarding_status"] = "failed"
        state["system_response"] = "Verification error occurred. Please try again."

    return state


async def generate_response_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """Generate appropriate response based on current state"""
    try:
        # If there's already a system response, keep it
        if not state.get("system_response"):
            onboarding_status = state.get("onboarding_status")
            if onboarding_status == "pending_info":
                state["system_response"] = (
                    "Please provide your authentication information."
                )
            elif onboarding_status == "pending_verification":
                state["system_response"] = "Please complete voice verification."
            elif onboarding_status == "failed":
                state["system_response"] = "Authentication failed. Please try again."
            else:
                state["system_response"] = "How can I help you today?"
    except Exception as e:
        state["error"] = f"Response generation failed: {str(e)}"
        state["system_response"] = (
            "I'm having trouble generating a response. Please try again."
        )

    return state


async def end_interaction_node(state: OnboardingAgentState) -> OnboardingAgentState:
    """End the authentication interaction"""
    state["system_response"] = "Authentication complete. Thank you!"
    state["awaiting_user_action"] = None
    return state


# Conditional functions for routing
def needs_more_info(state: OnboardingAgentState) -> bool:
    """Check if more information is needed"""
    return state.get("onboarding_status") == "pending_info"


def is_ready_for_onboarding(state: OnboardingAgentState) -> bool:
    """Check if ready for authentication"""
    return state.get("onboarding_status") == "ready"


def needs_verification(state: OnboardingAgentState) -> bool:
    """Check if verification is needed"""
    return state.get("onboarding_status") == "pending_verification"


def is_onboarded(state: OnboardingAgentState) -> bool:
    """Check if user is authenticated"""
    return state.get("onboarding_status") == "onboarded"


def is_failed(state: OnboardingAgentState) -> bool:
    """Check if authentication failed"""
    return state.get("onboarding_status") == "failed"


def awaiting_verification(state: OnboardingAgentState) -> bool:
    """Check if waiting for verification input"""
    return state.get("awaiting_user_action") == "speak_verification"


def has_error(state: OnboardingAgentState) -> bool:
    """Check if there's an error"""
    return bool(state.get("error"))
