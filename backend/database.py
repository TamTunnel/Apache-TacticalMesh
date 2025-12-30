# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Database module for TacticalMesh Mesh Controller.

Provides async SQLAlchemy engine, session management, and base model.
Includes connection retry logic and pool monitoring for production resilience.
"""

import asyncio
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import OperationalError, InterfaceError
from sqlalchemy import event, text

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Connection retry configuration
MAX_CONNECTION_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# Create async engine with production settings
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,  # Verify connections before use
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_timeout=30,  # Wait up to 30s for connection from pool
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for SQLAlchemy models
Base = declarative_base()


def log_pool_status() -> None:
    """Log connection pool statistics for monitoring."""
    pool = engine.pool
    logger.info(
        f"DB Pool Status: size={pool.size()}, "
        f"checkedin={pool.checkedin()}, "
        f"checkedout={pool.checkedout()}, "
        f"overflow={pool.overflow()}"
    )


async def get_db_with_retry() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session with retry logic.
    
    Retries connection up to MAX_CONNECTION_RETRIES times if pool 
    exhaustion or connection errors occur.
    
    Yields:
        AsyncSession: Database session for request handling
        
    Raises:
        OperationalError: After all retries exhausted
    """
    last_exception = None
    
    for attempt in range(1, MAX_CONNECTION_RETRIES + 1):
        try:
            async with async_session_maker() as session:
                try:
                    yield session
                    await session.commit()
                    return
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
                    
        except (OperationalError, InterfaceError) as e:
            last_exception = e
            logger.warning(
                f"Database connection attempt {attempt}/{MAX_CONNECTION_RETRIES} failed: {e}"
            )
            log_pool_status()
            
            if attempt < MAX_CONNECTION_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    f"Database connection failed after {MAX_CONNECTION_RETRIES} attempts"
                )
                raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    Yields an async session and ensures proper cleanup.
    Uses retry logic for production resilience.
    """
    async for session in get_db_with_retry():
        yield session


async def init_db() -> None:
    """
    Initialize database tables with retry logic.
    
    Attempts to create tables, retrying on connection failures.
    """
    for attempt in range(1, MAX_CONNECTION_RETRIES + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully")
            return
        except (OperationalError, InterfaceError) as e:
            logger.warning(f"Database init attempt {attempt} failed: {e}")
            if attempt < MAX_CONNECTION_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error("Failed to initialize database after all retries")
                raise


async def close_db() -> None:
    """Close database connections and dispose of pool."""
    log_pool_status()
    await engine.dispose()
    logger.info("Database connections closed")


async def health_check() -> bool:
    """
    Perform database health check.
    
    Returns:
        True if database is responsive, False otherwise
    """
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
