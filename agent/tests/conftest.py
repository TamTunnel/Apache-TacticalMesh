# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Pytest fixtures for TacticalMesh agent tests.

Provides mock objects and sample data for testing mesh routing functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add agent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mesh.peering import MeshPeering, PeerInfo, PeerStatus
from mesh.routing import MeshRouter, RoutePath, RelayMessage


@pytest.fixture
def mock_controller_client():
    """Mock controller client for testing."""
    client = Mock()
    client.heartbeat = Mock(return_value=[])
    client.report_command_result = Mock(return_value=True)
    client.last_success = datetime.utcnow()
    return client


@pytest.fixture
def mock_socket():
    """Mock UDP socket for mesh communication."""
    sock = Mock()
    sock.sendto = Mock(return_value=None)
    sock.recvfrom = Mock(return_value=(b'', ('127.0.0.1', 7777)))
    return sock


@pytest.fixture
def mock_peering(mock_socket):
    """Mock mesh peering with sample peers."""
    peering = Mock(spec=MeshPeering)
    peering._socket = mock_socket
    peering.node_id = "test-node-001"
    peering.peers = {}
    peering.get_reachable_peers = Mock(return_value=[])
    return peering


@pytest.fixture
def sample_peers():
    """Sample peer nodes for testing various scenarios."""
    return [
        PeerInfo(
            node_id="node-002",
            address="192.168.1.102",
            port=7777,
            status=PeerStatus.REACHABLE,
            last_seen=datetime.utcnow(),
            rtt_ms=50.0
        ),
        PeerInfo(
            node_id="node-003",
            address="192.168.1.103",
            port=7777,
            status=PeerStatus.REACHABLE,
            last_seen=datetime.utcnow(),
            rtt_ms=150.0
        ),
        PeerInfo(
            node_id="node-004",
            address="192.168.1.104",
            port=7777,
            status=PeerStatus.UNREACHABLE,
            last_seen=datetime.utcnow() - timedelta(seconds=120),
            rtt_ms=None
        )
    ]


@pytest.fixture
def mesh_router(mock_controller_client, mock_peering):
    """Create mesh router for testing."""
    router = MeshRouter(
        node_id="test-node-001",
        peering=mock_peering,
        controller_client=mock_controller_client,
        route_cache_ttl=60,
        max_hops=5
    )
    return router


@pytest.fixture
def sample_route_path():
    """Sample route path for testing."""
    return RoutePath(
        target="controller",
        next_hop="node-002",
        next_hop_addr=("192.168.1.102", 7777),
        total_hops=1,
        estimated_rtt_ms=50.0,
        last_updated=datetime.utcnow(),
        reliability=1.0
    )


@pytest.fixture
def sample_relay_message():
    """Sample relay message for testing."""
    return RelayMessage(
        message_id="test-msg-001",
        msg_type="heartbeat",
        origin_node_id="node-001",
        destination="controller",
        hop_count=0,
        max_hops=5,
        payload={
            "node_id": "node-001",
            "cpu_usage": 45.0,
            "memory_usage": 60.0,
            "disk_usage": 30.0
        },
        path_trace=["node-001"],
        timestamp=datetime.utcnow().isoformat()
    )


@pytest.fixture
def expired_route_path():
    """Expired route path for testing cache expiry."""
    return RoutePath(
        target="controller",
        next_hop="node-002",
        next_hop_addr=("192.168.1.102", 7777),
        total_hops=1,
        estimated_rtt_ms=50.0,
        last_updated=datetime.utcnow() - timedelta(seconds=120),  # 2 minutes old
        reliability=1.0
    )
