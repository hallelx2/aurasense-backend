"""
MenuItem Model
Graph node and relationship model for menu items (neomodel)
"""

from neomodel import (
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

class OrderItemRel(StructuredRel):
    quantity: int = IntegerProperty(default=1)
    unit_price: float | None = FloatProperty()
    special_instructions: str | None = StringProperty()
    satisfaction_rating: float | None = FloatProperty()

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
