# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Multi-hop mesh routing module for TacticalMesh.

This module implements Level 2 smart routing, enabling nodes to relay
heartbeats and commands through mesh peers when direct controller
connectivity is lost.

Key features:
- Route discovery via broadcast to neighboring peers
- Path selection based on hop count and RTT
- Automatic failover when direct path fails
- Loop prevention with TTL/hop limits
- Path tracing for debugging and audit

Example flow:
    1. Node A loses controller connectivity
    2. Node A broadcasts ROUTE_REQUEST to peers
    3. Node B responds: "I can reach controller in 1 hop, 50ms RTT"
    4. Node A relays heartbeat through Node B
    5. Node B forwards to controller via HTTP
"""

import json
import logging
import struct
import time
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .peering import MeshPeering, PeerInfo

logger = logging.getLogger(__name__)


# Message types for routing protocol (extend peering.py types)
MSG_ROUTE_REQUEST = b'\x04'
MSG_ROUTE_RESPONSE = b'\x05'
MSG_RELAY_DATA = b'\x06'
MSG_RELAY_ACK = b'\x07'


@dataclass
class RoutePath:
    """
    Represents a discovered path to a destination.
    
    Attributes:
        target: Destination identifier ("controller" or node_id)
        next_hop: Node ID of the next peer in the path
        next_hop_addr: (address, port) tuple for the next hop
        total_hops: Total hop count to reach destination
        estimated_rtt_ms: Estimated round-trip time in milliseconds
        last_updated: When this route was last confirmed
        reliability: Success rate 0.0-1.0 based on recent attempts
        success_count: Number of successful relays through this path
        failure_count: Number of failed relays through this path
    """
    target: str
    next_hop: str
    next_hop_addr: tuple
    total_hops: int
    estimated_rtt_ms: float
    last_updated: datetime = field(default_factory=datetime.utcnow)
    reliability: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if route has expired (default 60 second TTL)."""
        return datetime.utcnow() - self.last_updated > timedelta(seconds=60)
    
    def record_success(self) -> None:
        """Record a successful relay through this path."""
        self.success_count += 1
        self._update_reliability()
        self.last_updated = datetime.utcnow()
    
    def record_failure(self) -> None:
        """Record a failed relay through this path."""
        self.failure_count += 1
        self._update_reliability()
    
    def _update_reliability(self) -> None:
        """Recalculate reliability score."""
        total = self.success_count + self.failure_count
        if total > 0:
            self.reliability = self.success_count / total


@dataclass  
class RelayMessage:
    """
    Wrapper for data being relayed through the mesh network.
    
    Attributes:
        message_id: Unique identifier for tracking
        msg_type: Type of payload ("heartbeat", "command_result", "command")
        origin_node_id: Node that originated this message
        destination: Target ("controller" or specific node_id)
        hop_count: Current hop count (incremented at each relay)
        max_hops: Maximum allowed hops (TTL, default 5)
        payload: The actual data being relayed
        path_trace: List of node IDs traversed (for debugging)
        timestamp: When the message was created
    """
    message_id: str
    msg_type: str
    origin_node_id: str
    destination: str
    hop_count: int
    max_hops: int
    payload: Dict[str, Any]
    path_trace: List[str]
    timestamp: str
    
    def to_bytes(self) -> bytes:
        """Serialize the relay message for UDP transmission."""
        data = asdict(self)
        return json.dumps(data).encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "RelayMessage":
        """Deserialize a relay message from UDP data."""
        parsed = json.loads(data.decode('utf-8'))
        return cls(**parsed)
    
    def increment_hop(self, node_id: str) -> bool:
        """
        Increment hop count and add node to path trace.
        
        Returns:
            True if message can continue (under max_hops), False if TTL exceeded
        """
        self.hop_count += 1
        self.path_trace.append(node_id)
        return self.hop_count <= self.max_hops


class MeshRouter:
    """
    Handles route discovery and message relay for mesh networking.
    
    Integrates with MeshPeering to use peer connectivity data and
    provides automatic failover routing when direct controller
    connectivity is lost.
    
    Attributes:
        node_id: This node's identifier
        peering: MeshPeering instance for peer management
        controller_client: ControllerClient for HTTP forwarding
        route_table: Discovered routes by destination
        route_cache_ttl: Seconds before routes expire (default 60)
        max_hops: Maximum relay hops (default 5)
    """
    
    def __init__(
        self,
        node_id: str,
        peering: "MeshPeering",
        controller_client: Any,
        route_cache_ttl: int = 60,
        max_hops: int = 5
    ):
        """
        Initialize the mesh router.
        
        Args:
            node_id: This node's identifier
            peering: MeshPeering instance for peer management
            controller_client: ControllerClient for forwarding to controller
            route_cache_ttl: Seconds before routes expire
            max_hops: Maximum relay hops allowed
        """
        self.node_id = node_id
        self.peering = peering
        self.controller_client = controller_client
        self.route_cache_ttl = route_cache_ttl
        self.max_hops = max_hops
        
        # Routing state
        self.route_table: Dict[str, List[RoutePath]] = {}  # destination → [routes]
        self.pending_requests: Dict[str, datetime] = {}  # request_id → timestamp
        self.relay_cache: Dict[str, RelayMessage] = {}  # message_id → message (for ACKs)
        
        # Metrics
        self.metrics = {
            "routes_discovered": 0,
            "messages_relayed": 0,
            "successful_deliveries": 0,
            "failed_relays": 0,
            "avg_hop_count": 0.0
        }
        self._hop_counts: List[int] = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Callback for when we successfully forward to controller
        self._on_relay_complete: Optional[Callable[[str, bool], None]] = None
        
        logger.info(f"MeshRouter initialized: node_id={node_id}, max_hops={max_hops}")
    
    # =========================================================================
    # Controller Connectivity
    # =========================================================================
    
    def can_reach_controller_directly(self) -> bool:
        """
        Check if we have direct controller connectivity.
        
        Uses the controller client's last successful contact to determine
        if direct communication is possible.
        
        Returns:
            True if controller is directly reachable
        """
        # Check if controller client has recent successful contact
        if hasattr(self.controller_client, 'last_success'):
            if self.controller_client.last_success:
                elapsed = (datetime.utcnow() - self.controller_client.last_success).total_seconds()
                return elapsed < 60  # Consider reachable if contact within 60s
        
        # Try a quick health check
        try:
            # Most controller clients have a health check method
            if hasattr(self.controller_client, 'health_check'):
                return self.controller_client.health_check()
        except Exception:
            pass
        
        return False
    
    # =========================================================================
    # Route Discovery
    # =========================================================================
    
    def discover_routes(self, destination: str = "controller") -> str:
        """
        Broadcast route request to all reachable peers.
        
        Args:
            destination: Target to find routes to (default "controller")
            
        Returns:
            Request ID for tracking responses
        """
        request_id = str(uuid.uuid4())[:8]
        
        with self._lock:
            self.pending_requests[request_id] = datetime.utcnow()
        
        # Build route request message
        # Format: MSG_ROUTE_REQUEST + node_id + \x00 + request_id + \x00 + destination
        message = (
            MSG_ROUTE_REQUEST +
            self.node_id.encode('utf-8') + b'\x00' +
            request_id.encode('utf-8') + b'\x00' +
            destination.encode('utf-8')
        )
        
        # Broadcast to all reachable peers
        reachable_peers = self.peering.get_reachable_peers()
        for peer in reachable_peers:
            try:
                self._send_to_peer(message, peer.address, peer.port)
                logger.debug(f"Sent ROUTE_REQUEST to {peer.node_id} for {destination}")
            except Exception as e:
                logger.warning(f"Failed to send ROUTE_REQUEST to {peer.node_id}: {e}")
        
        logger.info(f"Route discovery initiated: destination={destination}, request_id={request_id}, peers={len(reachable_peers)}")
        return request_id
    
    def handle_route_request(
        self, 
        sender_id: str, 
        sender_addr: tuple,
        request_id: str, 
        destination: str
    ) -> None:
        """
        Respond to a route request from a peer.
        
        If we can reach the destination, we respond with our path info.
        
        Args:
            sender_id: Node that sent the request
            sender_addr: (address, port) of sender
            request_id: Unique request identifier
            destination: Where they're trying to reach
        """
        logger.debug(f"Received ROUTE_REQUEST from {sender_id} for {destination}")
        
        # Determine our hop count to destination
        hops = -1
        rtt_ms = 0.0
        
        if destination == "controller":
            if self.can_reach_controller_directly():
                hops = 0  # We can reach directly
                rtt_ms = 10.0  # Estimate for direct HTTP
            else:
                # Check if we have a mesh route
                route = self.select_best_route(destination)
                if route and not route.is_expired:
                    hops = route.total_hops + 1
                    rtt_ms = route.estimated_rtt_ms + 20  # Add relay overhead
        else:
            # Routing to specific node
            if destination == self.node_id:
                hops = 0
                rtt_ms = 0.0
            elif destination in self.peering.peers:
                peer = self.peering.peers[destination]
                if peer.status.value == "reachable":
                    hops = 1
                    rtt_ms = peer.rtt_ms or 50.0
        
        # Only respond if we have a valid route
        if hops >= 0:
            self._send_route_response(sender_addr, request_id, destination, hops, rtt_ms)
    
    def _send_route_response(
        self,
        addr: tuple,
        request_id: str,
        destination: str,
        hops: int,
        rtt_ms: float
    ) -> None:
        """Send a route response to a peer."""
        # Format: MSG_ROUTE_RESPONSE + node_id + \x00 + request_id + \x00 + destination + \x00 + hops(2B) + rtt_ms(4B float)
        message = (
            MSG_ROUTE_RESPONSE +
            self.node_id.encode('utf-8') + b'\x00' +
            request_id.encode('utf-8') + b'\x00' +
            destination.encode('utf-8') + b'\x00' +
            struct.pack('!H', hops) +
            struct.pack('!f', rtt_ms)
        )
        
        self._send_to_peer(message, addr[0], addr[1])
        logger.debug(f"Sent ROUTE_RESPONSE: {destination} via {hops} hops, {rtt_ms:.1f}ms")
    
    def handle_route_response(
        self,
        sender_id: str,
        sender_addr: tuple,
        request_id: str,
        destination: str,
        hops: int,
        rtt_ms: float
    ) -> None:
        """
        Process a route response and update routing table.
        
        Args:
            sender_id: Node that can route to destination
            sender_addr: (address, port) of sender
            request_id: Original request ID
            destination: Target they can reach
            hops: Total hop count to reach destination (through them)
            rtt_ms: Estimated round-trip time
        """
        # Verify this is a response to our request
        with self._lock:
            if request_id not in self.pending_requests:
                logger.debug(f"Ignoring ROUTE_RESPONSE with unknown request_id: {request_id}")
                return
        
        # Create route path entry (their hops + 1 for the hop to them)
        route = RoutePath(
            target=destination,
            next_hop=sender_id,
            next_hop_addr=sender_addr,
            total_hops=hops + 1,
            estimated_rtt_ms=rtt_ms + (self.peering.peers.get(sender_id, {}).rtt_ms or 20),
            last_updated=datetime.utcnow()
        )
        
        # Add to route table
        with self._lock:
            if destination not in self.route_table:
                self.route_table[destination] = []
            
            # Check if we already have a route via this next_hop
            existing = [r for r in self.route_table[destination] if r.next_hop == sender_id]
            if existing:
                # Update existing route
                existing[0].total_hops = route.total_hops
                existing[0].estimated_rtt_ms = route.estimated_rtt_ms
                existing[0].last_updated = route.last_updated
            else:
                # Add new route
                self.route_table[destination].append(route)
                self.metrics["routes_discovered"] += 1
        
        logger.info(f"Route discovered: {destination} via {sender_id} ({route.total_hops} hops, {route.estimated_rtt_ms:.1f}ms)")
    
    # =========================================================================
    # Route Selection
    # =========================================================================
    
    def has_route_to(self, destination: str) -> bool:
        """Check if we have any valid route to destination."""
        with self._lock:
            if destination not in self.route_table:
                return False
            
            valid_routes = [r for r in self.route_table[destination] if not r.is_expired]
            return len(valid_routes) > 0
    
    def select_best_route(self, destination: str) -> Optional[RoutePath]:
        """
        Select optimal route from discovered paths.
        
        Selection criteria (in order):
        1. Fewest hops
        2. Lowest RTT (if hops equal)
        3. Highest reliability score
        
        Args:
            destination: Target node or "controller"
            
        Returns:
            Best RoutePath or None if no route available
        """
        with self._lock:
            if destination not in self.route_table:
                return None
            
            # Filter expired routes
            valid_routes = [r for r in self.route_table[destination] if not r.is_expired]
            
            if not valid_routes:
                return None
            
            # Sort by: hops (asc), RTT (asc), reliability (desc)
            valid_routes.sort(key=lambda r: (r.total_hops, r.estimated_rtt_ms, -r.reliability))
            
            return valid_routes[0]
    
    def get_all_routes(self, destination: str) -> List[RoutePath]:
        """Get all valid routes to a destination."""
        with self._lock:
            if destination not in self.route_table:
                return []
            return [r for r in self.route_table[destination] if not r.is_expired]
    
    def invalidate_route(self, destination: str, next_hop: str) -> None:
        """Invalidate a route that is no longer working."""
        with self._lock:
            if destination in self.route_table:
                self.route_table[destination] = [
                    r for r in self.route_table[destination]
                    if r.next_hop != next_hop
                ]
                logger.info(f"Route invalidated: {destination} via {next_hop}")
    
    # =========================================================================
    # Message Relay
    # =========================================================================
    
    def relay_message(self, message: RelayMessage, max_retries: int = 2) -> bool:
        """
        Send a message via mesh relay with automatic retry on failure.
        
        If the primary route fails, attempts alternate routes up to max_retries.
        Implements circuit breaker pattern by tracking peer failures.
        
        Args:
            message: The relay message to send
            max_retries: Maximum retry attempts with alternate routes (default 2)
            
        Returns:
            True if message was sent to next hop
        """
        # Check TTL
        if message.hop_count >= message.max_hops:
            logger.warning(f"Message {message.message_id} exceeded max hops ({message.max_hops})")
            self.metrics["failed_relays"] += 1
            return False
        
        # Get all valid routes, sorted by preference
        all_routes = self.get_all_routes(message.destination)
        if not all_routes:
            logger.warning(f"No route available to {message.destination}")
            self.metrics["failed_relays"] += 1
            return False
        
        # Sort routes: prefer fewer hops, lower RTT, higher reliability
        all_routes.sort(key=lambda r: (r.total_hops, r.estimated_rtt_ms, -r.reliability))
        
        # Filter out circuit-broken peers (reliability < 0.2 and recent failures)
        viable_routes = [
            r for r in all_routes 
            if r.reliability >= 0.2 or r.failure_count < 3
        ]
        
        if not viable_routes:
            # Fall back to all routes if all are circuit-broken
            viable_routes = all_routes
            logger.warning(f"All routes to {message.destination} are degraded, trying anyway")
        
        # Increment hop and add to path (do this once before trying)
        if not message.increment_hop(self.node_id):
            logger.warning(f"Message {message.message_id} TTL exceeded after increment")
            self.metrics["failed_relays"] += 1
            return False
        
        # Cache message for ACK tracking
        with self._lock:
            self.relay_cache[message.message_id] = message
        
        # Try routes with retry logic
        attempts = 0
        tried_peers = set()
        
        for route in viable_routes:
            if attempts >= max_retries + 1:
                break
            
            if route.next_hop in tried_peers:
                continue
            
            tried_peers.add(route.next_hop)
            attempts += 1
            
            try:
                data = MSG_RELAY_DATA + message.to_bytes()
                self._send_to_peer(data, route.next_hop_addr[0], route.next_hop_addr[1])
                
                # Success - update metrics and route reliability
                route.record_success()
                self.metrics["messages_relayed"] += 1
                self._hop_counts.append(message.hop_count)
                self._update_avg_hop_count()
                
                logger.info(
                    f"Relaying message {message.message_id}: "
                    f"{message.origin_node_id} → {route.next_hop} → {message.destination} "
                    f"(hop {message.hop_count}/{message.max_hops})"
                )
                return True
                
            except Exception as e:
                logger.warning(
                    f"Relay attempt {attempts} via {route.next_hop} failed: {e}"
                )
                route.record_failure()
                
                # Apply exponential backoff penalty to reliability
                if route.failure_count >= 3:
                    logger.info(
                        f"Circuit breaker: marking {route.next_hop} as degraded "
                        f"(reliability={route.reliability:.2f})"
                    )
        
        # All attempts failed
        logger.error(
            f"Failed to relay message {message.message_id} after {attempts} attempts"
        )
        self.metrics["failed_relays"] += 1
        
        # Remove from cache since delivery failed
        with self._lock:
            self.relay_cache.pop(message.message_id, None)
        
        return False

    
    def handle_incoming_relay(self, data: bytes, sender_addr: tuple) -> None:
        """
        Receive a relay message from a peer.
        
        Args:
            data: Raw message data (without MSG_RELAY_DATA prefix)
            sender_addr: (address, port) of sender
        """
        try:
            message = RelayMessage.from_bytes(data)
        except Exception as e:
            logger.error(f"Failed to parse relay message: {e}")
            return
        
        logger.debug(f"Received relay message {message.message_id} from {sender_addr}")
        
        # Check if this message is for us
        if message.destination == self.node_id:
            self._handle_message_for_self(message, sender_addr)
            return
        
        # Check if we should forward to controller
        if message.destination == "controller":
            if self.can_reach_controller_directly():
                self._forward_to_controller(message, sender_addr)
                return
        
        # Otherwise, relay further
        if message.hop_count < message.max_hops:
            success = self.relay_message(message)
            if not success:
                logger.warning(f"Failed to relay message {message.message_id} further")
        else:
            logger.warning(f"Message {message.message_id} reached max hops, dropping")
    
    def _handle_message_for_self(self, message: RelayMessage, sender_addr: tuple) -> None:
        """Handle a relay message destined for this node."""
        logger.info(f"Received message {message.message_id} for self: type={message.msg_type}")
        
        # Process based on message type
        if message.msg_type == "command":
            # TODO: Execute command and send result back
            pass
        
        # Send ACK back to origin
        self._send_relay_ack(message.message_id, message.origin_node_id, True)
    
    def _forward_to_controller(self, message: RelayMessage, sender_addr: tuple) -> bool:
        """
        Forward a relay message to the controller via HTTP.
        
        Args:
            message: Message to forward
            sender_addr: Address of the peer who sent it to us
            
        Returns:
            True if successfully delivered
        """
        logger.info(f"Forwarding message {message.message_id} to controller: type={message.msg_type}")
        
        success = False
        
        try:
            if message.msg_type == "heartbeat":
                # Extract heartbeat data and forward
                payload = message.payload
                result = self.controller_client.heartbeat(
                    node_id=message.origin_node_id,
                    cpu_usage=payload.get("cpu_usage"),
                    memory_usage=payload.get("memory_usage"),
                    disk_usage=payload.get("disk_usage"),
                    custom_metrics=payload.get("custom_metrics", {})
                )
                success = result is not None
                
            elif message.msg_type == "command_result":
                # Forward command result
                payload = message.payload
                self.controller_client.report_command_result(
                    command_id=payload.get("command_id"),
                    status=payload.get("status"),
                    result=payload.get("result"),
                    error_message=payload.get("error_message")
                )
                success = True
                
            else:
                logger.warning(f"Unknown message type for forwarding: {message.msg_type}")
                
        except Exception as e:
            logger.error(f"Failed to forward message {message.message_id} to controller: {e}")
            success = False
        
        # Update metrics
        if success:
            self.metrics["successful_deliveries"] += 1
            
            # Find and update route reliability
            for routes in self.route_table.values():
                for route in routes:
                    if route.next_hop_addr == sender_addr:
                        route.record_success()
        
        # Send ACK back through mesh
        self._send_relay_ack(message.message_id, message.origin_node_id, success)
        
        return success
    
    def _send_relay_ack(self, message_id: str, origin_node_id: str, success: bool) -> None:
        """Send acknowledgment for a relayed message."""
        # Build ACK message
        # Format: MSG_RELAY_ACK + message_id + \x00 + success(1B)
        message = (
            MSG_RELAY_ACK +
            message_id.encode('utf-8') + b'\x00' +
            (b'\x01' if success else b'\x00')
        )
        
        # Find route back to origin
        # For now, we rely on the path trace being reversible
        # In a real implementation, we'd maintain reverse routes
        logger.debug(f"ACK for {message_id}: success={success}")
    
    def handle_relay_ack(self, message_id: str, success: bool) -> None:
        """Handle acknowledgment of a relayed message."""
        with self._lock:
            if message_id in self.relay_cache:
                message = self.relay_cache.pop(message_id)
                
                if success:
                    logger.info(f"Relay confirmed: {message_id} delivered successfully")
                    if self._on_relay_complete:
                        self._on_relay_complete(message_id, True)
                else:
                    logger.warning(f"Relay failed: {message_id} delivery unsuccessful")
                    if self._on_relay_complete:
                        self._on_relay_complete(message_id, False)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _send_to_peer(self, data: bytes, address: str, port: int) -> None:
        """Send data to a peer via the peering socket."""
        if self.peering._socket:
            self.peering._socket.sendto(data, (address, port))
        else:
            raise RuntimeError("Peering socket not available")
    
    def _update_avg_hop_count(self) -> None:
        """Update average hop count metric."""
        if self._hop_counts:
            # Keep only last 100 samples
            if len(self._hop_counts) > 100:
                self._hop_counts = self._hop_counts[-100:]
            self.metrics["avg_hop_count"] = sum(self._hop_counts) / len(self._hop_counts)
    
    def cleanup_expired_routes(self) -> int:
        """Remove expired routes from the routing table."""
        removed = 0
        with self._lock:
            for destination in list(self.route_table.keys()):
                original_count = len(self.route_table[destination])
                self.route_table[destination] = [
                    r for r in self.route_table[destination]
                    if not r.is_expired
                ]
                removed += original_count - len(self.route_table[destination])
                
                # Remove empty destinations
                if not self.route_table[destination]:
                    del self.route_table[destination]
        
        if removed > 0:
            logger.debug(f"Cleaned up {removed} expired routes")
        return removed
    
    def get_routing_status(self) -> Dict[str, Any]:
        """Get current routing status for debugging."""
        with self._lock:
            routes_by_dest = {}
            for dest, routes in self.route_table.items():
                routes_by_dest[dest] = [
                    {
                        "next_hop": r.next_hop,
                        "hops": r.total_hops,
                        "rtt_ms": r.estimated_rtt_ms,
                        "reliability": r.reliability,
                        "expired": r.is_expired
                    }
                    for r in routes
                ]
            
            return {
                "node_id": self.node_id,
                "can_reach_controller": self.can_reach_controller_directly(),
                "routes": routes_by_dest,
                "pending_requests": len(self.pending_requests),
                "cached_relays": len(self.relay_cache),
                "metrics": self.metrics.copy()
            }
    
    def on_relay_complete(self, callback: Callable[[str, bool], None]) -> None:
        """Set callback for when relay is confirmed."""
        self._on_relay_complete = callback
