"""
API Routes Package
All API route definitions
"""

from .voice import router as voice_router
from .food import router as food_router
from .travel import router as travel_router
from .social import router as social_router
from .auth import router as auth_router
from .onboarding_ws import router as onboarding_ws_router

# NOTE: the HTTP `routes/onboarding.py` route was removed in Phase 1 — it
# duplicated WS logic with worse code (inline 50-line prompt, manual
# `<think>` tag parsing). All onboarding now flows through the WebSocket
# at `routes/onboarding_ws.py`.

__all__ = [
    "auth_router",
    "voice_router",
    "food_router",
    "travel_router",
    "social_router",
    "onboarding_ws_router",
]
