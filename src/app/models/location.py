"""
Location Model
Graph node and relationship model for locations (neomodel)
"""

from neomodel import (
    config,
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
from src.app.models.relationships import DistanceRel
from src.app.core.config import settings
config.DATABASE_URL = settings.DATABASE_URL
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
