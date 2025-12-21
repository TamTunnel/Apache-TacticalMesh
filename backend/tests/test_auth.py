# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Authentication API tests for Apache TacticalMesh.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user):
    """Test successful login."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "testadmin",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user):
    """Test login with wrong password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "testadmin",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "nonexistent",
            "password": "password123"
        }
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_user_requires_admin(client: AsyncClient, operator_token: str):
    """Test that user registration requires admin role."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "password": "newpassword123",
            "role": "observer"
        },
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_user_as_admin(client: AsyncClient, admin_token: str):
    """Test user registration as admin."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newoperator",
            "email": "newoperator@test.com",
            "password": "newpassword123",
            "role": "operator"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newoperator"
    assert data["role"] == "operator"
