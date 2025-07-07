"""
Session Model
Session and interaction data structures
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class UserSession(BaseModel):
    """User session data model"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    is_authenticated: bool = False
    current_agent: Optional[str] = None
    conversation_history: List[Dict[str, Any]] = []
    context_data: Dict[str, Any] = {}
    location: Optional[Dict[str, Any]] = None
    device_info: Dict[str, str] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class VoiceInteraction(BaseModel):
    """Voice interaction data model"""
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    agent_name: str
    audio_url: Optional[str] = None
    transcribed_text: str
    agent_response: str
    response_audio_url: Optional[str] = None
    processing_time: float = 0.0
    confidence_score: float = 0.0
    cultural_context: Dict[str, Any] = {}
    health_flags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AudioSession(BaseModel):
    """Audio processing session model for alternative architecture"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    audio_url: str
    status: str = "processing"  # processing, completed, failed
    transcription: Optional[str] = None
    agent_response: Optional[str] = None
    processing_metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class AgentInteraction(BaseModel):
    """Agent interaction data model"""
    interaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: str
    agent_name: str
    user_input: str
    agent_response: str
    input_type: str = "voice"
    response_type: str = "voice"
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    context_used: Dict[str, Any] = {}
    feedback: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceAuthSession(BaseModel):
    """Voice authentication session"""
    auth_session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    challenge_sentence: str
    challenge_sent_at: datetime
    audio_response_url: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None
    auth_status: str = "pending"
    attempts_count: int = 0
    max_attempts: int = 3
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
