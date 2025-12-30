# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Audit logging module for TacticalMesh.

Provides structured audit logging for all significant operations,
supporting compliance requirements for defense and government deployments.
"""

import logging
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog, User
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def record_audit_event(
    db: AsyncSession,
    user: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None
) -> Optional[AuditLog]:
    """
    Record an audit event to the database.
    
    This function should be called for all significant operations including:
    - Authentication attempts (success and failure)
    - User management (create, modify, delete)
    - Node management (register, delete)
    - Command operations (create, cancel)
    - Configuration changes
    
    Args:
        db: Database session
        user: The user performing the action (None for anonymous/system actions)
        action: Description of the action taken (e.g., "node_registered", "command_created")
        target_type: Type of resource affected (e.g., "node", "command", "user", "config")
        target_id: Identifier of the affected resource
        metadata: Additional context as key-value pairs
        success: Whether the action succeeded
        error_message: Error description if action failed
        request: HTTP request object for extracting client info
        
    Returns:
        The created AuditLog entry, or None if audit logging is disabled
        
    Example:
        await record_audit_event(
            db=db,
            user=current_user,
            action="command_created",
            target_type="command",
            target_id=str(command.id),
            metadata={"command_type": command_type.value, "target_node": node_id}
        )
    """
    if not settings.audit_log_enabled:
        return None
    
    # Extract client information from request
    ip_address = None
    user_agent = None
    
    if request:
        # Safely get client IP, handling proxies
        ip_address = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else None)
        )
        user_agent = request.headers.get("user-agent", "")[:500]
    
    # Create audit log entry
    audit_log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        resource_type=target_type,
        resource_id=str(target_id) if target_id else None,
        details=metadata,
        success=success,
        error_message=error_message,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(audit_log)
    await db.flush()
    
    # Log to application logger as well for immediate visibility
    log_level = logging.INFO if success else logging.WARNING
    log_message = (
        f"AUDIT: user={user.username if user else 'system'} "
        f"action={action} "
        f"target={target_type}/{target_id} "
        f"success={success}"
    )
    if metadata:
        log_message += f" metadata={metadata}"
    if error_message:
        log_message += f" error={error_message}"
    
    logger.log(log_level, log_message)
    
    return audit_log


async def log_authentication_attempt(
    db: AsyncSession,
    username: str,
    success: bool,
    user: Optional[User] = None,
    error_message: Optional[str] = None,
    request: Optional[Request] = None
) -> Optional[AuditLog]:
    """
    Convenience function for logging authentication attempts.
    
    Args:
        db: Database session
        username: Username attempted
        success: Whether authentication succeeded
        user: User object if authentication succeeded
        error_message: Reason for failure if applicable
        request: HTTP request for client info
        
    Returns:
        Created AuditLog entry
    """
    action = "login_success" if success else "login_failed"
    return await record_audit_event(
        db=db,
        user=user,
        action=action,
        target_type="user",
        target_id=str(user.id) if user else None,
        metadata={"username": username},
        success=success,
        error_message=error_message,
        request=request
    )


async def log_resource_change(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str,
    changes: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> Optional[AuditLog]:
    """
    Convenience function for logging resource modifications.
    
    Args:
        db: Database session
        user: User making the change
        action: Action type (e.g., "created", "updated", "deleted")
        resource_type: Type of resource
        resource_id: Resource identifier
        changes: Dictionary describing what changed
        request: HTTP request for client info
        
    Returns:
        Created AuditLog entry
    """
    return await record_audit_event(
        db=db,
        user=user,
        action=f"{resource_type}_{action}",
        target_type=resource_type,
        target_id=resource_id,
        metadata=changes,
        success=True,
        request=request
    )
