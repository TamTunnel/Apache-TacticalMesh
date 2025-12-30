# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Tests for message relay functionality.

Tests message relay, hop count, TTL enforcement, and path tracing.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.routing import MeshRouter, RoutePath, RelayMessage


class TestRelayMessageDataclass:
    """Tests for RelayMessage dataclass."""

    def test_relay_message_to_bytes_and_back(self, sample_relay_message):
        """Message should serialize and deserialize correctly."""
        serialized = sample_relay_message.to_bytes()
        
        assert isinstance(serialized, bytes)
        
        deserialized = RelayMessage.from_bytes(serialized)
        
        assert deserialized.message_id == sample_relay_message.message_id
        assert deserialized.msg_type == sample_relay_message.msg_type
        assert deserialized.origin_node_id == sample_relay_message.origin_node_id
        assert deserialized.destination == sample_relay_message.destination
        assert deserialized.hop_count == sample_relay_message.hop_count
        assert deserialized.max_hops == sample_relay_message.max_hops

    def test_increment_hop_adds_node_to_trace(self, sample_relay_message):
        """Incrementing hop should add node to path trace."""
        original_trace_length = len(sample_relay_message.path_trace)
        
        result = sample_relay_message.increment_hop("relay-node")
        
        assert result is True
        assert sample_relay_message.hop_count == 1
        assert len(sample_relay_message.path_trace) == original_trace_length + 1
        assert "relay-node" in sample_relay_message.path_trace

    def test_increment_hop_returns_false_when_ttl_exceeded(self):
        """Increment should return False when max_hops reached."""
        message = RelayMessage(
            message_id="test-001",
            msg_type="heartbeat",
            origin_node_id="node-001",
            destination="controller",
            hop_count=5,  # Already at limit
            max_hops=5,
            payload={"cpu": 50.0},
            path_trace=["n1", "n2", "n3", "n4", "n5"],
            timestamp=datetime.utcnow().isoformat()
        )
        
        result = message.increment_hop("n6")
        
        assert result is False
        assert message.hop_count == 6  # Still increments


class TestRelayMessage:
    """Tests for message relay functionality."""

    def test_relay_message_increments_hop_count(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Relay should increment hop count."""
        mesh_router.route_table["controller"] = [sample_route_path]
        original_hop_count = sample_relay_message.hop_count
        
        result = mesh_router.relay_message(sample_relay_message)
        
        assert result is True
        assert sample_relay_message.hop_count == original_hop_count + 1

    def test_relay_message_updates_path_trace(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Relay should add current node to path trace."""
        mesh_router.route_table["controller"] = [sample_route_path]
        original_trace_length = len(sample_relay_message.path_trace)
        
        mesh_router.relay_message(sample_relay_message)
        
        assert len(sample_relay_message.path_trace) == original_trace_length + 1
        assert mesh_router.node_id in sample_relay_message.path_trace

    def test_relay_message_rejects_max_hops(self, mesh_router, sample_route_path):
        """Messages at max_hops should be rejected."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        message = RelayMessage(
            message_id="test-002",
            msg_type="heartbeat",
            origin_node_id="node-001",
            destination="controller",
            hop_count=5,  # At limit
            max_hops=5,
            payload={"cpu": 50.0},
            path_trace=["n1", "n2", "n3", "n4", "n5"],
            timestamp=datetime.utcnow().isoformat()
        )
        
        result = mesh_router.relay_message(message)
        
        assert result is False
        assert mesh_router.metrics["failed_relays"] >= 1

    def test_relay_message_fails_without_route(self, mesh_router, sample_relay_message):
        """Relay should fail if no route exists."""
        # No routes in table
        
        result = mesh_router.relay_message(sample_relay_message)
        
        assert result is False
        assert mesh_router.metrics["failed_relays"] >= 1

    def test_relay_message_sends_to_next_hop(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Relay should send message to next hop address."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        mesh_router.relay_message(sample_relay_message)
        
        # Verify socket.sendto was called with correct address
        mesh_router.peering._socket.sendto.assert_called()
        call_args = mesh_router.peering._socket.sendto.call_args
        assert call_args[0][1] == sample_route_path.next_hop_addr

    def test_relay_message_updates_metrics(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Successful relay should update metrics."""
        mesh_router.route_table["controller"] = [sample_route_path]
        initial_relayed = mesh_router.metrics["messages_relayed"]
        
        mesh_router.relay_message(sample_relay_message)
        
        assert mesh_router.metrics["messages_relayed"] == initial_relayed + 1

    def test_relay_message_caches_for_ack(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Relayed messages should be cached for ACK tracking."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        mesh_router.relay_message(sample_relay_message)
        
        assert sample_relay_message.message_id in mesh_router.relay_cache


class TestRelayAck:
    """Tests for relay acknowledgment handling."""

    def test_handle_relay_ack_success_removes_from_cache(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Successful ACK should remove message from cache."""
        mesh_router.route_table["controller"] = [sample_route_path]
        mesh_router.relay_message(sample_relay_message)
        
        mesh_router.handle_relay_ack(sample_relay_message.message_id, success=True)
        
        assert sample_relay_message.message_id not in mesh_router.relay_cache

    def test_handle_relay_ack_failure_removes_from_cache(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """Failed ACK should also remove message from cache."""
        mesh_router.route_table["controller"] = [sample_route_path]
        mesh_router.relay_message(sample_relay_message)
        
        mesh_router.handle_relay_ack(sample_relay_message.message_id, success=False)
        
        assert sample_relay_message.message_id not in mesh_router.relay_cache

    def test_handle_relay_ack_calls_callback(
        self, mesh_router, sample_route_path, sample_relay_message
    ):
        """ACK should trigger callback if registered."""
        mesh_router.route_table["controller"] = [sample_route_path]
        callback = Mock()
        mesh_router.on_relay_complete(callback)
        
        mesh_router.relay_message(sample_relay_message)
        mesh_router.handle_relay_ack(sample_relay_message.message_id, success=True)
        
        callback.assert_called_once_with(sample_relay_message.message_id, True)

    def test_handle_relay_ack_ignores_unknown_message(self, mesh_router):
        """ACK for unknown message should be ignored."""
        # Should not raise
        mesh_router.handle_relay_ack("unknown-msg-id", success=True)


class TestIncomingRelay:
    """Tests for handling incoming relay messages."""

    def test_incoming_relay_for_controller_forwards(self, mesh_router):
        """Relay to controller should forward via HTTP."""
        mesh_router.controller_client.heartbeat = Mock(return_value=[])
        
        # Make router think it can reach controller
        with patch.object(mesh_router, 'can_reach_controller_directly', return_value=True):
            message_data = RelayMessage(
                message_id="test-003",
                msg_type="heartbeat",
                origin_node_id="node-001",
                destination="controller",
                hop_count=1,
                max_hops=5,
                payload={"cpu": 50.0, "memory": 60.0},
                path_trace=["node-001", "node-002"],
                timestamp=datetime.utcnow().isoformat()
            ).to_bytes()
            
            mesh_router.handle_incoming_relay(message_data, ("192.168.1.102", 7777))
            
            # Should have called heartbeat on controller client
            mesh_router.controller_client.heartbeat.assert_called()

    def test_incoming_relay_relays_further_when_no_direct_access(
        self, mesh_router, sample_route_path
    ):
        """Relay should continue if we can't reach controller directly."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        with patch.object(mesh_router, 'can_reach_controller_directly', return_value=False):
            message_data = RelayMessage(
                message_id="test-004",
                msg_type="heartbeat",
                origin_node_id="node-001",
                destination="controller",
                hop_count=1,
                max_hops=5,
                payload={"cpu": 50.0},
                path_trace=["node-001"],
                timestamp=datetime.utcnow().isoformat()
            ).to_bytes()
            
            mesh_router.handle_incoming_relay(message_data, ("192.168.1.100", 7777))
            
            # Should have sent to next hop
            mesh_router.peering._socket.sendto.assert_called()
