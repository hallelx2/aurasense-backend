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
    Extract user information from text using structured LLM output.

    Args:
        text: Input text to extract information from

    Returns:
        Dictionary containing extracted user information
    """

    try:
        # Create a prompt for extracting user information
        extraction_prompt = f"""
        Extract user information from the following text. Only extract information that is explicitly mentioned.
        If information is not provided, do not make assumptions.

        Text: {text}

        Extract the following if mentioned:
        - Email address
        - First name
        - Last name
        - Username
        - Phone number
        - Password
        - Age
        - Dietary restrictions
        - Cuisine preferences
        - Price range preference (budget, mid-range, premium, luxury)
        - Whether they are a tourist
        """

        # Use structured output with the LLM
        llm_with_structured_response = llm_llama3.with_structured_output(
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
        # Return empty dict on error rather than raising
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

        # Note: cultural_background, food_allergies, spice_tolerance, preferred_languages
        # are not in the current User model - they would need to be added or stored separately

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
