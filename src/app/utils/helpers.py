"""
Helpers
Common helper functions
"""

import uuid
import math
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


def generate_session_id() -> str:
    """
    Generate unique session ID
    """
    return str(uuid.uuid4())


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates in kilometers
    """
    # Haversine formula
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def merge_contexts(
    base_context: Dict[str, Any], new_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge two context dictionaries
    """
    merged = base_context.copy()

    for key, value in new_context.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_contexts(merged[key], value)
        else:
            merged[key] = value

    return merged


def extract_cultural_indicators(text: str) -> Dict[str, Any]:
    """
    Extract cultural indicators from text
    """
    # Basic cultural indicator extraction
    # Can be enhanced with more sophisticated NLP
    indicators = {
        "religious_terms": [],
        "cultural_foods": [],
        "languages": [],
        "cultural_practices": [],
    }

    # Implementation will be added
    return indicators


def sanitize_input(user_input: str) -> str:
    """
    Sanitize user input for security
    """
    # Basic sanitization
    sanitized = user_input.strip()

    # Remove potentially harmful characters
    dangerous_chars = ["<", ">", "&", '"', "'", "\\", "/", "%"]
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")

    return sanitized


def format_error_response(
    error: Exception, include_details: bool = False
) -> Dict[str, Any]:
    """
    Format error response consistently
    """
    response = {
        "error": True,
        "message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if include_details:
        response["details"] = {
            "error_type": type(error).__name__,
            "traceback": str(error.__traceback__),
        }

    return response
