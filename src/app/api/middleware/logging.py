"""
Logging Middleware
Request/response logging for debugging and monitoring
"""

import logging
import time
from fastapi import Request, Response
from typing import Callable

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """
    Middleware for logging requests and responses
    """

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("middleware.logging")

    async def __call__(self, scope, receive, send):
        """
        Log request and response details
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Log request
        request = Request(scope, receive)
        self.logger.info(f"Request: {request.method} {request.url}")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                self.logger.info(f"Response: {message['status']} - {process_time:.3f}s")
            await send(message)

        await self.app(scope, receive, send_wrapper)
