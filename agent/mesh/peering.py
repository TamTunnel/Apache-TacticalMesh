# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Peer-to-peer mesh networking module for TacticalMesh.

> [!WARNING]
> This module is EXPERIMENTAL and intended for lab/demo environments only.
> It provides basic peer discovery and heartbeat exchange to demonstrate
> mesh networking concepts. Production mesh routing is planned for v0.2+.

This module implements:
- Peer discovery via static configuration or mDNS (when available)
- Simple heartbeat/ping exchange between neighboring nodes
- Peer status tracking

The goal is to provide just enough "mesh flavor" to justify the name while
keeping the implementation simple and auditable.
"""

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Callable
import threading

logger = logging.getLogger(__name__)


class PeerStatus(Enum):
    """Status of a peer node in the mesh."""
    UNKNOWN = "unknown"
    DISCOVERED = "discovered"
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"


@dataclass
class PeerInfo:
    """Information about a peer node."""
    node_id: str
    address: str
    port: int
    status: PeerStatus = PeerStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    rtt_ms: Optional[float] = None
    metadata: Dict = field(default_factory=dict)
    
    @property
    def is_stale(self) -> bool:
        """Check if peer information is stale (no contact in 60 seconds)."""
        if self.last_seen is None:
            return True
        return datetime.utcnow() - self.last_seen > timedelta(seconds=60)


class MeshPeering:
    """
    Experimental mesh peering implementation.
    
    This class manages peer discovery and heartbeat exchange with neighboring
    nodes in the mesh network. It is designed to be simple and auditable,
    serving as a foundation for more sophisticated mesh routing in future versions.
    
    Configuration example (in agent config.yaml):
    
        mesh:
          enabled: true
          listen_port: 7777
          peers:
            - node_id: edge-node-002
              address: 192.168.1.102
              port: 7777
            - node_id: edge-node-003
              address: 192.168.1.103
              port: 7777
          heartbeat_interval_seconds: 10
          peer_timeout_seconds: 30
    
    Attributes:
        node_id: This node's identifier
        listen_port: UDP port for receiving peer messages
        peers: Dictionary of known peers by node_id
        running: Whether the peering service is active
    """
    
    # Message types for the simple peer protocol
    MSG_PING = b'\x01'
    MSG_PONG = b'\x02'
    MSG_ANNOUNCE = b'\x03'
    
    # Routing protocol message types (handled externally)
    MSG_ROUTE_REQUEST = b'\x04'
    MSG_ROUTE_RESPONSE = b'\x05'
    MSG_RELAY_DATA = b'\x06'
    MSG_RELAY_ACK = b'\x07'
    
    def __init__(
        self,
        node_id: str,
        listen_port: int = 7777,
        heartbeat_interval: float = 10.0,
        peer_timeout: float = 30.0
    ):
        """
        Initialize the mesh peering service.
        
        Args:
            node_id: This node's identifier
            listen_port: UDP port to listen on (default: 7777)
            heartbeat_interval: Seconds between heartbeat pings (default: 10)
            peer_timeout: Seconds before marking peer unreachable (default: 30)
        """
        self.node_id = node_id
        self.listen_port = listen_port
        self.heartbeat_interval = heartbeat_interval
        self.peer_timeout = peer_timeout
        
        self.peers: Dict[str, PeerInfo] = {}
        self.running = False
        self._socket: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._pending_pings: Dict[str, float] = {}  # node_id -> send_time
        
        # Callbacks for integration
        self._on_peer_discovered: Optional[Callable[[PeerInfo], None]] = None
        self._on_peer_status_changed: Optional[Callable[[PeerInfo, PeerStatus], None]] = None
        self._on_routing_message: Optional[Callable[[bytes, bytes, tuple], None]] = None
        
        logger.info(f"MeshPeering initialized: node_id={node_id}, port={listen_port}")
    
    def add_static_peer(self, node_id: str, address: str, port: int = 7777) -> None:
        """
        Add a peer from static configuration.
        
        Args:
            node_id: Peer's node identifier
            address: Peer's IP address or hostname
            port: Peer's mesh port
        """
        if node_id == self.node_id:
            logger.debug(f"Skipping self as peer: {node_id}")
            return
            
        peer = PeerInfo(
            node_id=node_id,
            address=address,
            port=port,
            status=PeerStatus.DISCOVERED
        )
        self.peers[node_id] = peer
        logger.info(f"Added static peer: {node_id} at {address}:{port}")
    
    def start(self) -> None:
        """
        Start the mesh peering service.
        
        This starts:
        - UDP listener for incoming peer messages
        - Heartbeat sender for periodic peer pings
        """
        if self.running:
            logger.warning("MeshPeering already running")
            return
        
        self.running = True
        
        # Create UDP socket
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(('0.0.0.0', self.listen_port))
            self._socket.settimeout(1.0)  # Allow periodic checking of running flag
            logger.info(f"Mesh peering listening on UDP port {self.listen_port}")
        except Exception as e:
            logger.error(f"Failed to bind mesh socket: {e}")
            self.running = False
            return
        
        # Start listener thread
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._listener_thread.start()
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        
        logger.info("Mesh peering service started")
    
    def stop(self) -> None:
        """Stop the mesh peering service."""
        self.running = False
        
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        
        if self._listener_thread:
            self._listener_thread.join(timeout=2.0)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
        
        logger.info("Mesh peering service stopped")
    
    def _listener_loop(self) -> None:
        """Main loop for receiving peer messages."""
        logger.debug("Listener loop started")
        
        while self.running and self._socket:
            try:
                data, addr = self._socket.recvfrom(1024)
                self._handle_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Listener error: {e}")
    
    def _heartbeat_loop(self) -> None:
        """Main loop for sending heartbeat pings to peers."""
        logger.debug("Heartbeat loop started")
        
        while self.running:
            # Send ping to all known peers
            for peer in list(self.peers.values()):
                self._send_ping(peer)
                self._check_peer_timeout(peer)
            
            # Wait for next heartbeat interval
            time.sleep(self.heartbeat_interval)
    
    def _send_ping(self, peer: PeerInfo) -> None:
        """Send a ping message to a peer."""
        if not self._socket:
            return
        
        try:
            # Simple ping message: MSG_PING + node_id (null-terminated)
            message = self.MSG_PING + self.node_id.encode('utf-8') + b'\x00'
            self._socket.sendto(message, (peer.address, peer.port))
            self._pending_pings[peer.node_id] = time.time()
            logger.debug(f"Sent ping to {peer.node_id} at {peer.address}:{peer.port}")
        except Exception as e:
            logger.debug(f"Failed to ping {peer.node_id}: {e}")
    
    def _send_pong(self, sender_id: str, addr: tuple) -> None:
        """Send a pong response to a ping."""
        if not self._socket:
            return
        
        try:
            message = self.MSG_PONG + self.node_id.encode('utf-8') + b'\x00'
            self._socket.sendto(message, addr)
            logger.debug(f"Sent pong to {sender_id} at {addr}")
        except Exception as e:
            logger.debug(f"Failed to send pong to {sender_id}: {e}")
    
    def _handle_message(self, data: bytes, addr: tuple) -> None:
        """Handle an incoming peer message."""
        if len(data) < 2:
            return
        
        msg_type = data[0:1]
        payload = data[1:].split(b'\x00')[0].decode('utf-8', errors='ignore')
        sender_id = payload
        
        if msg_type == self.MSG_PING:
            logger.debug(f"Received ping from {sender_id} at {addr}")
            self._send_pong(sender_id, addr)
            self._update_peer_status(sender_id, addr, PeerStatus.REACHABLE)
            
        elif msg_type == self.MSG_PONG:
            logger.debug(f"Received pong from {sender_id} at {addr}")
            
            # Calculate RTT if we have a pending ping
            rtt_ms = None
            if sender_id in self._pending_pings:
                rtt_ms = (time.time() - self._pending_pings[sender_id]) * 1000
                del self._pending_pings[sender_id]
            
            self._update_peer_status(sender_id, addr, PeerStatus.REACHABLE, rtt_ms)
        
        elif msg_type in (self.MSG_ROUTE_REQUEST, self.MSG_ROUTE_RESPONSE, 
                          self.MSG_RELAY_DATA, self.MSG_RELAY_ACK):
            # Routing messages are handled by the MeshRouter
            if self._on_routing_message:
                self._on_routing_message(msg_type, data[1:], addr)
            else:
                logger.debug(f"Received routing message but no handler registered")
    
    def _update_peer_status(
        self, 
        node_id: str, 
        addr: tuple, 
        status: PeerStatus,
        rtt_ms: Optional[float] = None
    ) -> None:
        """Update the status of a peer."""
        now = datetime.utcnow()
        
        if node_id in self.peers:
            peer = self.peers[node_id]
            old_status = peer.status
            peer.status = status
            peer.last_seen = now
            if rtt_ms is not None:
                peer.rtt_ms = rtt_ms
            
            if old_status != status:
                logger.info(f"Peer {node_id} status changed: {old_status.value} -> {status.value}")
                if self._on_peer_status_changed:
                    self._on_peer_status_changed(peer, old_status)
        else:
            # Discovered a new peer
            peer = PeerInfo(
                node_id=node_id,
                address=addr[0],
                port=addr[1],
                status=status,
                last_seen=now,
                rtt_ms=rtt_ms
            )
            self.peers[node_id] = peer
            logger.info(f"Discovered new peer: {node_id} at {addr[0]}:{addr[1]}")
            if self._on_peer_discovered:
                self._on_peer_discovered(peer)
    
    def _check_peer_timeout(self, peer: PeerInfo) -> None:
        """Check if a peer has timed out."""
        if peer.last_seen is None:
            return
        
        elapsed = (datetime.utcnow() - peer.last_seen).total_seconds()
        if elapsed > self.peer_timeout and peer.status == PeerStatus.REACHABLE:
            old_status = peer.status
            peer.status = PeerStatus.UNREACHABLE
            logger.warning(f"Peer {peer.node_id} unreachable (no response for {elapsed:.1f}s)")
            if self._on_peer_status_changed:
                self._on_peer_status_changed(peer, old_status)
    
    def get_reachable_peers(self) -> List[PeerInfo]:
        """Get list of currently reachable peers."""
        return [p for p in self.peers.values() if p.status == PeerStatus.REACHABLE]
    
    def get_peer_status_summary(self) -> Dict[str, int]:
        """Get summary of peer statuses."""
        summary = {status.value: 0 for status in PeerStatus}
        for peer in self.peers.values():
            summary[peer.status.value] += 1
        return summary
    
    def on_peer_discovered(self, callback: Callable[[PeerInfo], None]) -> None:
        """Set callback for new peer discovery."""
        self._on_peer_discovered = callback
    
    def on_peer_status_changed(self, callback: Callable[[PeerInfo, PeerStatus], None]) -> None:
        """Set callback for peer status changes."""
        self._on_peer_status_changed = callback
    
    def on_routing_message(self, callback: Callable[[bytes, bytes, tuple], None]) -> None:
        """
        Set callback for routing protocol messages.
        
        The callback receives (msg_type, payload, sender_addr) where:
        - msg_type: One of MSG_ROUTE_REQUEST, MSG_ROUTE_RESPONSE, MSG_RELAY_DATA, MSG_RELAY_ACK
        - payload: Message data after the type byte
        - sender_addr: (address, port) tuple of the sender
        """
        self._on_routing_message = callback
    
    def send_raw(self, data: bytes, address: str, port: int) -> bool:
        """
        Send raw data to a specific address.
        
        Used by MeshRouter for sending routing protocol messages.
        
        Args:
            data: Raw bytes to send
            address: Destination IP address
            port: Destination port
            
        Returns:
            True if send was successful
        """
        if not self._socket:
            return False
        
        try:
            self._socket.sendto(data, (address, port))
            return True
        except Exception as e:
            logger.error(f"Failed to send raw data to {address}:{port}: {e}")
            return False
