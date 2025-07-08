"""
Authentication Dependencies
FastAPI dependency injection for authentication
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import logging
from src.app.core.security import security_manager
from src.app.models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Get current authenticated user from token
    """
    token = credentials.credentials
    payload = await security_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = User.nodes.filter(uid=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Store token in user object for logout functionality
    user._current_token = token
    return user


async def get_current_user_with_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> tuple[User, str]:
    """
    Get current authenticated user with the token
    """
    token = credentials.credentials
    payload = await security_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = User.nodes.filter(uid=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
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
