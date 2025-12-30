# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Command actions module for TacticalMesh Node Agent.

Provides built-in command handlers and extensibility for custom actions.
"""

import json
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)


class CommandResult:
    """Result of a command execution."""
    
    def __init__(
        self,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.result = result or {}
        self.error = error
    
    @property
    def status(self) -> str:
        return "completed" if self.success else "failed"


class ActionHandler(ABC):
    """Abstract base class for command action handlers."""
    
    @abstractmethod
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        """
        Execute the action.
        
        Args:
            payload: Command-specific payload
            
        Returns:
            CommandResult with execution outcome
        """
        pass


class PingHandler(ActionHandler):
    """Handler for PING commands - simple connectivity test."""
    
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        logger.info("Executing PING command")
        return CommandResult(
            success=True,
            result={"message": "pong", "timestamp": __import__('datetime').datetime.utcnow().isoformat()}
        )


class ReloadConfigHandler(ActionHandler):
    """Handler for RELOAD_CONFIG commands."""
    
    def __init__(self, config_path: str, reload_callback=None):
        self.config_path = config_path
        self.reload_callback = reload_callback
    
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        logger.info("Executing RELOAD_CONFIG command")
        try:
            if self.reload_callback:
                self.reload_callback()
            return CommandResult(
                success=True,
                result={"message": "Configuration reloaded", "config_path": self.config_path}
            )
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return CommandResult(success=False, error=str(e))


class UpdateConfigHandler(ActionHandler):
    """Handler for UPDATE_CONFIG commands - update local config file."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
    
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        logger.info("Executing UPDATE_CONFIG command")
        
        if not payload:
            return CommandResult(success=False, error="No configuration payload provided")
        
        try:
            config_updates = payload.get("config", {})
            
            # Load existing config
            config_file = Path(self.config_path)
            if config_file.exists():
                import yaml
                with open(config_file, 'r') as f:
                    current_config = yaml.safe_load(f) or {}
            else:
                current_config = {}
            
            # Merge updates
            def deep_update(base: dict, updates: dict) -> dict:
                for key, value in updates.items():
                    if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                        deep_update(base[key], value)
                    else:
                        base[key] = value
                return base
            
            updated_config = deep_update(current_config, config_updates)
            
            # Write back
            import yaml
            with open(config_file, 'w') as f:
                yaml.dump(updated_config, f, default_flow_style=False)
            
            logger.info(f"Configuration updated: {list(config_updates.keys())}")
            return CommandResult(
                success=True,
                result={"message": "Configuration updated", "updated_keys": list(config_updates.keys())}
            )
            
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return CommandResult(success=False, error=str(e))


class ChangeRoleHandler(ActionHandler):
    """Handler for CHANGE_ROLE commands - change node operational role."""
    
    def __init__(self, role_callback=None):
        self.role_callback = role_callback
    
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        logger.info("Executing CHANGE_ROLE command")
        
        if not payload or "role" not in payload:
            return CommandResult(success=False, error="No role specified in payload")
        
        new_role = payload["role"]
        
        try:
            if self.role_callback:
                self.role_callback(new_role)
            
            logger.info(f"Role changed to: {new_role}")
            return CommandResult(
                success=True,
                result={"message": f"Role changed to {new_role}", "new_role": new_role}
            )
        except Exception as e:
            logger.error(f"Failed to change role: {e}")
            return CommandResult(success=False, error=str(e))


class CustomHandler(ActionHandler):
    """Handler for CUSTOM commands - execute user-defined actions."""
    
    def __init__(self, allowed_actions: Optional[Dict[str, str]] = None):
        """
        Initialize with allowed custom actions.
        
        Args:
            allowed_actions: Dict of action_name -> script_path
        """
        self.allowed_actions = allowed_actions or {}
    
    def execute(self, payload: Optional[Dict[str, Any]]) -> CommandResult:
        logger.info("Executing CUSTOM command")
        
        if not payload:
            return CommandResult(success=False, error="No payload provided for custom command")
        
        action_name = payload.get("action")
        action_params = payload.get("params", {})
        
        if not action_name:
            return CommandResult(success=False, error="No action specified")
        
        # Check if action is allowed
        if action_name not in self.allowed_actions:
            logger.warning(f"Unknown or disallowed custom action: {action_name}")
            return CommandResult(
                success=False,
                error=f"Action '{action_name}' is not allowed"
            )
        
        script_path = self.allowed_actions[action_name]
        
        try:
            # Execute the script with params as JSON
            result = subprocess.run(
                [script_path, json.dumps(action_params)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return CommandResult(
                    success=True,
                    result={
                        "action": action_name,
                        "stdout": result.stdout,
                        "returncode": result.returncode
                    }
                )
            else:
                return CommandResult(
                    success=False,
                    error=f"Script failed with code {result.returncode}: {result.stderr}"
                )
                
        except subprocess.TimeoutExpired:
            return CommandResult(success=False, error="Script execution timed out")
        except Exception as e:
            return CommandResult(success=False, error=str(e))


class ActionRegistry:
    """Registry for command action handlers."""
    
    def __init__(self):
        self._handlers: Dict[str, ActionHandler] = {}
    
    def register(self, command_type: str, handler: ActionHandler):
        """Register a handler for a command type."""
        self._handlers[command_type.lower()] = handler
        logger.debug(f"Registered handler for command type: {command_type}")
    
    def get_handler(self, command_type: str) -> Optional[ActionHandler]:
        """Get the handler for a command type."""
        return self._handlers.get(command_type.lower())
    
    def execute(
        self,
        command_type: str,
        payload: Optional[Dict[str, Any]]
    ) -> CommandResult:
        """
        Execute a command using the appropriate handler.
        
        Args:
            command_type: Type of command
            payload: Command payload
            
        Returns:
            CommandResult with execution outcome
        """
        handler = self.get_handler(command_type)
        
        if not handler:
            logger.warning(f"No handler registered for command type: {command_type}")
            return CommandResult(
                success=False,
                error=f"Unknown command type: {command_type}"
            )
        
        try:
            return handler.execute(payload)
        except Exception as e:
            logger.error(f"Error executing {command_type} command: {e}")
            return CommandResult(success=False, error=str(e))


def create_default_registry(config_path: str = "config.yaml") -> ActionRegistry:
    """
    Create an action registry with default handlers.
    
    Args:
        config_path: Path to agent config file
        
    Returns:
        Configured ActionRegistry
    """
    registry = ActionRegistry()
    
    registry.register("ping", PingHandler())
    registry.register("reload_config", ReloadConfigHandler(config_path))
    registry.register("update_config", UpdateConfigHandler(config_path))
    registry.register("change_role", ChangeRoleHandler())
    registry.register("custom", CustomHandler())
    
    return registry
