#!/usr/bin/env python3
# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
TacticalMesh Node Agent - Main Entry Point

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
import struct
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import psutil

from .config import load_config, create_default_config, AgentConfig
from .client import ControllerClient, CommandInfo
from .actions import create_default_registry, ActionRegistry
from .mesh.peering import MeshPeering, PeerStatus
from .mesh.routing import MeshRouter, RelayMessage, MSG_ROUTE_REQUEST, MSG_ROUTE_RESPONSE, MSG_RELAY_DATA, MSG_RELAY_ACK

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
    command execution, and mesh networking.
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
        
        # Mesh networking components
        self.mesh_peering: Optional[MeshPeering] = None
        self.mesh_router: Optional[MeshRouter] = None
        self._init_mesh()
    
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
        
        Tries direct connection first, falls back to mesh relay if enabled.
        
        Returns:
            True if heartbeat was acknowledged (directly or via mesh)
        """
        # Try direct path first
        if self._send_heartbeat_direct():
            return True
        
        self.logger.warning("Direct heartbeat failed - controller unreachable")
        
        # If mesh enabled, try mesh relay
        if self.mesh_router:
            self.logger.info("Attempting mesh relay for heartbeat...")
            return self._send_heartbeat_via_mesh()
        
        return False

    
    def _init_mesh(self) -> None:
        """Initialize mesh networking if enabled."""
        if not self.config.mesh or not self.config.mesh.enabled:
            self.logger.info("Mesh networking disabled")
            return
        
        mesh_config = self.config.mesh
        
        # Initialize mesh peering
        self.mesh_peering = MeshPeering(
            node_id=self.config.node_id,
            listen_port=mesh_config.listen_port,
            heartbeat_interval=mesh_config.heartbeat_interval_seconds,
            peer_timeout=mesh_config.peer_timeout_seconds
        )
        
        # Add static peers from config
        for peer in mesh_config.peers:
            self.mesh_peering.add_static_peer(
                peer.node_id,
                peer.address,
                peer.port
            )
        
        # Initialize mesh router
        self.mesh_router = MeshRouter(
            node_id=self.config.node_id,
            peering=self.mesh_peering,
            controller_client=self.client,
            route_cache_ttl=mesh_config.route_cache_ttl_seconds,
            max_hops=mesh_config.max_hops
        )
        
        # Hook up message handlers
        self.mesh_peering.on_routing_message(self._handle_mesh_message)
        
        # Start mesh peering
        self.mesh_peering.start()
        
        self.logger.info(
            f"Mesh networking enabled: port={mesh_config.listen_port}, "
            f"peers={len(mesh_config.peers)}, max_hops={mesh_config.max_hops}"
        )
    
    def _handle_mesh_message(self, msg_type: bytes, payload: bytes, sender_addr: tuple) -> None:
        """
        Handle incoming mesh routing messages.
        
        Dispatches to appropriate MeshRouter method based on message type.
        
        Args:
            msg_type: Message type byte
            payload: Message payload after type byte
            sender_addr: (address, port) of sender
        """
        if not self.mesh_router:
            return
        
        try:
            if msg_type == MSG_ROUTE_REQUEST:
                # Parse: node_id + \x00 + request_id + \x00 + destination
                parts = payload.split(b'\x00', 2)
                if len(parts) >= 3:
                    sender_id = parts[0].decode('utf-8')
                    request_id = parts[1].decode('utf-8')
                    destination = parts[2].decode('utf-8')
                    self.mesh_router.handle_route_request(
                        sender_id, sender_addr, request_id, destination
                    )
            
            elif msg_type == MSG_ROUTE_RESPONSE:
                # Parse: node_id + \x00 + request_id + \x00 + destination + \x00 + hops(2B) + rtt(4B)
                parts = payload.split(b'\x00', 3)
                if len(parts) >= 4:
                    sender_id = parts[0].decode('utf-8')
                    request_id = parts[1].decode('utf-8')
                    destination = parts[2].decode('utf-8')
                    hops = struct.unpack('!H', parts[3][:2])[0]
                    rtt_ms = struct.unpack('!f', parts[3][2:6])[0]
                    self.mesh_router.handle_route_response(
                        sender_id, sender_addr, request_id, destination, hops, rtt_ms
                    )
            
            elif msg_type == MSG_RELAY_DATA:
                self.mesh_router.handle_incoming_relay(payload, sender_addr)
            
            elif msg_type == MSG_RELAY_ACK:
                # Parse: message_id + \x00 + success(1B)
                parts = payload.split(b'\x00', 1)
                if len(parts) >= 2:
                    message_id = parts[0].decode('utf-8')
                    success = parts[1][0] == 1 if parts[1] else False
                    self.mesh_router.handle_relay_ack(message_id, success)
                    
        except Exception as e:
            self.logger.error(f"Error handling mesh message: {e}")
    
    def _send_heartbeat_direct(self) -> bool:
        """
        Send heartbeat directly to controller.
        
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
            return False
        
        self.last_heartbeat = datetime.utcnow()
        self.logger.debug(f"Direct heartbeat acknowledged, {len(pending_commands)} pending commands")
        
        # Process any pending commands
        for cmd in pending_commands:
            self._execute_command(cmd)
        
        return True
    
    def _send_heartbeat_via_mesh(self) -> bool:
        """
        Send heartbeat via mesh routing when direct path fails.
        
        Returns:
            True if heartbeat was relayed successfully
        """
        if not self.mesh_router:
            return False
        
        # Discover routes if needed
        if not self.mesh_router.has_route_to("controller"):
            self.logger.info("Discovering mesh routes to controller...")
            self.mesh_router.discover_routes("controller")
            # Wait for responses
            time.sleep(2.5)
        
        # Check if route exists now
        route = self.mesh_router.select_best_route("controller")
        if not route:
            self.logger.warning("No mesh route to controller available")
            return False
        
        # Wrap heartbeat data in relay message
        metrics = get_system_metrics()
        relay_msg = RelayMessage(
            message_id=str(uuid.uuid4()),
            msg_type="heartbeat",
            origin_node_id=self.config.node_id,
            destination="controller",
            hop_count=0,
            max_hops=self.config.mesh.max_hops if self.config.mesh else 5,
            payload={
                "node_id": self.config.node_id,
                "cpu_usage": metrics.get("cpu_usage"),
                "memory_usage": metrics.get("memory_usage"),
                "disk_usage": metrics.get("disk_usage"),
                "timestamp": datetime.utcnow().isoformat()
            },
            path_trace=[],
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Send via mesh router
        success = self.mesh_router.relay_message(relay_msg)
        if success:
            self.logger.info(
                f"Heartbeat relayed via {route.next_hop} "
                f"({route.total_hops} hops, {route.estimated_rtt_ms:.0f}ms RTT)"
            )
            self.last_heartbeat = datetime.utcnow()
        
        return success
    
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
        if self.mesh_peering:
            self.mesh_peering.stop()
        self.client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TacticalMesh Node Agent",
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
