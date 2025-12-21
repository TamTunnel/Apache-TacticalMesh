# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Commands router for Apache TacticalMesh.

Provides command creation, listing, and status endpoints.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_audit_log, require_any_role, require_operator
from ..config import get_settings
from ..database import get_db
from ..models import Node, Command, CommandStatus, CommandType, User
from ..schemas import (
    CommandCreate,
    CommandResponse,
    CommandListResponse,
    CommandResultUpdate,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/commands", tags=["Commands"])


@router.post("", response_model=CommandResponse, status_code=status.HTTP_201_CREATED)
async def create_command(
    request: Request,
    command_data: CommandCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
) -> CommandResponse:
    """
    Create a new command for a target node (operator or admin only).
    
    - **target_node_id**: The node_id of the target node
    - **command_type**: Type of command (ping, reload_config, update_config, change_role, custom)
    - **payload**: Command-specific payload as JSON
    
    The command will be delivered to the node on its next heartbeat.
    """
    # Find target node
    result = await db.execute(
        select(Node).where(Node.node_id == command_data.target_node_id)
    )
    node = result.scalar_one_or_none()
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target node not found: {command_data.target_node_id}"
        )
    
    # Create command
    new_command = Command(
        command_type=command_data.command_type,
        status=CommandStatus.PENDING,
        target_node_id=node.id,
        payload=command_data.payload,
        created_by=current_user.id
    )
    
    db.add(new_command)
    await db.flush()
    
    await create_audit_log(
        db,
        user=current_user,
        action="command_created",
        resource_type="command",
        resource_id=str(new_command.id),
        details={
            "command_type": command_data.command_type.value,
            "target_node": command_data.target_node_id,
            "payload": command_data.payload
        },
        request=request
    )
    
    logger.info(
        f"Command created: {new_command.id} type={command_data.command_type.value} "
        f"target={command_data.target_node_id} by {current_user.username}"
    )
    
    return CommandResponse.model_validate(new_command)


@router.get("", response_model=CommandListResponse)
async def list_commands(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[CommandStatus] = None,
    command_type: Optional[CommandType] = None,
    target_node_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> CommandListResponse:
    """
    List commands with pagination and filtering.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **status_filter**: Filter by command status
    - **command_type**: Filter by command type
    - **target_node_id**: Filter by target node's node_id
    """
    # Build query
    query = select(Command)
    count_query = select(func.count(Command.id))
    
    if status_filter:
        query = query.where(Command.status == status_filter)
        count_query = count_query.where(Command.status == status_filter)
    
    if command_type:
        query = query.where(Command.command_type == command_type)
        count_query = count_query.where(Command.command_type == command_type)
    
    if target_node_id:
        # Join with Node to filter by node_id
        node_result = await db.execute(
            select(Node.id).where(Node.node_id == target_node_id)
        )
        node_uuid = node_result.scalar_one_or_none()
        if node_uuid:
            query = query.where(Command.target_node_id == node_uuid)
            count_query = count_query.where(Command.target_node_id == node_uuid)
    
    # Get total count
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get paginated results
    query = query.order_by(Command.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    commands = result.scalars().all()
    
    return CommandListResponse(
        commands=[CommandResponse.model_validate(c) for c in commands],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{command_id}", response_model=CommandResponse)
async def get_command(
    command_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> CommandResponse:
    """
    Get details of a specific command by ID.
    """
    result = await db.execute(
        select(Command).where(Command.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command not found: {command_id}"
        )
    
    return CommandResponse.model_validate(command)


@router.post("/{command_id}/result", response_model=CommandResponse)
async def update_command_result(
    command_id: UUID,
    result_data: CommandResultUpdate,
    db: AsyncSession = Depends(get_db)
) -> CommandResponse:
    """
    Update command result (called by node agent).
    
    - **command_id**: Command UUID
    - **status**: New command status
    - **result**: Command execution result as JSON
    - **error_message**: Error message if failed
    """
    result = await db.execute(
        select(Command).where(Command.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command not found: {command_id}"
        )
    
    # Update command
    command.status = result_data.status
    command.result = result_data.result
    command.error_message = result_data.error_message
    
    if result_data.status == CommandStatus.ACKNOWLEDGED:
        command.acknowledged_at = command.acknowledged_at or __import__('datetime').datetime.utcnow()
    elif result_data.status in [CommandStatus.COMPLETED, CommandStatus.FAILED]:
        command.completed_at = __import__('datetime').datetime.utcnow()
    
    await db.flush()
    
    logger.info(
        f"Command {command_id} result updated: status={result_data.status.value}"
    )
    
    return CommandResponse.model_validate(command)


@router.delete("/{command_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_command(
    request: Request,
    command_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Cancel a pending command (operator or admin only).
    
    Only commands in PENDING status can be cancelled.
    """
    result = await db.execute(
        select(Command).where(Command.id == command_id)
    )
    command = result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command not found: {command_id}"
        )
    
    if command.status != CommandStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel command in status: {command.status.value}"
        )
    
    await create_audit_log(
        db,
        user=current_user,
        action="command_cancelled",
        resource_type="command",
        resource_id=str(command.id),
        details={"command_type": command.command_type.value},
        request=request
    )
    
    await db.delete(command)
    await db.flush()
    
    logger.info(f"Command cancelled: {command_id} by {current_user.username}")
