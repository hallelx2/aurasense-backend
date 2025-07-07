"""
Request Schemas
Pydantic models for API requests
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


class VoiceProcessingRequest(BaseModel):
    """Voice processing request schema"""
    user_id: str
    session_id: Optional[str] = None
    audio_url: Optional[str] = None
    text_input: Optional[str] = None
    context: Dict[str, Any] = {}


class OnboardingData(BaseModel):
    """User onboarding data schema"""
    email: str
    cultural_background: List[str] = []
    dietary_restrictions: List[str] = []
    food_allergies: List[str] = []
    health_conditions: List[str] = []
    spice_tolerance: int = Field(default=3, ge=1, le=5)
    preferred_languages: List[str] = ["en"]
    location: Optional[Dict[str, float]] = None


class AuthenticationRequest(BaseModel):
    """Authentication request schema"""
    user_id: str
    challenge_response: str
    audio_url: Optional[str] = None
    session_id: Optional[str] = None


class LocationUpdateRequest(BaseModel):
    """Location update request schema"""
    user_id: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PreferenceUpdateRequest(BaseModel):
    """User preference update schema"""
    user_id: str
    preference_type: str
    preferences: Dict[str, Any]
    context: Dict[str, Any] = {}
