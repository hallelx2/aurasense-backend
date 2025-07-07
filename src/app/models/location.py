"""
Location Model
Graph node and relationship model for locations (neomodel)
"""

from neomodel import (
    StructuredNode,
    StructuredRel,
    StringProperty,
    FloatProperty,
    IntegerProperty,
    BooleanProperty,
    ArrayProperty,
    DateTimeProperty,
    RelationshipTo,
)

class DistanceRel(StructuredRel):
    distance_km: float | None = FloatProperty()
    travel_time_minutes: int | None = IntegerProperty()
    transportation_type: str | None = StringProperty(choices=[
        ("walking", "walking"),
        ("driving", "driving"),
        ("public_transport", "public_transport"),
    ])

class Location(StructuredNode):
    name: str = StringProperty(required=True, index=True)
    city: str = StringProperty(required=True, index=True)
    state: str | None = StringProperty()
    country: str = StringProperty(required=True)
    latitude: float | None = FloatProperty()
    longitude: float | None = FloatProperty()
    location_type: str | None = StringProperty(choices=[
        ("neighborhood", "neighborhood"),
        ("district", "district"),
        ("city", "city"),
        ("landmark", "landmark"),
    ])

    # Relationships
    nearby_locations = RelationshipTo(
        "Location",
        "NEAR",
        model=DistanceRel,
    )
