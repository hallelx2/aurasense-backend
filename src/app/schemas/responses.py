"""
Response Schemas
Pydantic models for API responses
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseResponse(BaseModel):
    """Base response schema"""
    success: bool = True
    message: str = "Operation completed successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class VoiceProcessingResponse(BaseResponse):
    """Voice processing response schema"""
    transcription: str
    agent_response: str
    agent_name: str
    confidence_score: float
    response_audio_url: Optional[str] = None
    session_id: str
    context_updates: Dict[str, Any] = {}


class AuthenticationResponse(BaseResponse):
    """Authentication response schema"""
    authenticated: bool
    user_id: str
    session_id: str
    access_token: Optional[str] = None
    challenge_sentence: Optional[str] = None
    verification_score: Optional[float] = None


class RecommendationResponse(BaseResponse):
    """Recommendation response schema"""
    recommendations: List[Dict[str, Any]]
    recommendation_type: str
    personalization_score: float
    cultural_context: Dict[str, Any] = {}
    health_considerations: List[str] = []


class OrderResponse(BaseResponse):
    """Order response schema"""
    order_id: str
    restaurant_name: str
    estimated_delivery_time: Optional[datetime] = None
    total_amount: float
    currency: str = "USD"
    order_status: str = "confirmed"


class SessionResponse(BaseResponse):
    """Session response schema"""
    session_id: str
    user_id: str
    expires_at: Optional[datetime] = None
    current_context: Dict[str, Any] = {}
