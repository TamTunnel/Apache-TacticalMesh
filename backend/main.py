# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Apache TacticalMesh Mesh Controller - FastAPI Application

This is the main entry point for the Mesh Controller backend service.
It provides the central orchestration for tactical mesh networks.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .database import init_db, close_db, async_session_maker
from .models import User, UserRole
from .auth import get_password_hash
from .schemas import HealthResponse
from .routers import auth, nodes, commands, config
from .security import limiter

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format
)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    # Startup
    logger.info("Starting Apache TacticalMesh Controller...")
    await init_db()
    
    # Create default admin user if not exists
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        if not result.scalar_one_or_none():
            admin_user = User(
                username="admin",
                email="admin@tacticalmesh.local",
                hashed_password=get_password_hash("admin123"),  # Change in production!
                role=UserRole.ADMIN,
                is_active=True,
                force_password_change=True  # Security: Force password change on first login
            )
            session.add(admin_user)
            await session.commit()
            logger.warning("Created default admin user - PASSWORD CHANGE REQUIRED ON FIRST LOGIN")
    
    logger.info("Apache TacticalMesh Controller started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Apache TacticalMesh Controller...")
    await close_db()
    logger.info("Apache TacticalMesh Controller stopped")


# Create FastAPI application
app = FastAPI(
    title="Apache TacticalMesh Controller",
    description="""
## Apache TacticalMesh - Tactical Edge Networking Platform

The Mesh Controller is the central orchestration component for Apache TacticalMesh,
providing command and control for distributed mesh nodes in tactical environments.

### Features

- **Node Management**: Register, monitor, and manage edge nodes
- **Command & Control**: Dispatch commands to nodes and track execution
- **Telemetry**: Collect and store node health and status metrics
- **Configuration**: Manage global and per-node configuration
- **Authentication**: JWT-based authentication with role-based access control
- **Audit Logging**: Complete audit trail for operator actions

### Roles

- **Admin**: Full access to all operations including user management
- **Operator**: Can manage nodes, send commands, and update configuration
- **Observer**: Read-only access to node status and command history

### License

Apache License 2.0 - https://www.apache.org/licenses/LICENSE-2.0
    """,
    version=settings.app_version,
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    },
    lifespan=lifespan
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An internal error occurred",
            "detail": str(exc) if settings.debug else None
        }
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the current health status and version of the controller.
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow()
    )


# Include routers
app.include_router(auth.router)
app.include_router(nodes.router)
app.include_router(commands.router)
app.include_router(config.router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
