"""
MenuItem Model
Graph node and relationship model for menu items (neomodel)
"""

from neomodel import (
    config,
    StructuredNode,
    StructuredRel,
    StringProperty,
    FloatProperty,
    ArrayProperty,
    UniqueIdProperty,
    RelationshipFrom,
    DateTimeProperty,
    IntegerProperty,
)
from datetime import datetime
from src.app.models.relationships import OrderItemRel
from src.app.core.config import settings
config.DATABASE_URL = settings.DATABASE_URL
class MenuItem(StructuredNode):
    name: str = StringProperty(required=True)
    description: str | None = StringProperty()
    price: float | None = FloatProperty()
    category: str | None = StringProperty()

    dietary_tags: list[str] | None = ArrayProperty(StringProperty())
    ingredients: list[str] | None = ArrayProperty(StringProperty())

    # Relationships
    restaurant = RelationshipFrom("Restaurant", "SERVES")
    ordered_by = RelationshipFrom("User", "ORDERED", model=OrderItemRel)
