"""
Security Configuration.

Authentication, authorization, and security utilities. Passwords are hashed
with Argon2 (via `argon2-cffi`). JWTs use PyJWT. Logged-out tokens are
blacklisted in Redis with a TTL equal to the token's remaining lifetime.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from src.app.core.config import settings
from src.app.core.database import redis_cache

logger = logging.getLogger(__name__)

# Argon2 is the only password hasher in use. The legacy bcrypt context that
# used to live here was never called and has been removed.
argon2_hasher = PasswordHasher()


class SecurityManager:
    """
    Security operations manager.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("security")
        self.jwt_secret = settings.SECRET_KEY
        self.jwt_algorithm = settings.ALGORITHM

    # ------------------------------------------------------------ JWT

    def create_access_token(
        self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a signed JWT."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta
            or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.jwt_algorithm)

    async def is_token_blacklisted(self, token: str) -> bool:
        """
        Check the Redis blacklist for `token`.

        Behavior on Redis errors:
          - In production we **fail closed** (return True / treat as blacklisted)
            because letting logged-out tokens work during a Redis outage is
            worse than briefly rejecting valid sessions.
          - In development we fail open so engineers aren't blocked when Redis
            is down locally.
        """
        if not redis_cache.redis_client:
            if settings.is_production:
                self.logger.error(
                    "Redis unavailable; failing CLOSED on blacklist check (prod)."
                )
                return True
            return False

        try:
            result = await redis_cache.get(f"blacklist:{token}")
            return result is not None
        except Exception:  # broad on purpose: any Redis-side fault
            self.logger.exception("Redis blacklist check failed")
            return settings.is_production  # closed in prod, open in dev

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a JWT and confirm it has not been blacklisted."""
        if await self.is_token_blacklisted(token):
            self.logger.warning("Token is blacklisted (logged out)")
            return None
        try:
            return jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None

    # ------------------------------------------------------- Passwords

    def hash_password(self, password: str) -> str:
        """Hash password using Argon2."""
        return argon2_hasher.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against an Argon2 hash."""
        try:
            return argon2_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception:
            self.logger.exception("Argon2 verify raised unexpectedly")
            return False

    # --------------------------------------------- Voice biometrics stubs

    def generate_challenge_sentence(self) -> str:
        """Generate a random sentence for voice authentication.

        Voice biometrics are out of scope for the current phase; this returns
        a placeholder and will be implemented when speaker verification ships.
        """
        raise NotImplementedError("voice biometrics not implemented in this phase")

    def calculate_audio_hash(self, audio_data: bytes) -> str:
        """Hash audio bytes for replay-attack detection.

        Stubbed pending the voice biometrics phase.
        """
        raise NotImplementedError("voice biometrics not implemented in this phase")


# Global security instance
security_manager = SecurityManager()
