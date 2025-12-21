# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Configuration module for Apache TacticalMesh Mesh Controller.

Handles environment-based configuration with sensible defaults for
development and production deployments.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application settings
    app_name: str = "Apache TacticalMesh Controller"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database settings
    database_url: str = Field(
        default="postgresql+asyncpg://tacticalmesh:tacticalmesh@localhost:5432/tacticalmesh",
        description="PostgreSQL connection URL"
    )
    
    # Redis settings (for transient data/caching)
    redis_url: Optional[str] = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and pub/sub"
    )
    
    # JWT Authentication settings
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET",
        description="Secret key for JWT token signing"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    
    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )
    
    # Node settings
    node_heartbeat_timeout_seconds: int = Field(
        default=60,
        description="Seconds after which a node is considered offline"
    )
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Audit logging
    audit_log_enabled: bool = True
    
    class Config:
        env_file = ".env"
        env_prefix = "TM_"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()
