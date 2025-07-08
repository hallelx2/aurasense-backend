"""
Restaurant Model
Restaurant and food data structures
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, time
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
    JSONProperty,
)
from datetime import datetime

# Import shared relationship models from user.py
from src.app.models.relationships import (
    RatingRel,
    SimilarityRel,
    LikesRel,
    DislikesRel,
    VisitedRel,
)
from src.app.core.config import settings

config.DATABASE_URL = settings.DATABASE_URL


class Restaurant(StructuredNode):
    restaurant_id: str = UniqueIdProperty()
    name: str = StringProperty(required=True, index=True)
    description: str | None = StringProperty()

    cuisine_type: list[str] | None = ArrayProperty(StringProperty())
    categories: list[str] | None = ArrayProperty(StringProperty())

    price_range: str | None = StringProperty(
        choices=[
            ("budget", "budget"),
            ("mid-range", "mid-range"),
            ("premium", "premium"),
            ("luxury", "luxury"),
        ]
    )
    rating: float = FloatProperty(default=0.0)
    total_reviews: int = IntegerProperty(default=0)

    features: list[str] | None = ArrayProperty(StringProperty())
    dietary_options: list[str] | None = ArrayProperty(StringProperty())

    opening_hours = JSONProperty()
    is_active: bool = BooleanProperty(default=True)

    # Relationships
    located_in = RelationshipTo("Location", "LOCATED_IN")
    menu_items = RelationshipTo("MenuItem", "SERVES")
    similar_to = RelationshipTo("Restaurant", "SIMILAR_TO", model=SimilarityRel)


class Restaurant(BaseModel):
    """Restaurant data model"""

    restaurant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    cuisine_types: List[str] = []
    cultural_background: List[str] = []
    address: str
    latitude: float
    longitude: float
    phone: Optional[str] = None
    rating: Optional[float] = None
    price_level: Optional[int] = Field(None, ge=1, le=4)
    opening_hours: Dict[str, Dict[str, str]] = {}
    dietary_options: List[str] = []
    allergen_warnings: List[str] = []
    traditional_dishes: List[str] = []
    google_place_id: Optional[str] = None
    external_ids: Dict[str, str] = {}
    data_quality_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MenuItem(BaseModel):
    """Menu item data model"""

    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    restaurant_id: str
    name: str
    description: str
    price: float
    currency: str = "USD"
    category: str
    dietary_tags: List[str] = []
    allergens: List[str] = []
    nutritional_info: Dict[str, Any] = {}
    spice_level: Optional[int] = Field(None, ge=1, le=5)
    cultural_authenticity: Optional[str] = None
    preparation_time: Optional[int] = None
    availability: bool = True
    image_url: Optional[str] = None


class RestaurantAvailability(BaseModel):
    """Restaurant availability status"""

    restaurant_id: str
    is_open: bool
    is_accepting_orders: bool
    estimated_wait_time: Optional[int] = None
    delivery_available: bool = True
    pickup_available: bool = True
    special_notes: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class FoodOrder(BaseModel):
    """Food order data model"""

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    restaurant_id: str
    items: List[Dict[str, Any]] = []
    total_amount: float
    currency: str = "USD"
    order_type: str = "delivery"  # delivery, pickup
    delivery_address: Optional[Dict[str, str]] = None
    special_instructions: Optional[str] = None
    order_status: str = "pending"
    estimated_delivery_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
