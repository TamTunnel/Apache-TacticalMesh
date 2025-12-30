# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Integration tests for multi-node mesh routing scenarios.

Tests end-to-end relay paths and failure handling.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.routing import MeshRouter, RoutePath, RelayMessage
from mesh.peering import MeshPeering, PeerInfo, PeerStatus


class TestMultiNodeRelay:
    """Integration tests for multi-node relay scenarios."""

    def test_three_node_relay_scenario(self, mock_controller_client):
        """
        Test A → B → Controller relay scenario.
        
        Scenario:
        - Node A cannot reach controller directly
        - Node A discovers Node B can reach controller
        - Node A relays heartbeat through Node B
        """
        # Setup Node A
        peering_a = Mock(spec=MeshPeering)
        peering_a._socket = Mock()
        peering_a.node_id = "node-a"
        
        router_a = MeshRouter(
            node_id="node-a",
            peering=peering_a,
            controller_client=mock_controller_client
        )
        
        # Node A has route to controller via Node B
        route_via_b = RoutePath(
            target="controller",
            next_hop="node-b",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow()
        )
        router_a.route_table["controller"] = [route_via_b]
        
        # Create heartbeat message
        message = RelayMessage(
            message_id="hb-001",
            msg_type="heartbeat",
            origin_node_id="node-a",
            destination="controller",
            hop_count=0,
            max_hops=5,
            payload={"cpu": 45.0, "memory": 60.0},
            path_trace=["node-a"],
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Relay message
        result = router_a.relay_message(message)
        
        # Verify
        assert result is True
        assert message.hop_count == 1
        assert "node-a" in message.path_trace
        peering_a._socket.sendto.assert_called_once()

    def test_route_rediscovery_on_failure(self, mesh_router, mock_peering, sample_peers):
        """Route should be rediscovered when relay fails."""
        # Setup initial route
        bad_route = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow()
        )
        mesh_router.route_table["controller"] = [bad_route]
        
        # Make socket throw an error on send
        mock_peering._socket.sendto.side_effect = Exception("Network unreachable")
        
        message = RelayMessage(
            message_id="hb-002",
            msg_type="heartbeat",
            origin_node_id="test-node-001",
            destination="controller",
            hop_count=0,
            max_hops=5,
            payload={"cpu": 50.0},
            path_trace=[],
            timestamp=datetime.utcnow().isoformat()
        )
        
        result = mesh_router.relay_message(message)
        
        # Relay should fail
        assert result is False
        # Bad route should have failure recorded
        assert bad_route.failure_count >= 1

    def test_metrics_tracking(self, mesh_router, sample_route_path, sample_relay_message):
        """Verify metrics are tracked correctly across operations."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        initial_metrics = mesh_router.metrics.copy()
        
        # Successful relay
        mesh_router.relay_message(sample_relay_message)
        
        assert mesh_router.metrics["messages_relayed"] == initial_metrics["messages_relayed"] + 1
        
        # Failed relay (no route to destination)
        bad_message = RelayMessage(
            message_id="bad-001",
            msg_type="heartbeat",
            origin_node_id="node-001",
            destination="unknown",
            hop_count=0,
            max_hops=5,
            payload={},
            path_trace=[],
            timestamp=datetime.utcnow().isoformat()
        )
        mesh_router.relay_message(bad_message)
        
        assert mesh_router.metrics["failed_relays"] >= initial_metrics["failed_relays"] + 1


class TestControllerConnectivity:
    """Tests for controller connectivity detection."""

    def test_can_reach_controller_directly_true_when_recent_success(
        self, mesh_router, mock_controller_client
    ):
        """Should return True if recent successful contact."""
        mock_controller_client.last_success = datetime.utcnow()
        
        with patch.object(mesh_router, 'controller_client', mock_controller_client):
            mesh_router.controller_client = mock_controller_client
            result = mesh_router.can_reach_controller_directly()
            
            assert result is True

    def test_can_reach_controller_directly_false_when_no_recent_success(
        self, mesh_router, mock_controller_client
    ):
        """Should return False if no recent successful contact."""
        mock_controller_client.last_success = datetime.utcnow() - timedelta(seconds=120)
        
        mesh_router.controller_client = mock_controller_client
        result = mesh_router.can_reach_controller_directly()
        
        assert result is False


class TestRoutingStatus:
    """Tests for routing status reporting."""

    def test_get_routing_status_returns_complete_info(
        self, mesh_router, sample_route_path
    ):
        """Status should include all relevant routing information."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        status = mesh_router.get_routing_status()
        
        assert "node_id" in status
        assert "can_reach_controller" in status
        assert "routes" in status
        assert "controller" in status["routes"]
        assert "metrics" in status
        assert len(status["routes"]["controller"]) == 1

    def test_get_routing_status_includes_metrics(self, mesh_router):
        """Status should include current metrics."""
        status = mesh_router.get_routing_status()
        
        assert "messages_relayed" in status["metrics"]
        assert "successful_deliveries" in status["metrics"]
        assert "failed_relays" in status["metrics"]
        assert "avg_hop_count" in status["metrics"]
