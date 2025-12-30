# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Dependency injection module for TacticalMesh.

Provides centralized dependencies for database sessions, authentication,
and role-based access control across all routers.
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session_maker
from .auth import decode_token, get_current_user, get_current_active_user
from .models import User, UserRole


# Re-export security scheme for use in routers
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    Yields an async session and ensures proper cleanup via context manager.
    The session auto-commits on successful exit or rolls back on exception.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory for role-based access control.
    
    Creates a dependency that validates the current user has one of the
    specified roles. Used to protect endpoints by role.
    
    Args:
        allowed_roles: One or more UserRole values that are permitted access
        
    Returns:
        A dependency function that returns the authenticated User if authorized
        
    Raises:
        HTTPException: 403 if user's role is not in allowed_roles
        
    Example:
        @router.post("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not authorized for this action. "
                       f"Required: {', '.join(r.value for r in allowed_roles)}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for common role combinations

# Admin-only access (user management, system configuration)
require_admin = require_role(UserRole.ADMIN)

# Operator access (command creation, node management)
require_operator = require_role(UserRole.ADMIN, UserRole.OPERATOR)

# Any authenticated user (read access)
require_any_role = require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.OBSERVER)


# Type aliases for cleaner endpoint signatures
DBSession = AsyncSession
AuthenticatedUser = User
