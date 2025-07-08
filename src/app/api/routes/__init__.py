"""
API Routes Package
All API route definitions
"""

from .voice import router as voice_router
from .onboarding import router as onboarding_router
from .food import router as food_router
from .travel import router as travel_router
from .social import router as social_router
from .auth import router as auth_router
from .onboarding_ws import router as onboarding_ws_router

__all__ = [
    "auth_router",
    "voice_router",
    "onboarding_router",
    "food_router",
    "travel_router",
    "social_router",
]
