# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Nodes router for Apache TacticalMesh.

Provides node registration, heartbeat, and query endpoints.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_audit_log, require_any_role, require_operator
from ..config import get_settings
from ..database import get_db
from ..models import Node, NodeStatus, Command, CommandStatus, TelemetryRecord, User
from ..schemas import (
    NodeRegisterRequest,
    NodeRegisterResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    NodeResponse,
    NodeListResponse,
    CommandBrief,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/nodes", tags=["Nodes"])


def generate_auth_token() -> str:
    """Generate a secure authentication token for a node."""
    return secrets.token_urlsafe(32)


@router.post("/register", response_model=NodeRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_node(
    request: Request,
    node_data: NodeRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> NodeRegisterResponse:
    """
    Register a new mesh node.
    
    - **node_id**: Unique identifier for this node
    - **name**: Human-readable name (optional)
    - **description**: Node description (optional)
    - **node_type**: Type of node (vehicle, dismounted, sensor, uas, etc.)
    - **ip_address**: Node's IP address
    - **mac_address**: Node's MAC address
    - **metadata**: Additional metadata as JSON
    
    Returns an authentication token for the node to use in subsequent requests.
    """
    # Check if node already exists
    result = await db.execute(
        select(Node).where(Node.node_id == node_data.node_id)
    )
    existing_node = result.scalar_one_or_none()
    
    if existing_node:
        # Re-registration: update and return new token
        existing_node.name = node_data.name or existing_node.name
        existing_node.description = node_data.description or existing_node.description
        existing_node.node_type = node_data.node_type or existing_node.node_type
        existing_node.ip_address = node_data.ip_address or existing_node.ip_address
        existing_node.mac_address = node_data.mac_address or existing_node.mac_address
        existing_node.metadata = node_data.metadata or existing_node.metadata
        existing_node.auth_token = generate_auth_token()
        existing_node.status = NodeStatus.ONLINE
        existing_node.last_heartbeat = datetime.utcnow()
        existing_node.updated_at = datetime.utcnow()
        
        await db.flush()
        
        logger.info(f"Node re-registered: {node_data.node_id}")
        
        return NodeRegisterResponse(
            id=existing_node.id,
            node_id=existing_node.node_id,
            auth_token=existing_node.auth_token,
            message="Node re-registered successfully"
        )
    
    # Create new node
    auth_token = generate_auth_token()
    new_node = Node(
        node_id=node_data.node_id,
        name=node_data.name,
        description=node_data.description,
        node_type=node_data.node_type,
        ip_address=node_data.ip_address,
        mac_address=node_data.mac_address,
        metadata=node_data.metadata,
        auth_token=auth_token,
        status=NodeStatus.ONLINE,
        last_heartbeat=datetime.utcnow()
    )
    
    db.add(new_node)
    await db.flush()
    
    await create_audit_log(
        db,
        user=None,
        action="node_registered",
        resource_type="node",
        resource_id=str(new_node.id),
        details={"node_id": node_data.node_id, "node_type": node_data.node_type},
        request=request
    )
    
    logger.info(f"Node registered: {node_data.node_id} (type: {node_data.node_type})")
    
    return NodeRegisterResponse(
        id=new_node.id,
        node_id=new_node.node_id,
        auth_token=auth_token,
        message="Node registered successfully"
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def node_heartbeat(
    heartbeat: HeartbeatRequest,
    db: AsyncSession = Depends(get_db)
) -> HeartbeatResponse:
    """
    Process node heartbeat with telemetry data.
    
    - **node_id**: Node identifier
    - **cpu_usage**: CPU usage percentage (0-100)
    - **memory_usage**: Memory usage percentage (0-100)
    - **disk_usage**: Disk usage percentage (0-100)
    - **latitude/longitude/altitude**: GPS coordinates (optional)
    - **custom_metrics**: Additional metrics as JSON
    
    Returns acknowledgment and any pending commands for this node.
    """
    # Find node
    result = await db.execute(
        select(Node).where(Node.node_id == heartbeat.node_id)
    )
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node not found: {heartbeat.node_id}"
        )
    
    # Update node status and telemetry
    node.status = NodeStatus.ONLINE
    node.last_heartbeat = datetime.utcnow()
    node.cpu_usage = heartbeat.cpu_usage
    node.memory_usage = heartbeat.memory_usage
    node.disk_usage = heartbeat.disk_usage
    node.latitude = heartbeat.latitude
    node.longitude = heartbeat.longitude
    node.altitude = heartbeat.altitude
    node.updated_at = datetime.utcnow()
    
    # Store telemetry record
    telemetry = TelemetryRecord(
        node_id=node.id,
        cpu_usage=heartbeat.cpu_usage,
        memory_usage=heartbeat.memory_usage,
        disk_usage=heartbeat.disk_usage,
        latitude=heartbeat.latitude,
        longitude=heartbeat.longitude,
        altitude=heartbeat.altitude,
        custom_metrics=heartbeat.custom_metrics
    )
    db.add(telemetry)
    
    # Fetch pending commands for this node
    result = await db.execute(
        select(Command)
        .where(Command.target_node_id == node.id)
        .where(Command.status == CommandStatus.PENDING)
        .order_by(Command.created_at)
        .limit(10)
    )
    pending_commands = result.scalars().all()
    
    # Mark commands as sent
    command_briefs = []
    for cmd in pending_commands:
        cmd.status = CommandStatus.SENT
        cmd.sent_at = datetime.utcnow()
        command_briefs.append(CommandBrief.model_validate(cmd))
    
    await db.flush()
    
    return HeartbeatResponse(
        acknowledged=True,
        server_time=datetime.utcnow(),
        pending_commands=command_briefs
    )


@router.get("", response_model=NodeListResponse)
async def list_nodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[NodeStatus] = None,
    node_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> NodeListResponse:
    """
    List all registered nodes with pagination and filtering.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **status_filter**: Filter by node status
    - **node_type**: Filter by node type
    """
    # Update stale node statuses
    timeout = datetime.utcnow() - timedelta(seconds=settings.node_heartbeat_timeout_seconds)
    await db.execute(
        Node.__table__.update()
        .where(Node.last_heartbeat < timeout)
        .where(Node.status == NodeStatus.ONLINE)
        .values(status=NodeStatus.OFFLINE)
    )
    
    # Build query
    query = select(Node)
    count_query = select(func.count(Node.id))
    
    if status_filter:
        query = query.where(Node.status == status_filter)
        count_query = count_query.where(Node.status == status_filter)
    
    if node_type:
        query = query.where(Node.node_type == node_type)
        count_query = count_query.where(Node.node_type == node_type)
    
    # Get total count
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get paginated results
    query = query.order_by(Node.registered_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    nodes = result.scalars().all()
    
    return NodeListResponse(
        nodes=[NodeResponse.model_validate(n) for n in nodes],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> NodeResponse:
    """
    Get details of a specific node by node_id.
    """
    result = await db.execute(
        select(Node).where(Node.node_id == node_id)
    )
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node not found: {node_id}"
        )
    
    return NodeResponse.model_validate(node)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Delete a node (operator or admin only).
    """
    result = await db.execute(
        select(Node).where(Node.node_id == node_id)
    )
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node not found: {node_id}"
        )
    
    await create_audit_log(
        db,
        user=current_user,
        action="node_deleted",
        resource_type="node",
        resource_id=str(node.id),
        details={"node_id": node_id},
        request=request
    )
    
    await db.delete(node)
    await db.flush()
    
    logger.info(f"Node deleted: {node_id} by {current_user.username}")
