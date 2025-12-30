# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Tests for mesh routing core functionality.

Tests route discovery, path selection, and route cache management.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, call
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.routing import MeshRouter, RoutePath, RelayMessage, MSG_ROUTE_REQUEST


class TestRouteDiscovery:
    """Tests for route discovery functionality."""

    def test_discover_routes_broadcasts_to_all_reachable_peers(
        self, mesh_router, mock_peering, sample_peers
    ):
        """Route discovery should broadcast to all reachable peers."""
        # Only return reachable peers
        reachable = [p for p in sample_peers if p.status.value == "reachable"]
        mock_peering.get_reachable_peers.return_value = reachable
        
        request_id = mesh_router.discover_routes("controller")
        
        # Should have sent to both reachable peers
        assert mock_peering._socket.sendto.call_count == 2
        assert request_id is not None
        assert len(request_id) == 8  # UUID prefix

    def test_discover_routes_returns_request_id(self, mesh_router, mock_peering):
        """Route discovery should return a unique request ID."""
        mock_peering.get_reachable_peers.return_value = []
        
        request_id = mesh_router.discover_routes("controller")
        
        assert request_id is not None
        assert request_id in mesh_router.pending_requests

    def test_discover_routes_ignores_unreachable_peers(
        self, mesh_router, mock_peering, sample_peers
    ):
        """Route discovery should not send to unreachable peers."""
        # Include unreachable peer
        mock_peering.get_reachable_peers.return_value = []
        
        mesh_router.discover_routes("controller")
        
        # Should not have sent any messages
        assert mock_peering._socket.sendto.call_count == 0


class TestPathSelection:
    """Tests for path selection algorithms."""

    def test_select_best_route_prefers_fewer_hops(self, mesh_router):
        """Fewer hops should win over lower RTT."""
        route_1hop = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=100.0,
            last_updated=datetime.utcnow(),
            reliability=1.0
        )
        
        route_2hop_faster = RoutePath(
            target="controller",
            next_hop="node-003",
            next_hop_addr=("192.168.1.103", 7777),
            total_hops=2,
            estimated_rtt_ms=50.0,  # Faster but more hops
            last_updated=datetime.utcnow(),
            reliability=1.0
        )
        
        mesh_router.route_table["controller"] = [route_2hop_faster, route_1hop]
        
        best = mesh_router.select_best_route("controller")
        
        assert best.total_hops == 1
        assert best.next_hop == "node-002"

    def test_select_best_route_uses_rtt_as_tiebreaker(self, mesh_router):
        """When hops are equal, prefer lower RTT."""
        route_fast = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=2,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow(),
            reliability=1.0
        )
        
        route_slow = RoutePath(
            target="controller",
            next_hop="node-003",
            next_hop_addr=("192.168.1.103", 7777),
            total_hops=2,
            estimated_rtt_ms=150.0,
            last_updated=datetime.utcnow(),
            reliability=1.0
        )
        
        mesh_router.route_table["controller"] = [route_slow, route_fast]
        
        best = mesh_router.select_best_route("controller")
        
        assert best.estimated_rtt_ms == 50.0
        assert best.next_hop == "node-002"

    def test_select_best_route_uses_reliability_as_final_tiebreaker(self, mesh_router):
        """When hops and RTT equal, prefer higher reliability."""
        route_reliable = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=2,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow(),
            reliability=0.95
        )
        
        route_unreliable = RoutePath(
            target="controller",
            next_hop="node-003",
            next_hop_addr=("192.168.1.103", 7777),
            total_hops=2,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow(),
            reliability=0.5
        )
        
        mesh_router.route_table["controller"] = [route_unreliable, route_reliable]
        
        best = mesh_router.select_best_route("controller")
        
        assert best.reliability == 0.95
        assert best.next_hop == "node-002"

    def test_select_best_route_returns_none_for_unknown_destination(self, mesh_router):
        """Should return None if no route exists."""
        best = mesh_router.select_best_route("unknown-destination")
        
        assert best is None

    def test_select_best_route_ignores_expired_routes(self, mesh_router, expired_route_path):
        """Expired routes should not be selected."""
        mesh_router.route_table["controller"] = [expired_route_path]
        
        best = mesh_router.select_best_route("controller")
        
        assert best is None


class TestRouteCache:
    """Tests for route cache management."""

    def test_has_route_to_returns_true_when_valid_route_exists(
        self, mesh_router, sample_route_path
    ):
        """Should return True when valid route exists."""
        mesh_router.route_table["controller"] = [sample_route_path]
        
        assert mesh_router.has_route_to("controller") is True

    def test_has_route_to_returns_false_when_all_routes_expired(
        self, mesh_router, expired_route_path
    ):
        """Should return False when all routes are expired."""
        mesh_router.route_table["controller"] = [expired_route_path]
        
        assert mesh_router.has_route_to("controller") is False

    def test_has_route_to_returns_false_for_unknown_destination(self, mesh_router):
        """Should return False for unknown destinations."""
        assert mesh_router.has_route_to("unknown") is False

    def test_cleanup_expired_routes_removes_old_routes(
        self, mesh_router, sample_route_path, expired_route_path
    ):
        """Cleanup should remove expired routes but keep valid ones."""
        mesh_router.route_table["controller"] = [sample_route_path, expired_route_path]
        
        removed = mesh_router.cleanup_expired_routes()
        
        assert removed == 1
        assert len(mesh_router.route_table["controller"]) == 1
        assert mesh_router.route_table["controller"][0].next_hop == sample_route_path.next_hop

    def test_invalidate_route_removes_specific_next_hop(self, mesh_router):
        """Invalidate should remove only routes via specific next_hop."""
        route1 = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow()
        )
        route2 = RoutePath(
            target="controller",
            next_hop="node-003",
            next_hop_addr=("192.168.1.103", 7777),
            total_hops=2,
            estimated_rtt_ms=100.0,
            last_updated=datetime.utcnow()
        )
        
        mesh_router.route_table["controller"] = [route1, route2]
        
        mesh_router.invalidate_route("controller", "node-002")
        
        assert len(mesh_router.route_table["controller"]) == 1
        assert mesh_router.route_table["controller"][0].next_hop == "node-003"


class TestRoutePathDataclass:
    """Tests for RoutePath dataclass methods."""

    def test_route_path_is_expired_when_old(self):
        """Route should be expired when older than TTL."""
        route = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow() - timedelta(seconds=120)
        )
        
        assert route.is_expired is True

    def test_route_path_not_expired_when_fresh(self):
        """Route should not be expired when recently updated."""
        route = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow()
        )
        
        assert route.is_expired is False

    def test_record_success_updates_reliability(self):
        """Recording success should update reliability score."""
        route = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow() - timedelta(seconds=30)
        )
        route.failure_count = 1
        
        route.record_success()
        
        assert route.success_count == 1
        assert route.reliability == 0.5  # 1 success / 2 total

    def test_record_failure_updates_reliability(self):
        """Recording failure should update reliability score."""
        route = RoutePath(
            target="controller",
            next_hop="node-002",
            next_hop_addr=("192.168.1.102", 7777),
            total_hops=1,
            estimated_rtt_ms=50.0,
            last_updated=datetime.utcnow()
        )
        route.success_count = 3
        
        route.record_failure()
        
        assert route.failure_count == 1
        assert route.reliability == 0.75  # 3 success / 4 total
