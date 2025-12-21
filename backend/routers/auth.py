# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Authentication router for Apache TacticalMesh.

Provides login and user management endpoints.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    authenticate_user,
    create_access_token,
    create_audit_log,
    get_password_hash,
    require_admin,
)
from ..config import get_settings
from ..database import get_db
from ..models import User, UserRole
from ..schemas import (
    LoginRequest,
    Token,
    UserCreate,
    UserResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Authenticate user and return JWT token.
    
    - **username**: User's username
    - **password**: User's password
    
    Returns a JWT token for subsequent authenticated requests.
    """
    user = await authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        await create_audit_log(
            db,
            user=None,
            action="login_failed",
            details={"username": login_data.username},
            success=False,
            error_message="Invalid credentials",
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.flush()
    
    # Create token
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": str(user.id),
            "role": user.role.value
        },
        expires_delta=expires_delta
    )
    
    await create_audit_log(
        db,
        user=user,
        action="login_success",
        resource_type="user",
        resource_id=str(user.id),
        request=request
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role=user.role
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> UserResponse:
    """
    Register a new user (admin only).
    
    - **username**: Unique username
    - **email**: Optional email address
    - **password**: Password (min 8 characters)
    - **role**: User role (admin, operator, observer)
    
    Only administrators can create new users.
    """
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role
    )
    
    db.add(new_user)
    await db.flush()
    
    await create_audit_log(
        db,
        user=current_user,
        action="user_created",
        resource_type="user",
        resource_id=str(new_user.id),
        details={"username": new_user.username, "role": new_user.role.value},
        request=request
    )
    
    logger.info(f"User created: {new_user.username} by {current_user.username}")
    
    return UserResponse.model_validate(new_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> list[UserResponse]:
    """
    List all users (admin only).
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(require_admin.__wrapped__(UserRole.ADMIN, UserRole.OPERATOR, UserRole.OBSERVER))
) -> UserResponse:
    """
    Get current user information.
    """
    return UserResponse.model_validate(current_user)
