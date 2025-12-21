# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Configuration module for Apache TacticalMesh Node Agent.

Handles loading and validation of agent configuration from YAML files.
"""

import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, validator


class ControllerConfig(BaseModel):
    """Controller connection configuration."""
    primary_url: str = Field(..., description="Primary controller URL")
    backup_urls: List[str] = Field(default=[], description="Backup controller URLs")
    timeout_seconds: int = Field(default=30, description="Request timeout")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")


class AgentConfig(BaseModel):
    """Agent configuration model."""
    
    # Node identification
    node_id: str = Field(..., min_length=1, max_length=100, description="Unique node identifier")
    name: Optional[str] = Field(None, max_length=255, description="Human-readable node name")
    node_type: Optional[str] = Field(None, description="Node type (vehicle, sensor, etc.)")
    
    # Controller connection
    controller: ControllerConfig
    
    # Authentication
    auth_token: Optional[str] = Field(None, description="Pre-configured auth token")
    
    # Heartbeat settings
    heartbeat_interval_seconds: int = Field(
        default=30, 
        ge=5, 
        le=300,
        description="Heartbeat interval in seconds"
    )
    
    # Command polling
    command_poll_interval_seconds: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Command polling interval"
    )
    
    # Retry settings
    max_retries: int = Field(default=5, ge=1, le=20)
    retry_backoff_base: float = Field(default=2.0, ge=1.0, le=5.0)
    retry_backoff_max: int = Field(default=300, description="Max retry backoff in seconds")
    
    # Logging
    log_level: str = Field(default="INFO")
    log_file: Optional[str] = Field(None, description="Log file path")
    
    # Local storage
    data_dir: str = Field(default="./data", description="Local data directory")
    buffer_commands: bool = Field(default=True, description="Buffer unexecuted commands locally")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of {valid_levels}')
        return v.upper()


def load_config(config_path: str) -> AgentConfig:
    """
    Load agent configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Validated AgentConfig instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    # Support environment variable substitution
    raw_config = _substitute_env_vars(raw_config)
    
    return AgentConfig(**raw_config)


def _substitute_env_vars(obj):
    """Recursively substitute environment variables in config values."""
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Support ${VAR} and ${VAR:-default} syntax
        if obj.startswith('${') and obj.endswith('}'):
            var_spec = obj[2:-1]
            if ':-' in var_spec:
                var_name, default = var_spec.split(':-', 1)
                return os.environ.get(var_name, default)
            else:
                return os.environ.get(var_spec, obj)
        return obj
    else:
        return obj


def create_default_config(config_path: str, node_id: str, controller_url: str):
    """
    Create a default configuration file.
    
    Args:
        config_path: Path to write the configuration
        node_id: Unique node identifier
        controller_url: Controller URL
    """
    default_config = {
        'node_id': node_id,
        'name': f'Node {node_id}',
        'node_type': 'generic',
        'controller': {
            'primary_url': controller_url,
            'backup_urls': [],
            'timeout_seconds': 30,
            'verify_ssl': True
        },
        'auth_token': None,
        'heartbeat_interval_seconds': 30,
        'command_poll_interval_seconds': 10,
        'max_retries': 5,
        'retry_backoff_base': 2.0,
        'retry_backoff_max': 300,
        'log_level': 'INFO',
        'log_file': None,
        'data_dir': './data',
        'buffer_commands': True
    }
    
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    return path
