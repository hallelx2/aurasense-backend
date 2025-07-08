"""
Hotel Model
Hotel and accommodation data structures
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid

# --- Graph Node and Relationship Models (from schema.py) ---
from neomodel import (
    config,
    StructuredNode,
    StringProperty,
    IntegerProperty,
    FloatProperty,
    BooleanProperty,
    ArrayProperty,
    UniqueIdProperty,
    DateTimeProperty,
    RelationshipTo,
)

# Import shared relationship models from user.py
from src.app.models.relationships import StayedRel, RatingRel
from src.app.core.config import settings

config.DATABASE_URL = settings.DATABASE_URL


class Hotel(StructuredNode):
    """Hotel data model"""

    hotel_id: str = UniqueIdProperty()
    name: str = StringProperty(required=True, index=True)
    address: str
    latitude: float
    longitude: float
    star_rating: int | None = IntegerProperty()
    rating: Optional[float] = None
    price_range: str | None = StringProperty(
        choices=[
            ("budget", "budget"),
            ("mid-range", "mid-range"),
            ("premium", "premium"),
            ("luxury", "luxury"),
        ]
    )
    hotel_type: str | None = StringProperty(
        choices=[
            ("business", "business"),
            ("leisure", "leisure"),
            ("boutique", "boutique"),
            ("resort", "resort"),
        ]
    )
    amenities: list[str] | None = ArrayProperty(StringProperty())
    room_types: List[str] = []
    cultural_features: List[str] = []
    dietary_accommodations: List[str] = []
    phone: Optional[str] = None
    website: Optional[str] = None
    booking_url: Optional[str] = None
    images: List[str] = []
    description: str | None = StringProperty()
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    is_active: bool = BooleanProperty(default=True)
    created_at: datetime = DateTimeProperty(default_now=True)
    updated_at: datetime = DateTimeProperty(default_now=True)

    # Relationships
    located_in = RelationshipTo("Location", "LOCATED_IN")
    has_restaurants = RelationshipTo("Restaurant", "HAS_RESTAURANT")
    # Ratings and stays
    rated_by = RelationshipTo("User", "RATED", model=RatingRel)
    stayed_by = RelationshipTo("User", "STAYED_AT", model=StayedRel)


class HotelBooking(BaseModel):
    """Hotel booking data model"""

    booking_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    hotel_id: str
    check_in_date: date
    check_out_date: date
    room_type: str
    number_of_guests: int
    special_requests: Optional[str] = None
    total_amount: float
    currency: str = "USD"
    booking_status: str = "pending"
    confirmation_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TravelContext(BaseModel):
    """Travel context data model"""

    user_id: str
    current_location: Dict[str, Any]
    destination: Optional[Dict[str, Any]] = None
    travel_dates: Optional[Dict[str, date]] = None
    travel_purpose: Optional[str] = None
    accommodation_preferences: Dict[str, Any] = {}
    dietary_needs_while_traveling: List[str] = []
    cultural_interests: List[str] = []
    budget_constraints: Optional[Dict[str, float]] = None
    travel_companions: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
