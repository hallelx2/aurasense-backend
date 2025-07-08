"""
Formatters
Output formatting utilities
"""

from typing import Dict, Any, Optional
from datetime import datetime
import json


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format currency amount
    """
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CAD": "C$",
        "AUD": "A$",
    }

    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"


def format_datetime(dt: datetime, format_type: str = "standard") -> str:
    """
    Format datetime for display
    """
    formats = {
        "standard": "%Y-%m-%d %H:%M:%S",
        "date_only": "%Y-%m-%d",
        "time_only": "%H:%M:%S",
        "human": "%B %d, %Y at %I:%M %p",
        "iso": "%Y-%m-%dT%H:%M:%SZ",
    }

    format_str = formats.get(format_type, formats["standard"])
    return dt.strftime(format_str)


def format_response(
    data: Any, success: bool = True, message: str = ""
) -> Dict[str, Any]:
    """
    Format API response consistently
    """
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data,
    }

    if message:
        response["message"] = message

    return response


def format_food_recommendation(
    restaurant: Dict[str, Any], user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format food recommendation for display
    """
    formatted = {
        "name": restaurant.get("name", "Unknown Restaurant"),
        "cuisine": restaurant.get("cuisine_types", []),
        "rating": restaurant.get("rating", 0),
        "price_level": restaurant.get("price_level", 0),
        "distance": restaurant.get("distance", 0),
        "cultural_match": restaurant.get("cultural_match_score", 0),
        "health_score": restaurant.get("health_score", 0),
        "estimated_wait": restaurant.get("estimated_wait_time", 0),
        "dietary_options": restaurant.get("dietary_options", []),
        "address": restaurant.get("address", ""),
    }

    return formatted


def format_voice_response(text: str, cultural_context: Dict[str, Any]) -> str:
    """
    Format text response for voice synthesis with cultural adaptation
    """
    # Basic cultural adaptation
    if cultural_context.get("formal_address", False):
        # Use more formal language
        text = text.replace("Hey", "Hello")
        text = text.replace("Yeah", "Yes")

    # Add cultural greetings if appropriate
    cultural_background = cultural_context.get("cultural_background", [])
    if "indian" in cultural_background:
        text = text.replace("Hello", "Namaste")
    elif "japanese" in cultural_background:
        text = text.replace("Hello", "Konnichiwa")

    return text


def format_audio_metadata(audio_data: bytes) -> Dict[str, Any]:
    """
    Format audio metadata for response
    """
    metadata = {
        "size_bytes": len(audio_data),
        "size_mb": round(len(audio_data) / (1024 * 1024), 2),
        "format": "audio/wav",  # Default format
        "duration_estimate": 0.0,  # Will be calculated
        "quality": "standard",
    }

    return metadata
