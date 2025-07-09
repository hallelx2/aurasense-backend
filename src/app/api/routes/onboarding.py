"""
Onboarding API Routes
Single endpoint for dynamic user onboarding with transcript processing
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel
import logging
from src.agents.onboaring_agent.tools import (
    get_user_onboarding_state, 
    extract_user_information
)
from src.agents.onboaring_agent.llm import llm_qwen
from src.app.models.user import User
from src.app.api.dependencies.auth import get_current_user
from src.app.services.memory_service import MemoryService
from src.app.api.routes.auth import security_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
memory_service = MemoryService()


class OnboardingRequest(BaseModel):
    query: str  # The transcript from the user


class OnboardingResponse(BaseModel):
    final_answer: str


@router.post("")
async def onboarding_endpoint(
    request: OnboardingRequest, 
    current_user: User = Depends(get_current_user)
) -> OnboardingResponse:
    """
    Single onboarding endpoint that processes transcript queries and uses Qwen reasoning
    to dynamically ask for missing information and extract data for the graph.
    """
    try:
        # Get current user's onboarding state from database
        db_state = await get_user_onboarding_state(current_user.email)
        
        if not db_state.get("success"):
            raise HTTPException(status_code=500, detail="Failed to retrieve user state")
        
        current_state = db_state.get("current_state", {})
        missing_fields = db_state.get("missing_fields", [])
        
        # Use Qwen with reasoning to process the query
        reasoning_prompt = f"""
        <think>
        You are an intelligent onboarding assistant helping users complete their food preference profile.
        
        Current user information:
        {current_state}
        
        Missing fields that need to be collected:
        {missing_fields}
        
        User's query/transcript: "{request.query}"
        
        I need to:
        1. Extract any relevant information from the user's query that can populate missing fields
        2. Determine if the user has provided information for any of the missing fields
        3. If information is provided, acknowledge it and ask for the next missing field
        4. If no relevant information is provided, ask for the most important missing field
        5. Be conversational and natural, not robotic
        
        Required fields to collect:
        - age: User's age (numeric)
        - dietary_restrictions: List of dietary restrictions (vegetarian, vegan, gluten-free, etc.)
        - cuisine_preferences: List of cuisine preferences (Italian, Chinese, Mexican, etc.)
        - price_range: Budget preference (budget, mid-range, premium, luxury)
        - is_tourist: Whether user is a tourist (boolean)
        - cultural_background: List of cultural/ethnic backgrounds
        - food_allergies: List of food allergies (nuts, shellfish, dairy, etc.)
        - spice_tolerance: Spice tolerance level (1-5 scale)
        - preferred_languages: List of preferred languages
        - phone: Phone number
        
        Let me analyze the user's query for any extractable information and determine the best response.
        </think>
        
        You are a friendly onboarding assistant helping users complete their food preference profile.
        
        Current user information: {current_state}
        Missing fields: {missing_fields}
        User query: "{request.query}"
        
        Your task:
        1. Extract any relevant information from the user's query that matches the missing fields
        2. If information is provided, acknowledge it and ask for the next most important missing field
        3. If no relevant information, ask for the most important missing field conversationally
        4. Be natural and friendly, not robotic
        
        Required fields to collect:
        - age, dietary_restrictions, cuisine_preferences, price_range, is_tourist
        - cultural_background, food_allergies, spice_tolerance, preferred_languages, phone
        
        Respond with only your final answer to the user. Be conversational and helpful.
        """
        
        # Get response from Qwen
        response = llm_qwen.invoke(reasoning_prompt)
        raw_response = response.content.strip()
        
        # Parse response to separate thinking and final answer
        thinking_part = ""
        final_answer = raw_response
        
        if "<think>" in raw_response and "</think>" in raw_response:
            # Extract thinking part
            think_start = raw_response.find("<think>") + len("<think>")
            think_end = raw_response.find("</think>")
            thinking_part = raw_response[think_start:think_end].strip()
            
            # Extract final answer (everything after </think>)
            final_answer = raw_response[think_end + len("</think>"):].strip()
        
        # Clean up final answer - remove newlines and extra spaces
        final_answer = ' '.join(final_answer.split())
        
        # Store reasoning in Graphiti if thinking part exists
        if thinking_part:
            await memory_service.store_user_memory(
                current_user.uid,
                {
                    "content": f"Onboarding reasoning for query: {request.query}",
                    "metadata": {
                        "type": "reasoning",
                        "thinking": thinking_part,
                        "user_query": request.query,
                        "final_response": final_answer
                    }
                }
            )
        
        # Extract information from the user's query
        extracted_info = extract_user_information(request.query)
        
        # Update user profile with any extracted information
        if extracted_info:
            await _update_user_profile(current_user, extracted_info)
        
        # Store conversation interaction in memory service
        await memory_service.store_user_memory(
            current_user.uid,
            {
                "content": f"User: {request.query} | Assistant: {final_answer}",
                "metadata": {
                    "type": "onboarding_conversation",
                    "user_query": request.query,
                    "assistant_response": final_answer,
                    "extracted_info": extracted_info
                }
            }
        )
        
        # Check if user is now fully onboarded
        updated_db_state = await get_user_onboarding_state(current_user.email)
        updated_missing_fields = updated_db_state.get("missing_fields", [])
        
        if not updated_missing_fields:
            # User is fully onboarded
            current_user.is_onboarded = True
            current_user.save()
            
            final_answer = f"Perfect! Your personalization is now complete, {current_user.first_name}. I have all the information I need to provide you with amazing food recommendations!"
        
        return OnboardingResponse(final_answer=final_answer)
        
    except Exception as e:
        logger.error(f"Onboarding failed: {e}")
        raise HTTPException(status_code=500, detail=f"Onboarding failed: {str(e)}")


async def _update_user_profile(user: User, extracted_info: Dict[str, Any]) -> None:
    """
    Update user profile with extracted information
    """
    try:
        # Update user fields if they exist in extracted info
        if "phone" in extracted_info:
            user.phone = extracted_info["phone"]
        if "age" in extracted_info:
            user.age = extracted_info["age"]
        if "dietary_restrictions" in extracted_info:
            user.dietary_restrictions = extracted_info["dietary_restrictions"]
        if "cuisine_preferences" in extracted_info:
            user.cuisine_preferences = extracted_info["cuisine_preferences"]
        if "price_range" in extracted_info:
            user.price_range = extracted_info["price_range"]
        if "is_tourist" in extracted_info:
            user.is_tourist = extracted_info["is_tourist"]
        if "cultural_background" in extracted_info:
            user.cultural_background = extracted_info["cultural_background"]
        if "food_allergies" in extracted_info:
            user.food_allergies = extracted_info["food_allergies"]
        if "spice_tolerance" in extracted_info:
            user.spice_tolerance = extracted_info["spice_tolerance"]
        if "preferred_languages" in extracted_info:
            user.preferred_languages = extracted_info["preferred_languages"]
        
        # Save to database
        user.save()
        
        # Store in graph memory for additional context
        await memory_service.store_user_memory(
            user.uid,
            {
                "content": f"User profile updated with: {', '.join(extracted_info.keys())}",
                "metadata": extracted_info
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")


@router.post("/skip")
async def skip_onboarding(current_user: User = Depends(get_current_user)):
    """
    Skip onboarding and mark user as onboarded
    """
    try:
        # Mark user as onboarded
        current_user.is_onboarded = True
        current_user.save()
        
        # Create new JWT token with updated isOnboarded status
        new_token = security_manager.create_access_token({
            "sub": current_user.uid,
            "email": current_user.email,
            "isOnboarded": current_user.is_onboarded
        })
        
        # Store in graph memory
        await memory_service.store_user_memory(
            current_user.uid,
            {
                "content": f"User {current_user.email} skipped onboarding process",
                "metadata": {"action": "skip_onboarding"}
            }
        )
        
        return {
            "status": "success",
            "message": "Onboarding skipped successfully",
            "user": {
                "uid": current_user.uid,
                "email": current_user.email,
                "is_onboarded": current_user.is_onboarded,
                "isOnboarded": current_user.is_onboarded,
            },
            "access_token": new_token
        }
        
    except Exception as e:
        logger.error(f"Error skipping onboarding: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to skip onboarding: {str(e)}"
        )