"""
User Model
User data structures and graph models (now using neomodel)
"""

# NOTE: User data is now managed via the graph database using neomodel.
# Import the User node from the graph_models package.
# from src.app.graph_models import User

# If you need to use Pydantic models for API validation, define them separately.
# All persistence and queries should use the neomodel User class.

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# --- Graph Node and Relationship Models (from schema.py) ---
from neomodel import (
    StructuredNode,
    StructuredRel,
    StringProperty,
    IntegerProperty,
    FloatProperty,
    BooleanProperty,
    ArrayProperty,
    UniqueIdProperty,
    DateTimeProperty,
    EmailProperty,
    RelationshipTo,
    RelationshipFrom,
    JSONProperty,
)

class VisitedRel(StructuredRel):
    visited_date: datetime = DateTimeProperty(default_now=True)
    visit_purpose: str | None = StringProperty(choices=[
        ("dining", "dining"),
        ("business", "business"),
        ("celebration", "celebration"),
        ("casual", "casual"),
    ])
    party_size: int | None = IntegerProperty()
    duration_minutes: int | None = IntegerProperty()
    weather: str | None = StringProperty()
    occasion: str | None = StringProperty()
    sentiment_score: float | None = FloatProperty()
    would_return: bool | None = BooleanProperty()

class StayedRel(StructuredRel):
    check_in: datetime | None = DateTimeProperty()
    check_out: datetime | None = DateTimeProperty()
    room_type: str | None = StringProperty()
    purpose: str | None = StringProperty(choices=[
        ("business", "business"),
        ("leisure", "leisure"),
        ("event", "event"),
    ])
    booking_price: float | None = FloatProperty()
    would_recommend: bool | None = BooleanProperty()

class LikesRel(StructuredRel):
    liked_at: datetime = DateTimeProperty(default_now=True)
    reason: str | None = StringProperty()
    intensity: int = IntegerProperty(default=5)
    liked_aspects: list[str] | None = ArrayProperty(StringProperty())

class DislikesRel(StructuredRel):
    disliked_at: datetime = DateTimeProperty(default_now=True)
    reason: str | None = StringProperty()
    intensity: int = IntegerProperty(default=5)
    disliked_aspects: list[str] | None = ArrayProperty(StringProperty())

class RatingRel(StructuredRel):
    rating: float = FloatProperty(required=True)
    review_text: str | None = StringProperty()
    rated_at: datetime = DateTimeProperty(default_now=True)
    food_rating: float | None = FloatProperty()
    service_rating: float | None = FloatProperty()
    ambiance_rating: float | None = FloatProperty()
    value_rating: float | None = FloatProperty()

class FriendsRel(StructuredRel):
    friends_since: datetime = DateTimeProperty(default_now=True)
    shared_meals: int = IntegerProperty(default=0)
    similar_taste_score: float | None = FloatProperty()

class User(StructuredNode):
    uid: str = UniqueIdProperty()
    email: str = EmailProperty(unique_index=True, required=True)
    username: str | None = StringProperty(unique_index=True)
    password_hash: str = StringProperty(required=True)  # Argon2 hashed password

    # Profile
    first_name: str = StringProperty(required=True)
    last_name: str = StringProperty(required=True)
    phone: str | None = StringProperty()
    age: int | None = IntegerProperty()

    # Preferences
    dietary_restrictions: list[str] | None = ArrayProperty(StringProperty())
    cuisine_preferences: list[str] | None = ArrayProperty(StringProperty())
    price_range: str | None = StringProperty(
        choices=[("budget", "budget"), ("mid-range", "mid-range"), ("premium", "premium"), ("luxury", "luxury")]
    )

    # Temporal
    created_at: datetime = DateTimeProperty(default_now=True)
    last_active: datetime = DateTimeProperty(default_now=True)
    is_tourist: bool = BooleanProperty(default=False)

    # Relationships
    current_location = RelationshipTo("Location", "CURRENTLY_AT")
    home_location = RelationshipTo("Location", "LIVES_IN")

    friends = RelationshipTo("User", "FRIENDS", model=FriendsRel)
    follows = RelationshipTo("User", "FOLLOWS")

    visited_restaurants = RelationshipTo(
        "Restaurant", "VISITED", model=VisitedRel
    )
    visited_hotels = RelationshipTo("Hotel", "STAYED_AT", model=StayedRel)

    likes = RelationshipTo("Restaurant", "LIKES", model=LikesRel)
    dislikes = RelationshipTo("Restaurant", "DISLIKES", model=DislikesRel)
    rated_restaurants = RelationshipTo("Restaurant", "RATED", model=RatingRel)
    rated_hotels = RelationshipTo("Hotel", "RATED", model=RatingRel)

    orders = RelationshipTo("Order", "PLACED_ORDER")

class UserProfile(BaseModel):
    """User profile data model"""
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    cultural_background: List[str] = []
    dietary_restrictions: List[str] = []
    food_allergies: List[str] = []
    health_conditions: List[str] = []
    spice_tolerance: int = Field(default=3, ge=1, le=5)
    preferred_languages: List[str] = ["en"]
    location: Optional[Dict[str, Any]] = None
    voice_profile: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VoiceProfile(BaseModel):
    """Voice authentication profile"""
    user_id: str
    voice_print_hash: str
    accent_type: Optional[str] = None
    language_preferences: List[str] = []
    cultural_voice_markers: Dict[str, Any] = {}
    verification_accuracy: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: Optional[datetime] = None


class HealthProfile(BaseModel):
    """Health and dietary profile"""
    user_id: str
    allergies: List[str] = []
    dietary_restrictions: List[str] = []
    health_conditions: List[str] = []
    medications: List[str] = []
    nutritional_goals: Dict[str, Any] = {}
    emergency_contacts: List[Dict[str, str]] = []


class CulturalProfile(BaseModel):
    """Cultural background and preferences"""
    user_id: str
    cultural_backgrounds: List[str] = []
    religious_preferences: List[str] = []
    traditional_cuisines: List[str] = []
    cultural_restrictions: List[str] = []
    festival_preferences: List[str] = []
    language_preferences: List[str] = []
