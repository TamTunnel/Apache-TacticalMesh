# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Node API tests for Apache TacticalMesh.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_register_node(client: AsyncClient):
    """Test node registration."""
    response = await client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "test-node-001",
            "name": "Test Node 1",
            "node_type": "sensor",
            "ip_address": "192.168.1.100"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["node_id"] == "test-node-001"
    assert "auth_token" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_node_heartbeat(client: AsyncClient):
    """Test node heartbeat."""
    # First register a node
    reg_response = await client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "test-node-002",
            "name": "Test Node 2",
            "node_type": "vehicle"
        }
    )
    assert reg_response.status_code == 201
    
    # Send heartbeat
    hb_response = await client.post(
        "/api/v1/nodes/heartbeat",
        json={
            "node_id": "test-node-002",
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "disk_usage": 30.0,
            "latitude": 38.8977,
            "longitude": -77.0365
        }
    )
    assert hb_response.status_code == 200
    data = hb_response.json()
    assert data["acknowledged"] is True
    assert "server_time" in data


@pytest.mark.asyncio
async def test_list_nodes_requires_auth(client: AsyncClient):
    """Test that listing nodes requires authentication."""
    response = await client.get("/api/v1/nodes")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_nodes_with_auth(client: AsyncClient, admin_token: str):
    """Test listing nodes with authentication."""
    # Register a node first
    await client.post(
        "/api/v1/nodes/register",
        json={
            "node_id": "test-node-003",
            "name": "Test Node 3",
            "node_type": "uas"
        }
    )
    
    # List nodes with auth
    response = await client.get(
        "/api/v1/nodes",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "total" in data
    assert len(data["nodes"]) >= 1
