"""
Rate Limiting Middleware
Rate limiting for API endpoints
"""

import time
from typing import Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Rate limiting middleware
    """

    def __init__(self, app, requests_per_minute: int = 60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.clients = {}
        self.logger = logging.getLogger("middleware.rate_limit")

    async def __call__(self, scope, receive, send):
        """
        Check rate limits for requests
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        client_ip = request.client.host

        # Check rate limit
        if self.is_rate_limited(client_ip):
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def is_rate_limited(self, client_ip: str) -> bool:
        """
        Check if client is rate limited
        """
        current_time = time.time()

        if client_ip not in self.clients:
            self.clients[client_ip] = []

        # Clean old requests
        self.clients[client_ip] = [
            req_time
            for req_time in self.clients[client_ip]
            if current_time - req_time < 60  # 1 minute window
        ]

        # Check if over limit
        if len(self.clients[client_ip]) >= self.requests_per_minute:
            return True

        # Add current request
        self.clients[client_ip].append(current_time)
        return False
