# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Configuration router for Apache TacticalMesh.

Provides endpoints for managing global and per-node configuration.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_audit_log, require_any_role, require_operator
from ..database import get_db
from ..models import Configuration, Node, User
from ..schemas import (
    ConfigItem,
    ConfigResponse,
    ConfigListResponse,
    ConfigUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])


@router.get("", response_model=ConfigListResponse)
async def list_configs(
    scope: Optional[str] = Query(None, description="Filter by scope (global, node)"),
    node_id: Optional[str] = Query(None, description="Filter by node_id for node-scoped configs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> ConfigListResponse:
    """
    List configuration items with optional filtering.
    
    - **scope**: Filter by configuration scope (global, node)
    - **node_id**: Filter by node_id for node-scoped configurations
    """
    query = select(Configuration)
    count_query = select(func.count(Configuration.id))
    
    if scope:
        query = query.where(Configuration.scope == scope)
        count_query = count_query.where(Configuration.scope == scope)
    
    if node_id:
        # Get node UUID
        node_result = await db.execute(
            select(Node.id).where(Node.node_id == node_id)
        )
        node_uuid = node_result.scalar_one_or_none()
        if node_uuid:
            query = query.where(Configuration.node_id == node_uuid)
            count_query = count_query.where(Configuration.node_id == node_uuid)
    
    # Get total count
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Get results
    result = await db.execute(query.order_by(Configuration.key))
    configs = result.scalars().all()
    
    return ConfigListResponse(
        configs=[ConfigResponse.model_validate(c) for c in configs],
        total=total
    )


@router.get("/{key}", response_model=ConfigResponse)
async def get_config(
    key: str,
    node_id: Optional[str] = Query(None, description="Node ID for node-scoped config"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any_role)
) -> ConfigResponse:
    """
    Get a specific configuration item by key.
    
    - **key**: Configuration key
    - **node_id**: Optional node_id for node-scoped configuration
    """
    query = select(Configuration).where(Configuration.key == key)
    
    if node_id:
        node_result = await db.execute(
            select(Node.id).where(Node.node_id == node_id)
        )
        node_uuid = node_result.scalar_one_or_none()
        if node_uuid:
            query = query.where(Configuration.node_id == node_uuid)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node not found: {node_id}"
            )
    else:
        query = query.where(Configuration.scope == "global")
    
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {key}"
        )
    
    return ConfigResponse.model_validate(config)


@router.put("/{key}", response_model=ConfigResponse)
async def upsert_config(
    request: Request,
    key: str,
    config_data: ConfigItem,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
) -> ConfigResponse:
    """
    Create or update a configuration item (operator or admin only).
    
    - **key**: Configuration key
    - **value**: Configuration value (any JSON-serializable value)
    - **scope**: Configuration scope (global or node)
    - **node_id**: Node ID if scope is node
    - **description**: Human-readable description
    """
    node_uuid = None
    if config_data.node_id:
        node_result = await db.execute(
            select(Node.id).where(Node.node_id == config_data.node_id)
        )
        node_uuid = node_result.scalar_one_or_none()
        if not node_uuid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node not found: {config_data.node_id}"
            )
    
    # Check if config exists
    query = select(Configuration).where(Configuration.key == key)
    if node_uuid:
        query = query.where(Configuration.node_id == node_uuid)
    else:
        query = query.where(Configuration.scope == "global")
    
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if config:
        # Update existing
        old_value = config.value
        config.value = config_data.value
        config.description = config_data.description or config.description
        
        await create_audit_log(
            db,
            user=current_user,
            action="config_updated",
            resource_type="config",
            resource_id=str(config.id),
            details={
                "key": key,
                "old_value": old_value,
                "new_value": config_data.value
            },
            request=request
        )
        
        logger.info(f"Config updated: {key} by {current_user.username}")
    else:
        # Create new
        config = Configuration(
            key=key,
            value=config_data.value,
            scope=config_data.scope,
            node_id=node_uuid,
            description=config_data.description
        )
        db.add(config)
        
        await create_audit_log(
            db,
            user=current_user,
            action="config_created",
            resource_type="config",
            resource_id=key,
            details={
                "key": key,
                "value": config_data.value,
                "scope": config_data.scope
            },
            request=request
        )
        
        logger.info(f"Config created: {key} by {current_user.username}")
    
    await db.flush()
    
    return ConfigResponse.model_validate(config)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    request: Request,
    key: str,
    node_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """
    Delete a configuration item (operator or admin only).
    
    - **key**: Configuration key to delete
    - **node_id**: Node ID for node-scoped config
    """
    query = select(Configuration).where(Configuration.key == key)
    
    if node_id:
        node_result = await db.execute(
            select(Node.id).where(Node.node_id == node_id)
        )
        node_uuid = node_result.scalar_one_or_none()
        if node_uuid:
            query = query.where(Configuration.node_id == node_uuid)
    else:
        query = query.where(Configuration.scope == "global")
    
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration not found: {key}"
        )
    
    await create_audit_log(
        db,
        user=current_user,
        action="config_deleted",
        resource_type="config",
        resource_id=str(config.id),
        details={"key": key},
        request=request
    )
    
    await db.delete(config)
    await db.flush()
    
    logger.info(f"Config deleted: {key} by {current_user.username}")
