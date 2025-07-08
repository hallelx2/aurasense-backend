"""
Onboarding API Routes
Handles user registration and profile setup
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import uuid
from src.agents.onboaring_agent.graph import run_onboarding_agent, continue_onboarding_conversation
from src.agents.onboaring_agent.state import OnboardingAgentState
from src.agents.onboaring_agent.tools import convert_text_to_speech
from src.app.models.user import User
from src.app.api.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingRequest(BaseModel):
    conversation_text: str
    user_id: Optional[str] = None

class OnboardingStartRequest(BaseModel):
    pass
    
class OnboardingInputRequest(BaseModel):
    transcript: str
    session_id: str
    
class OnboardingStopRequest(BaseModel):
    session_id: str


@router.post("/start")
async def start_onboarding(request: OnboardingStartRequest, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Start the onboarding process for a user
    """
    try:
        # Generate session ID for this onboarding session
        session_id = str(uuid.uuid4())
        
        # Get user information from Bearer token
        user_info = {
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "phone": current_user.phone,
            "age": current_user.age,
            "dietary_restrictions": current_user.dietary_restrictions or [],
            "cuisine_preferences": current_user.cuisine_preferences or [],
            "price_range": current_user.price_range,
            "is_tourist": current_user.is_tourist,
            "cultural_background": current_user.cultural_background or [],
            "food_allergies": current_user.food_allergies or [],
            "spice_tolerance": current_user.spice_tolerance,
            "preferred_languages": current_user.preferred_languages or ["en"]
        }
        
        # Initialize onboarding state
        initial_state = OnboardingAgentState(
            user_input="Hello, I'm ready to start onboarding!",
            extracted_information=user_info,
            onboarding_status="pending_info",
            messages=[]
        )
        
        # Start the onboarding process
        state = await run_onboarding_agent(initial_state["user_input"])
        
        # Convert response to speech if needed
        response_text = state.get("system_response", "Welcome! Let's get you set up with personalized recommendations.")
        
        try:
            audio_path = await convert_text_to_speech(response_text)
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            import base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        except Exception as e:
            logger.warning(f"TTS conversion failed: {e}")
            audio_base64 = None
        
        # Store session state in Neo4j
        await _store_session_state(current_user.uid, session_id, state)
        
        return {
            "session_id": session_id,
            "message": response_text,
            "audio_response": audio_base64,
            "onboarding_status": state.get("onboarding_status", "pending_info"),
            "progress": _calculate_progress(state.get("extracted_information", {})),
            "user_id": current_user.uid,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Onboarding start failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start onboarding: {str(e)}")


@router.post("/input")
async def process_onboarding_input(request: OnboardingInputRequest, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Process user input transcript and return voice agent response
    """
    try:
        # Get current state from Neo4j session storage
        current_state = await _get_session_state(current_user.uid, request.session_id)
        if not current_state:
            # Create new state if session not found
            current_state = OnboardingAgentState(
                user_input=request.transcript,
                extracted_information={
                    "email": current_user.email,
                    "first_name": current_user.first_name,
                    "last_name": current_user.last_name,
                },
                onboarding_status="pending_info",
                messages=[]
            )
        
        # Continue the onboarding conversation
        state = await continue_onboarding_conversation(current_state, request.transcript)
        
        # Get the response text
        response_text = state.get("system_response", "I understand. Let's continue with your personalization.")
        
        # Convert response to speech
        try:
            audio_path = await convert_text_to_speech(response_text)
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            import base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        except Exception as e:
            logger.warning(f"TTS conversion failed: {e}")
            audio_base64 = None
        
        # Update session state in Neo4j
        await _store_session_state(current_user.uid, request.session_id, state)
        
        # Save to user profile if onboarding is complete
        if state.get("onboarding_status") == "onboarded":
            await _save_onboarding_to_user(current_user, state.get("extracted_information", {}))
        
        return {
            "session_id": request.session_id,
            "message": response_text,
            "audio_response": audio_base64,
            "onboarding_status": state.get("onboarding_status", "pending_info"),
            "progress": _calculate_progress(state.get("extracted_information", {})),
            "extracted_info": state.get("extracted_information", {}),
            "user_id": current_user.uid,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Onboarding input processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process input: {str(e)}")


@router.post("/stop")
async def stop_onboarding(request: OnboardingStopRequest, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Stop onboarding process and redirect user to food selection
    """
    try:
        # Clean up session data from Neo4j
        await _cleanup_session_state(current_user.uid, request.session_id)
        
        return {
            "session_id": request.session_id,
            "message": "Great! Let's start exploring delicious food options for you.",
            "redirect_to": "/food-selection",
            "user_id": current_user.uid,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Onboarding stop failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop onboarding: {str(e)}")


async def _store_session_state(user_id: str, session_id: str, state: OnboardingAgentState) -> None:
    """
    Store onboarding session state in Neo4j
    """
    try:
        import json
        from neomodel import db
        
        # Create or update session node
        query = """
        MERGE (s:OnboardingSession {session_id: $session_id, user_id: $user_id})
        SET s.state = $state_json, s.updated_at = datetime()
        RETURN s
        """
        
        state_json = json.dumps({
            "extracted_information": state.get("extracted_information", {}),
            "onboarding_status": state.get("onboarding_status", "pending_info"),
            "system_response": state.get("system_response", ""),
            "error": state.get("error", "")
        })
        
        db.cypher_query(query, {
            "session_id": session_id,
            "user_id": user_id,
            "state_json": state_json
        })
        
    except Exception as e:
        logger.warning(f"Failed to store session state: {e}")


async def _get_session_state(user_id: str, session_id: str) -> Optional[OnboardingAgentState]:
    """
    Retrieve onboarding session state from Neo4j
    """
    try:
        import json
        from neomodel import db
        
        query = """
        MATCH (s:OnboardingSession {session_id: $session_id, user_id: $user_id})
        RETURN s.state as state_json
        """
        
        results, _ = db.cypher_query(query, {
            "session_id": session_id,
            "user_id": user_id
        })
        
        if results:
            state_data = json.loads(results[0][0])
            return OnboardingAgentState(
                user_input="",
                extracted_information=state_data.get("extracted_information", {}),
                onboarding_status=state_data.get("onboarding_status", "pending_info"),
                system_response=state_data.get("system_response", ""),
                error=state_data.get("error", ""),
                messages=[]
            )
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to get session state: {e}")
        return None


async def _cleanup_session_state(user_id: str, session_id: str) -> None:
    """
    Clean up onboarding session state from Neo4j
    """
    try:
        from neomodel import db
        
        query = """
        MATCH (s:OnboardingSession {session_id: $session_id, user_id: $user_id})
        DELETE s
        """
        
        db.cypher_query(query, {
            "session_id": session_id,
            "user_id": user_id
        })
        
    except Exception as e:
        logger.warning(f"Failed to cleanup session state: {e}")


async def _save_onboarding_to_user(user: User, extracted_info: Dict[str, Any]) -> None:
    """
    Save completed onboarding information to user profile
    """
    try:
        # Update user with extracted information
        user.phone = extracted_info.get("phone", user.phone)
        user.age = extracted_info.get("age", user.age)
        user.dietary_restrictions = extracted_info.get("dietary_restrictions", user.dietary_restrictions)
        user.cuisine_preferences = extracted_info.get("cuisine_preferences", user.cuisine_preferences)
        user.price_range = extracted_info.get("price_range", user.price_range)
        user.is_tourist = extracted_info.get("is_tourist", user.is_tourist)
        user.cultural_background = extracted_info.get("cultural_background", user.cultural_background)
        user.food_allergies = extracted_info.get("food_allergies", user.food_allergies)
        user.spice_tolerance = extracted_info.get("spice_tolerance", user.spice_tolerance)
        user.preferred_languages = extracted_info.get("preferred_languages", user.preferred_languages)
        user.is_onboarded = True
        
        # Save to database
        user.save()
        
    except Exception as e:
        logger.error(f"Failed to save onboarding to user: {e}")


def _calculate_progress(extracted_info: Dict[str, Any]) -> float:
    """
    Calculate onboarding progress based on extracted information
    """
    from src.agents.onboaring_agent.nodes import ONBOARDING_REQUIRED_FIELDS
    
    completed_fields = sum(1 for field in ONBOARDING_REQUIRED_FIELDS if extracted_info.get(field))
    total_fields = len(ONBOARDING_REQUIRED_FIELDS)
    
    return (completed_fields / total_fields) * 100.0 if total_fields > 0 else 0.0
