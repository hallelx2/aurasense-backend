"""
Authentication Dependencies
FastAPI dependency injection for authentication
"""

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.app.core.database import run_in_thread
from src.app.core.security import security_manager
from src.app.models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer()


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _resolve_user_from_token(token: str) -> User:
    """Verify a JWT and load the matching User from Neo4j (off the event loop).

    `neomodel` is sync; we push the lookup into a thread so a slow Neo4j
    response doesn't stall every other in-flight async request on the
    same worker.
    """
    payload = await security_manager.verify_token(token)
    if not payload:
        raise _unauthorized()

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized()

    user = await run_in_thread(User.nodes.filter(uid=user_id).first)
    if not user:
        raise _unauthorized("User not found")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    token = credentials.credentials
    user = await _resolve_user_from_token(token)
    # Stash the token on the user object so /logout can blacklist it.
    user._current_token = token
    return user


async def get_current_user_with_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Tuple[User, str]:
    """Same as `get_current_user` but also returns the raw token."""
    token = credentials.credentials
    user = await _resolve_user_from_token(token)
    return user, token


async def get_current_session(session_id: str) -> Dict[str, Any]:
    """
    Get current user session
    """
    # Implementation will be added
    pass


async def verify_voice_authentication(audio_data: bytes, user_id: str) -> bool:
    """
    Verify voice authentication
    """
    # Implementation will be added
    pass


class AuthenticationRequired:
    """
    Authentication dependency class
    """

    def __init__(self, require_voice_auth: bool = False):
        self.require_voice_auth = require_voice_auth

    async def __call__(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Dict[str, Any]:
        """
        Authenticate user with optional voice verification
        """
        # Implementation will be added
        pass
