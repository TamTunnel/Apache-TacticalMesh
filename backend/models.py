# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
SQLAlchemy models for Apache TacticalMesh Mesh Controller.

Defines the database schema for nodes, commands, users, configurations,
and audit logs.
"""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    """User roles for access control."""
    ADMIN = "admin"
    OPERATOR = "operator"
    OBSERVER = "observer"


class NodeStatus(str, enum.Enum):
    """Node operational status."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CommandStatus(str, enum.Enum):
    """Command execution status."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CommandType(str, enum.Enum):
    """Built-in command types."""
    PING = "ping"
    RELOAD_CONFIG = "reload_config"
    UPDATE_CONFIG = "update_config"
    CHANGE_ROLE = "change_role"
    CUSTOM = "custom"


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.OBSERVER)
    is_active = Column(Boolean, default=True)
    
    # Security fields
    force_password_change = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
    commands = relationship("Command", back_populates="created_by_user")



class Node(Base):
    """Mesh node model representing edge devices."""
    
    __tablename__ = "nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    node_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    node_type = Column(String(50), nullable=True)  # vehicle, dismounted, sensor, uas, etc.
    
    # Status and health
    status = Column(Enum(NodeStatus), default=NodeStatus.UNKNOWN)
    last_heartbeat = Column(DateTime, nullable=True)
    
    # Telemetry
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    
    # Location (optional)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    
    # Network info
    ip_address = Column(String(45), nullable=True)
    mac_address = Column(String(17), nullable=True)
    
    # Authentication
    auth_token = Column(String(255), nullable=True)
    
    # Metadata
    node_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    registered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    commands = relationship("Command", back_populates="target_node")
    telemetry_records = relationship("TelemetryRecord", back_populates="node")


class Command(Base):
    """Command model for controller-to-node instructions."""
    
    __tablename__ = "commands"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    command_type = Column(Enum(CommandType), nullable=False)
    status = Column(Enum(CommandStatus), default=CommandStatus.PENDING)
    
    # Target
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    
    # Command details
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Creator
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    target_node = relationship("Node", back_populates="commands")
    created_by_user = relationship("User", back_populates="commands")


class TelemetryRecord(Base):
    """Time-series telemetry data from nodes."""
    
    __tablename__ = "telemetry_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    
    # Metrics
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    network_rx_bytes = Column(Integer, nullable=True)
    network_tx_bytes = Column(Integer, nullable=True)
    
    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    
    # Additional data
    custom_metrics = Column(JSON, nullable=True)
    
    # Timestamp
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    node = relationship("Node", back_populates="telemetry_records")


class Configuration(Base):
    """Configuration storage for global and per-node settings."""
    
    __tablename__ = "configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    key = Column(String(255), nullable=False, index=True)
    value = Column(JSON, nullable=True)
    scope = Column(String(50), default="global")  # global, node, etc.
    node_id = Column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Audit log for tracking operator actions."""
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Who
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=True)
    
    # What
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)  # node, command, config, user
    resource_id = Column(String(100), nullable=True)
    
    # Details
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # When
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
