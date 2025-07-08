# tools.py

import os
import uuid
import aiofiles
import json
import tempfile
from pathlib import Path
from typing import Literal, TypedDict, Optional, Union, Dict, Any
from rich import print
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import List
from datetime import datetime

# Import your LLM clients
from .llm import stt_client, tts_client, llm_llama3, llm_deepseek, llm_qwen
from src.app.core.config import settings


class UserInformation(BaseModel):
    """Pydantic model for user information extracted from text"""

    email: Optional[EmailStr] = Field(None, description="User's email address")
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    username: Optional[str] = Field(None, description="User's username")
    phone: Optional[str] = Field(None, description="User's phone number")
    password: Optional[str] = Field(None, description="User's password")
    age: Optional[int] = Field(None, ge=0, le=150, description="User's age")
    dietary_restrictions: Optional[List[str]] = Field(
        default=[], description="User's dietary restrictions"
    )
    cuisine_preferences: Optional[List[str]] = Field(
        default=[], description="User's cuisine preferences"
    )
    price_range: Optional[str] = Field(
        None, description="User's price range preference"
    )
    is_tourist: Optional[bool] = Field(
        default=False, description="Whether user is a tourist"
    )
    cultural_background: Optional[List[str]] = Field(
        default=[], description="User's cultural background"
    )
    food_allergies: Optional[List[str]] = Field(
        default=[], description="User's food allergies"
    )
    spice_tolerance: Optional[int] = Field(
        None, ge=1, le=5, description="User's spice tolerance (1-5)"
    )
    preferred_languages: Optional[List[str]] = Field(
        default=["en"], description="User's preferred languages"
    )

    @field_validator("price_range")
    def validate_price_range(cls, v):
        if v is not None and v not in ["budget", "mid-range", "premium", "luxury"]:
            return None  # Return None for invalid values instead of raising error
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "phone": "+1234567890",
                "password": "securepassword123",
                "age": 30,
                "dietary_restrictions": ["vegetarian", "gluten-free"],
                "cuisine_preferences": ["italian", "mediterranean"],
                "price_range": "mid-range",
                "is_tourist": True,
                "cultural_background": ["italian", "american"],
                "food_allergies": ["nuts", "shellfish"],
                "spice_tolerance": 3,
                "preferred_languages": ["en", "it"]
            }
        }


class TranscriptionParams(TypedDict, total=False):
    """Type-safe transcription parameters for audio transcription"""

    model: Literal["whisper-large-v3-turbo", "distil-whisper-large-v3-en"]
    prompt: Optional[str]
    response_format: Literal["json", "text", "verbose_json", "srt", "vtt"]
    timestamp_granularities: Optional[List[Literal["word", "segment"]]]
    language: Optional[str]
    temperature: Optional[float]
    file: Optional[Any]  # File object


async def transcribe_audio(
    audio_input: Union[str, bytes],
    response_format: Literal["json", "text", "verbose_json", "srt", "vtt"] = "text",
    **kwargs,
) -> Union[str, Dict[str, Any]]:
    """
    Transcribe audio input to text.

    Args:
        audio_input: Either a file path (str) or audio bytes
        response_format: Format for the response
        **kwargs: Additional parameters for transcription

    Returns:
        Transcribed text or structured response based on response_format
    """

    # Set up type-safe transcription parameters
    transcription_params: TranscriptionParams = {
        "model": "distil-whisper-large-v3-en",
        "language": "en",
        "temperature": 0.0,
        "response_format": response_format,
        **kwargs,
    }

    temp_file = None

    try:
        if isinstance(audio_input, str):
            # Handle file path
            audio_path = Path(audio_input)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            with open(audio_path, "rb") as audio_file:
                transcription_params["file"] = audio_file
                response = stt_client.audio.transcriptions.create(
                    **transcription_params
                )

        elif isinstance(audio_input, bytes):
            # Handle bytes - write to temp file, transcribe, then cleanup
            try:
                # Create temporary file
                temp_fd, temp_file = tempfile.mkstemp(suffix=".wav")
                os.close(temp_fd)
                temp_path = Path(temp_file)

                # Write bytes to temp file
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(audio_input)

                # Transcribe the temp file
                with open(temp_path, "rb") as audio_file:
                    transcription_params["file"] = audio_file
                    response = stt_client.audio.transcriptions.create(
                        **transcription_params
                    )

            finally:
                # Clean up temp file
                if temp_file and Path(temp_file).exists():
                    Path(temp_file).unlink()
        else:
            raise ValueError("audio_input must be either a string (file path) or bytes")

        # Handle different response formats
        if response_format == "text":
            return response.text if hasattr(response, "text") else str(response)
        else:
            return response.dict() if hasattr(response, "dict") else response

    except Exception as e:
        # Clean up temp file on error
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()
        raise Exception(f"Transcription failed: {str(e)}")


async def convert_text_to_speech(
    text: str,
    voice: str = "Fritz-PlayAI",
    model: str = "playai-tts",
    response_format: str = "wav",
    output_path: Optional[str] = None,
    stream: bool = False,
    **kwargs,
) -> Union[str, bytes]:
    """
    Convert text to speech using TTS API.

    Args:
        text: The text to convert to speech
        voice: The voice to use for synthesis
        model: The TTS model to use
        response_format: The output format (wav, mp3, etc.)
        output_path: Optional file path to save the audio. If None, returns bytes
        stream: Whether to use streaming mode for file output
        **kwargs: Additional parameters to pass to the API

    Returns:
        str: File path if output_path is provided, bytes if not
    """

    try:
        # Set up TTS parameters
        tts_params = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": response_format,
            **kwargs,
        }

        # Generate speech
        response = tts_client.audio.speech.create(**tts_params)

        if not output_path:
            # Generate a random file name
            output_path = Path(f"output_{uuid.uuid4()}.{response_format}")

        # Save to file
        if stream and hasattr(response, "stream_to_file"):
            response.stream_to_file(output_path)
        elif hasattr(response, "write_to_file"):
            response.write_to_file(output_path)
        else:
            # Fallback: write response content to file
            with open(output_path, "wb") as f:
                f.write(response.content)

        return str(output_path)

    except Exception as e:
        raise Exception(f"Text-to-speech conversion failed: {str(e)}")


def extract_user_information(text: str) -> Dict[str, Any]:
    """
    Extract user information from text using structured LLM output with enhanced reasoning.
    This function now focuses on extracting the final answer without <think> tags.

    Args:
        text: Input text to extract information from

    Returns:
        Dictionary containing extracted user information
    """

    try:
        extraction_prompt = f"""
        You are an expert nutritionist and cultural food specialist. Extract user information from the following text.
        
        USER INPUT: {text}
        
        EXTRACTION RULES:
        1. Only extract information that is explicitly mentioned or clearly implied
        2. For dietary restrictions, look for mentions of: vegetarian, vegan, gluten-free, lactose-free, kosher, halal, keto, paleo, low-carb, diabetic, etc.
        3. For cuisine preferences, identify specific cuisines like: Italian, Chinese, Mexican, Indian, Japanese, Mediterranean, etc.
        4. For food allergies, look for mentions of: nuts, shellfish, dairy, eggs, soy, wheat, fish, etc.
        5. For cultural/religious restrictions, identify: pork restriction (Islamic/Jewish), beef restriction (Hindu), alcohol restrictions, etc.
        6. For spice tolerance, look for keywords: mild, medium, spicy, very spicy, no spice, love spice, etc.
        7. For price preferences, map to: budget, mid-range, premium, luxury
        8. For age, extract numeric values or age ranges
        9. For tourist status, look for travel-related mentions
        10. For preferred languages, identify language codes or language names
        
        Extract the information and provide the structured response directly. Do not include reasoning or thinking process.
        
        REQUIRED FIELDS TO EXTRACT:
        - Email address
        - First name
        - Last name
        - Username
        - Phone number
        - Password
        - Age (numeric)
        - Dietary restrictions (list)
        - Cuisine preferences (list)
        - Price range preference (budget/mid-range/premium/luxury)
        - Whether they are a tourist (boolean)
        - Cultural background (list)
        - Food allergies (list)
        - Spice tolerance (1-5 scale)
        - Preferred languages (list)
        """

        # Use Qwen model with reasoning capabilities
        llm_with_structured_response = llm_qwen.with_structured_output(
            UserInformation
        )
        response = llm_with_structured_response.invoke(extraction_prompt)

        # Convert to dict and filter out None values
        if hasattr(response, "dict"):
            result = response.model_dump()
        else:
            result = response

        # Filter out None values and empty lists
        filtered_result = {}
        for key, value in result.items():
            if value is not None and value != [] and value != "":
                filtered_result[key] = value

        return filtered_result

    except Exception as e:
        print(f"Error extracting user information: {str(e)}")
        return {}


# Authentication helper functions
async def authenticate_user(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Authenticate a user with the provided information.

    Args:
        user_info: Dictionary containing user information

    Returns:
        Dictionary containing authentication result
    """

    try:
        # This would integrate with your actual authentication system
        # For demo purposes, we'll simulate authentication

        required_fields = ["email", "first_name", "last_name", "password"]

        if not all(user_info.get(field) for field in required_fields):
            return {
                "success": False,
                "status": "pending_info",
                "message": "Missing required information",
            }

        # Simulate authentication logic
        email = user_info.get("email")

        # Example: Some users need verification
        if email in ["janedoe@example.com", "test@verification.com"]:
            return {
                "success": False,
                "status": "pending_verification",
                "message": "Voice verification required",
            }

        # Example: Simulate successful authentication
        return {
            "success": True,
            "status": "authenticated",
            "message": "Authentication successful",
            "user_id": str(uuid.uuid4()),
        }

    except Exception as e:
        return {
            "success": False,
            "status": "failed",
            "message": f"Authentication error: {str(e)}",
        }


async def verify_voice_match(
    spoken_text: str, expected_text: str, threshold: float = 0.9
) -> bool:
    """
    Verify if spoken text matches expected text for voice verification.

    Args:
        spoken_text: The text that was spoken by the user
        expected_text: The expected text for verification
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        Boolean indicating if verification passed
    """

    try:
        from difflib import SequenceMatcher

        # Clean and normalize both texts
        spoken_clean = spoken_text.strip().lower()
        expected_clean = expected_text.strip().lower()

        # Use difflib SequenceMatcher for fuzzy string matching
        matcher = SequenceMatcher(None, spoken_clean, expected_clean)
        similarity = matcher.ratio()

        # Return True if similarity meets or exceeds threshold
        return similarity >= threshold

    except Exception as e:
        print(f"Voice verification error: {str(e)}")
        return False


def generate_dietary_question(missing_field: str, user_context: Dict[str, Any] = None) -> str:
    """
    Generate contextual dietary preference questions using AI reasoning.
    
    Args:
        missing_field: The field that needs to be collected
        user_context: Any existing user information for context
        
    Returns:
        Personalized question string
    """
    context = user_context or {}
    
    dietary_questions = {
        "dietary_restrictions": [
            "I'd love to know about your dietary preferences! Are you vegetarian, vegan, gluten-free, or following any specific eating plan?",
            "Do you have any dietary restrictions I should know about? For example, are you vegetarian, vegan, keto, paleo, or have any medical dietary needs?",
            "Let's talk about your diet! Are there any foods you avoid for health, religious, or personal reasons?"
        ],
        "cuisine_preferences": [
            "What types of cuisine make your taste buds happy? Are you into Italian, Asian, Mexican, Mediterranean, or something else?",
            "Tell me about your favorite food styles! Do you love spicy Asian dishes, comfort Italian food, fresh Mediterranean, or maybe authentic Mexican?",
            "I'm curious about your food preferences! What cuisines do you find yourself craving most often?"
        ],
        "food_allergies": [
            "For your safety, do you have any food allergies I absolutely need to know about? Things like nuts, shellfish, dairy, or eggs?",
            "Are there any foods that cause allergic reactions for you? I want to make sure we avoid anything dangerous like nuts, shellfish, or dairy.",
            "Let's talk about food allergies - do you have any that I should be aware of when suggesting restaurants?"
        ],
        "cultural_background": [
            "What's your cultural background? This helps me recommend authentic experiences and understand any cultural food preferences.",
            "I'd love to learn about your cultural heritage! Are there specific cultural or religious food traditions that are important to you?",
            "Tell me about your cultural background - this helps me suggest authentic restaurants and respect any cultural food preferences."
        ],
        "spice_tolerance": [
            "How do you handle spicy food? Are you a mild person, or do you love the heat? Rate yourself from 1 (no spice) to 5 (bring the fire)!",
            "Let's talk spice! On a scale of 1-5, where 1 is mild and 5 is super spicy, what's your comfort level?",
            "Are you a spice lover or do you prefer milder flavors? Rate your spice tolerance from 1 (mild) to 5 (very spicy)."
        ],
        "preferred_languages": [
            "What languages do you prefer to communicate in? This helps me find restaurants with staff who speak your language.",
            "Which languages are you most comfortable with? I can suggest places where you'll feel at home communicating.",
            "Do you have preferred languages for communication? This helps me recommend restaurants with multilingual staff."
        ],
        "price_range": [
            "What's your budget comfort zone for dining? Are you looking for budget-friendly spots, mid-range gems, or maybe premium experiences?",
            "Let's talk budget! Are you more of a budget-conscious diner, mid-range explorer, or do you enjoy premium dining experiences?",
            "What price range feels right for you? Budget-friendly, mid-range, premium, or luxury dining?"
        ]
    }
    
    questions = dietary_questions.get(missing_field, [f"Can you tell me about your {missing_field.replace('_', ' ')}?"])
    
    # Use AI to select and customize the question based on context
    if context:
        prompt = f"""
        Based on the user context: {context}
        
        Select and customize the most appropriate question from these options:
        {questions}
        
        Make it personal and conversational while maintaining the core information need.
        Return only the customized question, no additional text.
        """
        
        try:
            response = llm_qwen.invoke(prompt)
            return response.content.strip()
        except:
            pass
    
    # Fallback to first question if AI fails
    import random
    return random.choice(questions)


def validate_dietary_response(field: str, response: str) -> Dict[str, Any]:
    """
    Validate and normalize dietary preference responses using AI reasoning.
    
    Args:
        field: The field being validated
        response: User's response
        
    Returns:
        Dictionary with validation results and normalized value
    """
    
    validation_prompt = f"""
    You are validating a user's response for the field: {field}
    User response: {response}
    
    Based on the field type, validate and normalize the response:
    
    For dietary_restrictions: Convert to list of standard dietary restrictions
    For cuisine_preferences: Convert to list of standard cuisine types
    For food_allergies: Convert to list of standard allergens
    For cultural_background: Convert to list of cultural/ethnic backgrounds
    For spice_tolerance: Convert to integer 1-5 scale
    For preferred_languages: Convert to list of language codes
    For price_range: Convert to one of: budget, mid-range, premium, luxury
    
    Return a JSON object with:
    - "valid": boolean
    - "normalized_value": the normalized value
    - "confidence": float 0-1
    - "suggestions": list of clarifying questions if needed
    """
    
    try:
        response = llm_qwen.invoke(validation_prompt)
        import json
        return json.loads(response.content)
    except:
        return {
            "valid": False,
            "normalized_value": None,
            "confidence": 0.0,
            "suggestions": [f"Could you clarify your {field.replace('_', ' ')}?"]
        }


async def get_user_onboarding_state(user_email: str) -> Dict[str, Any]:
    """
    Get the current onboarding state for a user from the database.
    Args:
        user_email: User's email address
    Returns:
        Dictionary with current user state and missing fields
    """
    try:
        from src.app.models.user import User
        
        # Find the user by email
        user = User.nodes.filter(email=user_email).first()
        if not user:
            return {"success": False, "message": "User not found", "missing_fields": []}
        
        # Define all possible onboarding fields
        onboarding_fields = [
            "age", "dietary_restrictions", "cuisine_preferences", 
            "price_range", "is_tourist", "cultural_background", 
            "food_allergies", "spice_tolerance", "preferred_languages", "phone"
        ]
        
        # Get current user state
        current_state = {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "phone": user.phone,
            "age": user.age,
            "dietary_restrictions": user.dietary_restrictions or [],
            "cuisine_preferences": user.cuisine_preferences or [],
            "price_range": user.price_range,
            "is_tourist": user.is_tourist,
            "cultural_background": user.cultural_background or [],
            "food_allergies": user.food_allergies or [],
            "spice_tolerance": user.spice_tolerance,
            "preferred_languages": user.preferred_languages or ["en"],
            "is_onboarded": user.is_onboarded
        }
        
        # Identify missing fields
        missing_fields = []
        for field in onboarding_fields:
            value = current_state.get(field)
            if value is None or (isinstance(value, list) and len(value) == 0):
                missing_fields.append(field)
        
        return {
            "success": True,
            "current_state": current_state,
            "missing_fields": missing_fields,
            "is_onboarded": user.is_onboarded,
            "completion_percentage": ((len(onboarding_fields) - len(missing_fields)) / len(onboarding_fields)) * 100
        }
        
    except Exception as e:
        return {"success": False, "message": str(e), "missing_fields": []}


def generate_contextual_onboarding_question(missing_field: str, current_state: Dict[str, Any]) -> str:
    """
    Generate a contextual, intelligent onboarding question based on the missing field and current user state.
    Args:
        missing_field: The field that needs to be collected
        current_state: Current user information for context
    Returns:
        Personalized question string
    """
    
    # Get user's name for personalization
    first_name = current_state.get("first_name", "")
    name_greeting = f"{first_name}, " if first_name else ""
    
    # Context-aware question generation
    question_prompts = {
        "age": f"Hi {name_greeting}to provide you with the most suitable recommendations, could you tell me your age?",
        
        "dietary_restrictions": f"{name_greeting}I'd love to know about your dietary preferences! Are you vegetarian, vegan, gluten-free, or following any specific eating plan?",
        
        "cuisine_preferences": f"{name_greeting}what types of cuisine make your taste buds happy? Are you into Italian, Asian, Mexican, Mediterranean, or something else?",
        
        "price_range": f"{name_greeting}what's your preferred price range when dining out? Are you looking for budget-friendly spots, mid-range options, premium experiences, or luxury dining?",
        
        "is_tourist": f"{name_greeting}are you visiting this area as a tourist, or do you live here locally? This helps me recommend the best experiences for you.",
        
        "cultural_background": f"{name_greeting}what's your cultural background? This helps me recommend authentic experiences and understand any cultural food preferences you might have.",
        
        "food_allergies": f"{name_greeting}for your safety, do you have any food allergies I absolutely need to know about? Things like nuts, shellfish, dairy, or eggs?",
        
        "spice_tolerance": f"{name_greeting}how do you handle spicy food? Are you a mild person, or do you love the heat? Rate yourself from 1 (no spice) to 5 (bring the fire)!",
        
        "preferred_languages": f"{name_greeting}what languages do you prefer to communicate in? This helps me find restaurants with staff who speak your language.",
        
        "phone": f"{name_greeting}what's your phone number? This helps us send you important updates and reservation confirmations."
    }
    
    # Get the base question
    base_question = question_prompts.get(missing_field, f"{name_greeting}could you tell me about your {missing_field.replace('_', ' ')}?")
    
    # Use AI to make it more contextual if we have enough user information
    if len(current_state) > 3:  # If we have some context
        try:
            context_prompt = f"""
            You are a friendly onboarding assistant. Based on the user's current information: {current_state}
            
            Generate a personalized, conversational question to ask about their {missing_field.replace('_', ' ')}.
            Make it feel natural and contextual based on what you already know about them.
            
            Base question: {base_question}
            
            Requirements:
            - Make it personal but not intrusive
            - Keep it concise and conversational
            - Return ONLY the final question
            - Do not include any reasoning, thinking, or additional text
            - Do not use <think> tags or similar formatting
            
            Respond with just the question:
            """
            
            response = llm_qwen.invoke(context_prompt)
            return response.content.strip()
            
        except Exception as e:
            print(f"AI question generation failed: {e}")
            return base_question
    
    return base_question


async def save_user_to_graph_db(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save the onboarded user to the graph database.
    Args:
        user_info: Dictionary containing all user onboarding information
    Returns:
        Dictionary with success status and message
    """
    try:
        from src.app.models.user import User

        # Find the user by email (assuming email is always present)
        email = user_info.get("email")
        if not email:
            return {"success": False, "message": "Email is required to save user"}

        user = User.nodes.filter(email=email).first()
        if not user:
            return {"success": False, "message": "User not found"}

        # Update user with onboarding information
        user.username = user_info.get("username", user.username)
        user.phone = user_info.get("phone", user.phone)
        user.age = user_info.get("age", user.age)
        user.dietary_restrictions = user_info.get("dietary_restrictions", user.dietary_restrictions)
        user.cuisine_preferences = user_info.get("cuisine_preferences", user.cuisine_preferences)
        user.price_range = user_info.get("price_range", user.price_range)
        user.is_tourist = user_info.get("is_tourist", user.is_tourist)
        user.cultural_background = user_info.get("cultural_background", user.cultural_background)
        user.food_allergies = user_info.get("food_allergies", user.food_allergies)
        user.spice_tolerance = user_info.get("spice_tolerance", user.spice_tolerance)
        user.preferred_languages = user_info.get("preferred_languages", user.preferred_languages)

        # Mark user as onboarded
        user.is_onboarded = True

        # Save to database
        user.save()

        return {"success": True, "message": "User onboarding completed and saved to graph DB"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# Testing functions
# async def test_transcription():
#     """Test transcription functionality"""
#     test_text = "Hello, this is a test of the transcription system."

#     # Convert to speech first
#     audio_path = await convert_text_to_speech(test_text)
#     print(f"Audio saved to: {audio_path}")

#     # Then transcribe back
#     transcribed = await transcribe_audio(audio_path)
#     print(f"Transcribed: {transcribed}")

#     # Clean up
#     if Path(audio_path).exists():
#         Path(audio_path).unlink()


# async def test_information_extraction():
#     """Test information extraction"""
#     test_text = "Hi, my name is John Doe, my email is john.doe@example.com and my password is secret123"

#     extracted = extract_user_information(test_text)
#     print(f"Extracted information: {extracted}")


# if __name__ == "__main__":
#     import asyncio

#     # Test the functions
#     asyncio.run(test_transcription())
#     asyncio.run(test_information_extraction())
