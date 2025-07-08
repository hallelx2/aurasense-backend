"""
Auth API Routes
Handles user registration and authentication
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header
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
async def register_user(request: RegisterRequest):
    # Check if user exists
    if User.nodes.filter(email=request.email).all():
        raise HTTPException(status_code=400, detail="Email already registered")
    if request.username and User.nodes.filter(username=request.username).all():
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


@router.post("/login", response_model=AuthResponse)
async def login_user(request: LoginRequest):
    user = User.nodes.filter(email=request.email).first()
    if not user or not security_manager.verify_password(
        request.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = security_manager.create_access_token({"sub": user.uid, "email": user.email})
    
    # Store login in memory
    await memory_service.store_user_login(user)
    
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


@router.post("/logout", response_model=AuthResponse)
async def logout_user(user_and_token: tuple[User, str] = Depends(get_current_user_with_token)):
    """
    Invalidate the current JWT by blacklisting it in Redis until its expiry.
    """
    current_user, token = user_and_token
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        exp = payload.get("exp")
        if not exp:
            raise HTTPException(status_code=400, detail="Invalid token: no expiry")
        ttl = int(exp - datetime.utcnow().timestamp())
        if ttl > 0:
            await redis_cache.set(f"blacklist:{token}", "1", ttl)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token already expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Store logout in memory
    await memory_service.store_user_logout(current_user.uid)
    
    return AuthResponse(
        status="success", 
        message="Logged out successfully", 
        data={"user_id": current_user.uid}
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
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
