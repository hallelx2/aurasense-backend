"""
Auth API Routes
Handles user registration and authentication
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Any
from src.app.models.user import User
from src.app.core.security import security_manager
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

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user(request: RegisterRequest):
    # Check if user exists
    if User.nodes.filter(email=request.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if request.username and User.nodes.filter(username=request.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    # Hash password
    password_hash = security_manager.hash_password(request.password)
    # Create user
    user = User(
        email=request.email,
        password_hash=password_hash,
        first_name=request.first_name,
        last_name=request.last_name,
        username=request.username
    ).save()
    # Generate JWT
    token = security_manager.create_access_token({"sub": user.uid, "email": user.email})
    return AuthResponse(
        status="success",
        message="User registered successfully",
        data={
            "user": {
                "uid": user.uid,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            },
            "access_token": token
        }
    )

@router.post("/login", response_model=AuthResponse)
async def login_user(request: LoginRequest):
    user = User.nodes.filter(email=request.email).first()
    if not user or not security_manager.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = security_manager.create_access_token({"sub": user.uid, "email": user.email})
    return AuthResponse(
        status="success",
        message="Login successful",
        data={
            "user": {
                "uid": user.uid,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            },
            "access_token": token
        }
    )

@router.post("/logout", response_model=AuthResponse)
async def logout_user(Authorization: str = Header(...)):
    """
    Invalidate the current JWT by blacklisting it in Redis until its expiry.
    """
    token = Authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        if not exp:
            raise HTTPException(status_code=400, detail="Invalid token: no expiry")
        ttl = int(exp - datetime.utcnow().timestamp())
        if ttl > 0:
            await redis_cache.redis_client.setex(f"blacklist:{token}", ttl, "1")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token already expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return AuthResponse(
        status="success",
        message="Logged out successfully",
        data={}
    )
