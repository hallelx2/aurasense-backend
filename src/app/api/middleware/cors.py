"""
CORS Middleware
Cross-origin resource sharing configuration
"""

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def add_cors_middleware(app):
    """
    Add CORS middleware to FastAPI app
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"]
    )


class CustomCORSMiddleware:
    """
    Custom CORS middleware for advanced configuration
    """

    def __init__(self, app, allowed_origins: list = None):
        self.app = app
        self.allowed_origins = allowed_origins or ["*"]

    async def __call__(self, scope, receive, send):
        """
        Process CORS for requests
        """
        # Implementation will be added
        pass
