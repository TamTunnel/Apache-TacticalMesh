# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Test configuration and fixtures for Apache TacticalMesh backend tests.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.auth import get_password_hash, create_access_token
from backend.models import User, UserRole


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create test session factory
test_async_session = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Configure pytest-asyncio mode
# Note: pytest-asyncio will handle event loop creation automatically
pytest_plugins = ['pytest_asyncio']


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with test_async_session() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database dependency override."""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    user = User(
        username="testadmin",
        email="testadmin@test.com",
        hashed_password=get_password_hash("testpassword123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    """Create an admin JWT token for testing."""
    return create_access_token(
        data={
            "sub": admin_user.username,
            "user_id": str(admin_user.id),
            "role": admin_user.role.value
        }
    )


@pytest_asyncio.fixture
async def operator_user(db_session: AsyncSession) -> User:
    """Create an operator user for testing."""
    user = User(
        username="testoperator",
        email="testoperator@test.com",
        hashed_password=get_password_hash("testpassword123"),
        role=UserRole.OPERATOR,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def operator_token(operator_user: User) -> str:
    """Create an operator JWT token for testing."""
    return create_access_token(
        data={
            "sub": operator_user.username,
            "user_id": str(operator_user.id),
            "role": operator_user.role.value
        }
    )
