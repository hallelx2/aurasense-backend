"""
Auth API Routes
Handles user registration and authentication
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any
from src.app.models.user import User
from src.app.core.security import security_manager
from src.app.api.dependencies.auth import get_current_user, get_current_user_with_token
from src.app.services.memory_service import memory_service
from neomodel import db
from src.app.core.database import redis_cache
import jwt
from src.app.core.config import settings
from datetime import datetime
import logging
import traceback
from neomodel.exceptions import DoesNotExist

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    username: str | None = None


class AuthResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(request: RegisterRequest, http_request: Request):
    try:
        logger.info(f"Registration attempt for email: {request.email}")

        # Check if user exists
        if User.nodes.filter(email=request.email).all():
            logger.warning(f"Registration failed: Email already exists: {request.email}")
            raise HTTPException(status_code=400, detail="Email already registered")

        if request.username and User.nodes.filter(username=request.username).all():
            logger.warning(f"Registration failed: Username already taken: {request.username}")
            raise HTTPException(status_code=400, detail="Username already taken")

        # Hash password
        password_hash = security_manager.hash_password(request.password)

        # Create user
        user = User(
            email=request.email,
            password_hash=password_hash,
            first_name=request.first_name,
            last_name=request.last_name,
            username=request.username,
            is_onboarded=False,  # Explicitly set onboarding status
        ).save()

        # Generate JWT
        token = security_manager.create_access_token({"sub": user.uid, "email": user.email})

        # Store registration in memory
        await memory_service.store_user_registration(user)

        logger.info(f"User registered successfully: {user.email}")

        return AuthResponse(
            status="success",
            message="User registered successfully",
            data={
                "user": {
                    "uid": user.uid,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "isOnboarded": getattr(user, "is_onboarded", False),
                },
                "access_token": token,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error for {request.email}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration"
        )


@router.post("/login", response_model=AuthResponse)
async def login_user(request: LoginRequest, http_request: Request):
    try:
        logger.info(f"Login attempt for email: {request.email}")

        try:
            user = User.nodes.filter(email=request.email).first()
            if not user:
                logger.warning(f"Login failed: User not found: {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
        except DoesNotExist:
            logger.warning(f"Login failed: User not found: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if not security_manager.verify_password(request.password, user.password_hash):
            logger.warning(f"Login failed: Invalid password for user: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        token = security_manager.create_access_token({"sub": user.uid, "email": user.email})

        # Store login in memory
        await memory_service.store_user_login(user)

        logger.info(f"User logged in successfully: {user.email}")

        return AuthResponse(
            status="success",
            message="Login successful",
            data={
                "user": {
                    "uid": user.uid,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "isOnboarded": getattr(user, "is_onboarded", False),
                },
                "access_token": token,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {request.email}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


@router.post("/logout", response_model=AuthResponse)
async def logout_user(
    http_request: Request,
    user_and_token: tuple[User, str] = Depends(get_current_user_with_token)
):
    """
    Invalidate the current JWT by blacklisting it in Redis until its expiry.
    """
    current_user, token = user_and_token

    try:
        logger.info(f"Logout attempt for user: {current_user.email}")

        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            exp = payload.get("exp")
            if not exp:
                logger.warning(f"Logout failed: Invalid token (no expiry) for user: {current_user.email}")
                raise HTTPException(status_code=400, detail="Invalid token: no expiry")

            ttl = int(exp - datetime.utcnow().timestamp())
            if ttl > 0:
                await redis_cache.set(f"blacklist:{token}", "1", ttl)

        except jwt.ExpiredSignatureError:
            logger.warning(f"Logout failed: Token expired for user: {current_user.email}")
            raise HTTPException(status_code=401, detail="Token already expired")
        except jwt.InvalidTokenError:
            logger.warning(f"Logout failed: Invalid token for user: {current_user.email}")
            raise HTTPException(status_code=401, detail="Invalid token")

        # Store logout in memory
        await memory_service.store_user_logout(current_user.uid)

        logger.info(f"User logged out successfully: {current_user.email}")

        return AuthResponse(
            status="success",
            message="Logged out successfully",
            data={"user_id": current_user.uid}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error for {current_user.email}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout"
        )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    http_request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    try:
        logger.info(f"Fetching user info for: {current_user.email}")

        return AuthResponse(
            status="success",
            message="User information retrieved",
            data={
                "user": {
                    "uid": current_user.uid,
                    "email": current_user.email,
                    "first_name": current_user.first_name,
                    "last_name": current_user.last_name,
                    "username": current_user.username,
                    "onboarding_completed": getattr(current_user, "is_onboarded", False),
                    "health_profile_verified": False,  # TODO: implement health profile verification
                    "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
                }
            },
        )
    except Exception as e:
        logger.error(f"Error fetching user info for {current_user.email}: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching user information"
        )
