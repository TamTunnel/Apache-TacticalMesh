# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Pydantic schemas for Apache TacticalMesh Mesh Controller.

Defines request/response models for API validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr

from .models import UserRole, NodeStatus, CommandStatus, CommandType


# =============================================================================
# Base Schemas
# =============================================================================

class BaseResponse(BaseModel):
    """Base response with common fields."""
    success: bool = True
    message: Optional[str] = None


# =============================================================================
# Authentication Schemas
# =============================================================================

class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: UserRole
    requires_password_change: bool = False


class TokenData(BaseModel):
    """Data extracted from JWT token."""
    username: Optional[str] = None
    user_id: Optional[UUID] = None
    role: Optional[UserRole] = None


class LoginRequest(BaseModel):
    """Login request payload."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)


class UserCreate(BaseModel):
    """User creation request (admin only)."""
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.OBSERVER


class UserResponse(BaseModel):
    """User response model."""
    id: UUID
    username: str
    email: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# =============================================================================
# Node Schemas
# =============================================================================

class NodeRegisterRequest(BaseModel):
    """Node registration request."""
    node_id: str = Field(..., min_length=1, max_length=100, description="Unique node identifier")
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    node_type: Optional[str] = Field(None, max_length=50)
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    node_metadata: Optional[Dict[str, Any]] = None


class NodeRegisterResponse(BaseModel):
    """Node registration response."""
    id: UUID
    node_id: str
    auth_token: str
    message: str = "Node registered successfully"


class HeartbeatRequest(BaseModel):
    """Node heartbeat request with telemetry."""
    node_id: str
    cpu_usage: Optional[float] = Field(None, ge=0, le=100)
    memory_usage: Optional[float] = Field(None, ge=0, le=100)
    disk_usage: Optional[float] = Field(None, ge=0, le=100)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude: Optional[float] = None
    custom_metrics: Optional[Dict[str, Any]] = None


class HeartbeatResponse(BaseModel):
    """Heartbeat response with pending commands."""
    acknowledged: bool = True
    server_time: datetime
    pending_commands: List["CommandBrief"] = []


class NodeResponse(BaseModel):
    """Node information response."""
    id: UUID
    node_id: str
    name: Optional[str]
    description: Optional[str]
    node_type: Optional[str]
    status: NodeStatus
    last_heartbeat: Optional[datetime]
    cpu_usage: Optional[float]
    memory_usage: Optional[float]
    disk_usage: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]
    ip_address: Optional[str]
    node_metadata: Optional[Dict[str, Any]]
    registered_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeListResponse(BaseModel):
    """Paginated node list response."""
    nodes: List[NodeResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Command Schemas
# =============================================================================

class CommandCreate(BaseModel):
    """Command creation request."""
    target_node_id: str = Field(..., description="Target node's node_id")
    command_type: CommandType
    payload: Optional[Dict[str, Any]] = None


class CommandBrief(BaseModel):
    """Brief command info for heartbeat responses."""
    id: UUID
    command_type: CommandType
    payload: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class CommandResponse(BaseModel):
    """Full command response."""
    id: UUID
    command_type: CommandType
    status: CommandStatus
    target_node_id: UUID
    payload: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    sent_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CommandResultUpdate(BaseModel):
    """Command result update from node."""
    command_id: UUID
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class CommandListResponse(BaseModel):
    """Paginated command list response."""
    commands: List[CommandResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Configuration Schemas
# =============================================================================

class ConfigItem(BaseModel):
    """Configuration item."""
    key: str
    value: Any
    scope: str = "global"
    node_id: Optional[str] = None
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    """Configuration response."""
    id: UUID
    key: str
    value: Any
    scope: str
    node_id: Optional[UUID]
    description: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class ConfigListResponse(BaseModel):
    """Configuration list response."""
    configs: List[ConfigResponse]
    total: int


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    value: Any
    description: Optional[str] = None


# =============================================================================
# Audit Log Schemas
# =============================================================================

class AuditLogResponse(BaseModel):
    """Audit log entry response."""
    id: UUID
    user_id: Optional[UUID]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Audit log list response."""
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Health Check
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    timestamp: datetime


# Forward reference updates
HeartbeatResponse.model_rebuild()
