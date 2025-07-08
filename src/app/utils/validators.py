"""
Validators
Input validation utilities
"""

import re
from typing import Dict, Any, Optional, Tuple
from email_validator import validate_email as email_validate, EmailNotValidError


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format
    """
    try:
        valid = email_validate(email)
        return True, valid.email
    except EmailNotValidError:
        return False, None


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format
    """
    # Simple phone validation - can be enhanced with phonenumbers library
    phone_pattern = re.compile(r"^\+?1?\d{9,15}$")
    return bool(phone_pattern.match(phone.replace(" ", "").replace("-", "")))


def validate_location(location: Dict[str, Any]) -> bool:
    """
    Validate location coordinates
    """
    if not isinstance(location, dict):
        return False

    if "latitude" not in location or "longitude" not in location:
        return False

    try:
        lat = float(location["latitude"])
        lon = float(location["longitude"])

        # Check valid coordinate ranges
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return True
    except (ValueError, TypeError):
        pass

    return False


def validate_audio_file(file_data: bytes) -> bool:
    """
    Validate audio file format and size
    """
    if not file_data:
        return False

    # Check file size (10MB limit)
    if len(file_data) > 10 * 1024 * 1024:
        return False

    # Basic audio format validation
    # Can be enhanced with proper audio format detection
    return True


def validate_user_input(user_input: str) -> bool:
    """
    Validate user text input
    """
    if not user_input or len(user_input.strip()) == 0:
        return False

    # Check for reasonable length
    if len(user_input) > 1000:
        return False

    return True
