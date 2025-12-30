# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Mesh networking module for TacticalMesh agent.

This module provides peer-to-peer mesh networking capabilities including:
- Peer discovery and status tracking (peering.py)
- Multi-hop routing with automatic failover (routing.py)
"""

from .peering import MeshPeering, PeerInfo, PeerStatus
from .routing import MeshRouter, RoutePath, RelayMessage

__all__ = [
    "MeshPeering",
    "PeerInfo", 
    "PeerStatus",
    "MeshRouter",
    "RoutePath",
    "RelayMessage",
]
