#!/usr/bin/env python3
# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Apache TacticalMesh Node Agent - Main Entry Point

This is the main entry point for the Node Agent, a lightweight service
that runs on edge nodes to communicate with the Mesh Controller.

Usage:
    python -m agent.main --config config.yaml
    python -m agent.main --config config.yaml --log-level DEBUG
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

from .config import load_config, create_default_config, AgentConfig
from .client import ControllerClient, CommandInfo
from .actions import create_default_registry, ActionRegistry

# Global flag for graceful shutdown
_shutdown_requested = False


def setup_logging(config: AgentConfig) -> logging.Logger:
    """Configure logging based on agent configuration."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=log_format,
        handlers=handlers
    )
    
    return logging.getLogger("tacticalmesh.agent")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    logging.getLogger("tacticalmesh.agent").info(
        f"Received signal {signum}, initiating graceful shutdown..."
    )


def get_system_metrics() -> dict:
    """Collect system metrics for telemetry."""
    try:
        return {
            "cpu_usage": psutil.cpu_percent(interval=0.1),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except Exception as e:
        logging.getLogger("tacticalmesh.agent").warning(f"Failed to collect metrics: {e}")
        return {}


def get_network_info() -> dict:
    """Get network interface information."""
    try:
        interfaces = psutil.net_if_addrs()
        for iface_name, addrs in interfaces.items():
            if iface_name == 'lo':
                continue
            for addr in addrs:
                if addr.family.name == 'AF_INET':
                    return {
                        "ip_address": addr.address,
                        "interface": iface_name
                    }
    except Exception as e:
        logging.getLogger("tacticalmesh.agent").warning(f"Failed to get network info: {e}")
    return {}


class NodeAgent:
    """
    Main Node Agent class.
    
    Handles the node lifecycle including registration, heartbeat,
    and command execution.
    """
    
    def __init__(self, config: AgentConfig, logger: logging.Logger):
        """
        Initialize the Node Agent.
        
        Args:
            config: Agent configuration
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.client = ControllerClient(config)
        self.action_registry = create_default_registry(config.data_dir)
        self.registered = False
        self.last_heartbeat: Optional[datetime] = None
    
    def register(self) -> bool:
        """
        Register this node with the controller.
        
        Returns:
            True if registration was successful
        """
        network_info = get_network_info()
        
        token = self.client.register(
            ip_address=network_info.get("ip_address"),
            metadata={
                "hostname": os.uname().nodename,
                "platform": sys.platform,
                "python_version": sys.version,
                "agent_version": "0.1.0"
            }
        )
        
        if token:
            self.registered = True
            self.logger.info(f"Successfully registered with controller")
            
            # Save token to data directory for persistence
            token_file = Path(self.config.data_dir) / ".auth_token"
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(token)
            
            return True
        
        return False
    
    def send_heartbeat(self) -> bool:
        """
        Send heartbeat with telemetry to the controller.
        
        Returns:
            True if heartbeat was acknowledged
        """
        metrics = get_system_metrics()
        
        pending_commands = self.client.heartbeat(
            cpu_usage=metrics.get("cpu_usage"),
            memory_usage=metrics.get("memory_usage"),
            disk_usage=metrics.get("disk_usage"),
            custom_metrics={
                "uptime": time.time() - psutil.boot_time()
            }
        )
        
        if pending_commands is None:
            self.logger.warning("Heartbeat failed - controller unreachable")
            return False
        
        self.last_heartbeat = datetime.utcnow()
        self.logger.debug(f"Heartbeat acknowledged, {len(pending_commands)} pending commands")
        
        # Process any pending commands
        for cmd in pending_commands:
            self._execute_command(cmd)
        
        return True
    
    def _execute_command(self, command: CommandInfo):
        """
        Execute a command received from the controller.
        
        Args:
            command: Command information
        """
        self.logger.info(f"Executing command: {command.id} ({command.command_type})")
        
        # Acknowledge receipt
        self.client.report_command_result(
            command_id=command.id,
            status="acknowledged"
        )
        
        # Execute the command
        result = self.action_registry.execute(
            command_type=command.command_type,
            payload=command.payload
        )
        
        # Report result
        self.client.report_command_result(
            command_id=command.id,
            status=result.status,
            result=result.result,
            error_message=result.error
        )
        
        if result.success:
            self.logger.info(f"Command {command.id} completed successfully")
        else:
            self.logger.error(f"Command {command.id} failed: {result.error}")
    
    def run(self):
        """
        Main agent loop.
        
        Runs until shutdown is requested or an unrecoverable error occurs.
        """
        global _shutdown_requested
        
        self.logger.info(f"Starting TacticalMesh Node Agent: {self.config.node_id}")
        
        # Try to load saved auth token
        token_file = Path(self.config.data_dir) / ".auth_token"
        if token_file.exists():
            self.client.auth_token = token_file.read_text().strip()
            self.logger.info("Loaded saved authentication token")
        
        # Registration loop
        retry_delay = 5
        while not self.registered and not _shutdown_requested:
            if self.register():
                break
            
            self.logger.warning(f"Registration failed, retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, self.config.retry_backoff_max)
        
        if _shutdown_requested:
            return
        
        # Main heartbeat loop
        heartbeat_failures = 0
        last_heartbeat_time = 0
        
        while not _shutdown_requested:
            current_time = time.time()
            
            # Send heartbeat at configured interval
            if current_time - last_heartbeat_time >= self.config.heartbeat_interval_seconds:
                if self.send_heartbeat():
                    heartbeat_failures = 0
                else:
                    heartbeat_failures += 1
                    
                    # Re-register if too many failures
                    if heartbeat_failures >= 3:
                        self.logger.warning("Multiple heartbeat failures, attempting re-registration")
                        self.registered = False
                        if self.register():
                            heartbeat_failures = 0
                
                last_heartbeat_time = current_time
            
            # Brief sleep to prevent tight loop
            time.sleep(1)
        
        self.logger.info("Node Agent shutting down...")
        self.client.close()
    
    def cleanup(self):
        """Cleanup resources on shutdown."""
        self.client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Apache TacticalMesh Node Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main --config config.yaml
  python -m agent.main --config config.yaml --log-level DEBUG
  python -m agent.main --init-config --node-id my-node-001 --controller http://controller:8000
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level from config"
    )
    
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Initialize a new configuration file"
    )
    
    parser.add_argument(
        "--node-id",
        help="Node ID for init-config"
    )
    
    parser.add_argument(
        "--controller",
        help="Controller URL for init-config"
    )
    
    args = parser.parse_args()
    
    # Handle config initialization
    if args.init_config:
        if not args.node_id or not args.controller:
            parser.error("--init-config requires --node-id and --controller")
        
        config_path = create_default_config(args.config, args.node_id, args.controller)
        print(f"Configuration file created: {config_path}")
        return 0
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")
        print("Use --init-config to create a new configuration file")
        return 1
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1
    
    # Override log level if specified
    if args.log_level:
        config.log_level = args.log_level
    
    # Setup logging
    logger = setup_logging(config)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run agent
    agent = NodeAgent(config, logger)
    
    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        agent.cleanup()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
