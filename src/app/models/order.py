"""
Order Model
Graph node for orders (neomodel)
"""

from neomodel import (
    config,
    StructuredNode,
    StringProperty,
    FloatProperty,
    UniqueIdProperty,
    DateTimeProperty,
    RelationshipFrom,
    RelationshipTo,
)
from datetime import datetime
from src.app.models.relationships import OrderItemRel
from src.app.core.config import settings

config.DATABASE_URL = settings.DATABASE_URL


class Order(StructuredNode):
    order_id: str = UniqueIdProperty()
    order_date: datetime = DateTimeProperty(default_now=True)
    total_amount: float | None = FloatProperty()
    status: str | None = StringProperty(
        choices=[
            ("pending", "pending"),
            ("confirmed", "confirmed"),
            ("delivered", "delivered"),
            ("cancelled", "cancelled"),
        ]
    )

    # Relationships
    user = RelationshipFrom("User", "PLACED_ORDER")
    restaurant = RelationshipTo("Restaurant", "FROM_RESTAURANT")
    items = RelationshipTo("MenuItem", "CONTAINS")
