from neomodel import (
    config,
    StructuredRel,
    StringProperty,
    IntegerProperty,
    FloatProperty,
    BooleanProperty,
    DateTimeProperty,
    ArrayProperty,
)
from datetime import datetime
from src.app.core.config import settings
config.DATABASE_URL = settings.DATABASE_URL
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

class SimilarityRel(StructuredRel):
    similarity_score: float | None = FloatProperty()
    similarity_reasons: list[str] | None = ArrayProperty(StringProperty())
    calculated_at: datetime = DateTimeProperty(default_now=True)

class OrderItemRel(StructuredRel):
    quantity: int = IntegerProperty(default=1)
    unit_price: float | None = FloatProperty()
    special_instructions: str | None = StringProperty()
    satisfaction_rating: float | None = FloatProperty()

class DistanceRel(StructuredRel):
    distance_km: float | None = FloatProperty()
    travel_time_minutes: int | None = IntegerProperty()
    transportation_type: str | None = StringProperty(choices=[
        ("walking", "walking"),
        ("driving", "driving"),
        ("public_transport", "public_transport"),
    ])
