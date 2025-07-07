"""
Security Configuration
Authentication, authorization, and security utilities
"""

from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from .config import settings
from argon2 import PasswordHasher
from src.app.core.database import redis_cache
import asyncio

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
argon2_hasher = PasswordHasher()


class SecurityManager:
    """
    Security operations manager
    """

    def __init__(self):
        self.logger = logging.getLogger("security")
        self.jwt_secret = settings.SECRET_KEY
        self.jwt_algorithm = settings.ALGORITHM

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token using PyJWT"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.jwt_secret, algorithm=self.jwt_algorithm)
        return encoded_jwt

    async def is_token_blacklisted(self, token: str) -> bool:
        if not redis_cache.redis_client:
            return False
        result = await redis_cache.redis_client.get(f"blacklist:{token}")
        return result is not None

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token using PyJWT and check blacklist in Redis"""
        if await self.is_token_blacklisted(token):
            self.logger.warning("Token is blacklisted (logged out)")
            return None
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None

    def hash_password(self, password: str) -> str:
        """Hash password using Argon2"""
        return argon2_hasher.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against Argon2 hash"""
        try:
            return argon2_hasher.verify(hashed_password, plain_password)
        except Exception:
            return False

    def generate_challenge_sentence(self) -> str:
        """Generate random sentence for voice authentication"""
        # Implementation will be added
        pass

    def calculate_audio_hash(self, audio_data: bytes) -> str:
        """Calculate hash of audio data"""
        # Implementation will be added
        pass


# Global security instance
security_manager = SecurityManager()
