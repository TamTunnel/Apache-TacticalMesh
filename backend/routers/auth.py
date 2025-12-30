# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Authentication router for TacticalMesh.

Provides login and user management endpoints with security controls:
- Rate limiting on login attempts
- Account lockout after failed attempts
- Password complexity enforcement
- Forced password change for default credentials
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
    require_any_role,
    get_current_active_user,
    verify_password,
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
from ..security import (
    limiter,
    PasswordValidator,
    lockout_manager,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
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
    
    Security controls:
    - Rate limited to 5 attempts per minute per IP
    - Account locks after 5 failed attempts for 15 minutes
    """
    # Check if account is locked out
    if lockout_manager.is_locked_out(login_data.username):
        remaining = lockout_manager.get_lockout_remaining(login_data.username)
        await create_audit_log(
            db,
            user=None,
            action="login_blocked_lockout",
            details={"username": login_data.username, "remaining_seconds": remaining},
            success=False,
            error_message="Account locked due to too many failed attempts",
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)}
        )
    
    user = await authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        # Record failed attempt and check for lockout
        is_now_locked = lockout_manager.record_failed_attempt(login_data.username)
        remaining_attempts = lockout_manager.get_remaining_attempts(login_data.username)
        
        await create_audit_log(
            db,
            user=None,
            action="login_failed",
            details={
                "username": login_data.username,
                "remaining_attempts": remaining_attempts,
                "now_locked": is_now_locked
            },
            success=False,
            error_message="Invalid credentials",
            request=request
        )
        
        if is_now_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account locked due to too many failed attempts. Try again in 15 minutes.",
                headers={"Retry-After": "900"}
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Incorrect username or password. {remaining_attempts} attempts remaining.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Clear failed attempts on successful login
    lockout_manager.clear_attempts(login_data.username)
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.flush()
    
    # Check if password change is required
    requires_password_change = user.force_password_change
    
    # Create token
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": str(user.id),
            "role": user.role.value,
            "requires_password_change": requires_password_change
        },
        expires_delta=expires_delta
    )
    
    await create_audit_log(
        db,
        user=user,
        action="login_success",
        resource_type="user",
        resource_id=str(user.id),
        details={"requires_password_change": requires_password_change},
        request=request
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role=user.role,
        requires_password_change=requires_password_change
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Change the current user's password.
    
    - **current_password**: Current password for verification
    - **new_password**: New password (must meet complexity requirements)
    
    Password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        await create_audit_log(
            db,
            user=current_user,
            action="password_change_failed",
            resource_type="user",
            resource_id=str(current_user.id),
            success=False,
            error_message="Current password verification failed",
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Validate new password complexity
    PasswordValidator.validate_or_raise(new_password)
    
    # Update password
    current_user.hashed_password = get_password_hash(new_password)
    current_user.force_password_change = False
    await db.flush()
    
    await create_audit_log(
        db,
        user=current_user,
        action="password_changed",
        resource_type="user",
        resource_id=str(current_user.id),
        request=request
    )
    
    logger.info(f"Password changed for user: {current_user.username}")
    
    return {"message": "Password changed successfully"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
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
    - **password**: Password (must meet complexity requirements)
    - **role**: User role (admin, operator, observer)
    
    Only administrators can create new users.
    """
    # Validate password complexity
    PasswordValidator.validate_or_raise(user_data.password)
    
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
    current_user: User = Depends(require_any_role)
) -> UserResponse:
    """
    Get current user information.
    """
    return UserResponse.model_validate(current_user)

