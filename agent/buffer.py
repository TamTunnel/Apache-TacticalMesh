# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Local buffering module for TacticalMesh agent.

Provides resilient buffering of telemetry and command results when the
controller is unreachable, with automatic flush when connectivity is restored.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from queue import Queue, Empty
import time

logger = logging.getLogger(__name__)


@dataclass
class BufferedItem:
    """An item stored in the local buffer."""
    item_type: str  # "telemetry" or "command_result"
    data: Dict[str, Any]
    timestamp: str
    attempt_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BufferedItem":
        return cls(**d)


class LocalBuffer:
    """
    Local buffer for storing telemetry and command results during disconnection.
    
    This buffer provides resilience when the controller is unreachable:
    - Stores pending telemetry data
    - Stores command execution results
    - Persists to disk to survive agent restarts
    - Flushes automatically when connectivity is restored
    
    Configuration example (in agent config.yaml):
    
        buffer:
          enabled: true
          max_items: 1000
          persist_path: /var/lib/tacticalmesh/buffer.json
          flush_batch_size: 50
    
    Attributes:
        max_items: Maximum number of items to buffer (oldest dropped when exceeded)
        persist_path: Path to persist buffer to disk (optional)
        items: List of buffered items
    """
    
    def __init__(
        self,
        max_items: int = 1000,
        persist_path: Optional[str] = None,
        flush_batch_size: int = 50
    ):
        """
        Initialize the local buffer.
        
        Args:
            max_items: Maximum items to buffer before dropping oldest
            persist_path: Optional path to persist buffer to disk
            flush_batch_size: Number of items to flush in each batch
        """
        self.max_items = max_items
        self.persist_path = persist_path
        self.flush_batch_size = flush_batch_size
        
        self.items: List[BufferedItem] = []
        self._lock = threading.Lock()
        
        # Load from disk if available
        if persist_path:
            self._load_from_disk()
        
        logger.info(
            f"LocalBuffer initialized: max_items={max_items}, "
            f"persist_path={persist_path or 'none'}, "
            f"current_items={len(self.items)}"
        )
    
    def add_telemetry(self, telemetry_data: Dict[str, Any]) -> None:
        """
        Add telemetry data to the buffer.
        
        Args:
            telemetry_data: Telemetry payload that would be sent to controller
        """
        self._add_item("telemetry", telemetry_data)
    
    def add_command_result(self, command_id: str, result: Dict[str, Any]) -> None:
        """
        Add a command result to the buffer.
        
        Args:
            command_id: ID of the command that was executed
            result: Execution result to report
        """
        self._add_item("command_result", {
            "command_id": command_id,
            "result": result
        })
    
    def _add_item(self, item_type: str, data: Dict[str, Any]) -> None:
        """Add an item to the buffer."""
        item = BufferedItem(
            item_type=item_type,
            data=data,
            timestamp=datetime.utcnow().isoformat()
        )
        
        with self._lock:
            self.items.append(item)
            
            # Drop oldest items if over limit
            if len(self.items) > self.max_items:
                dropped = len(self.items) - self.max_items
                self.items = self.items[dropped:]
                logger.warning(f"Buffer full, dropped {dropped} oldest items")
            
            # Persist to disk
            if self.persist_path:
                self._save_to_disk()
        
        logger.debug(f"Buffered {item_type}: {len(self.items)} items total")
    
    def get_pending_count(self) -> Dict[str, int]:
        """Get count of pending items by type."""
        with self._lock:
            counts = {"telemetry": 0, "command_result": 0, "total": len(self.items)}
            for item in self.items:
                counts[item.item_type] = counts.get(item.item_type, 0) + 1
            return counts
    
    def get_items_to_flush(self, item_type: Optional[str] = None) -> List[BufferedItem]:
        """
        Get a batch of items to flush.
        
        Args:
            item_type: Optional filter by type ("telemetry" or "command_result")
            
        Returns:
            List of items to send (up to flush_batch_size)
        """
        with self._lock:
            if item_type:
                filtered = [i for i in self.items if i.item_type == item_type]
            else:
                filtered = self.items.copy()
            
            return filtered[:self.flush_batch_size]
    
    def mark_flushed(self, items: List[BufferedItem]) -> None:
        """
        Remove successfully flushed items from the buffer.
        
        Args:
            items: Items that were successfully sent to the controller
        """
        flushed_set = {(i.item_type, i.timestamp) for i in items}
        
        with self._lock:
            original_count = len(self.items)
            self.items = [
                i for i in self.items 
                if (i.item_type, i.timestamp) not in flushed_set
            ]
            removed = original_count - len(self.items)
            
            if self.persist_path:
                self._save_to_disk()
        
        logger.info(f"Flushed {removed} items from buffer, {len(self.items)} remaining")
    
    def mark_failed(self, items: List[BufferedItem]) -> None:
        """
        Mark items as failed (increment retry counter).
        
        Args:
            items: Items that failed to flush
        """
        failed_set = {(i.item_type, i.timestamp) for i in items}
        
        with self._lock:
            for item in self.items:
                if (item.item_type, item.timestamp) in failed_set:
                    item.attempt_count += 1
            
            if self.persist_path:
                self._save_to_disk()
    
    def clear(self) -> int:
        """
        Clear all buffered items.
        
        Returns:
            Number of items cleared
        """
        with self._lock:
            count = len(self.items)
            self.items = []
            
            if self.persist_path:
                self._save_to_disk()
        
        logger.info(f"Buffer cleared: {count} items removed")
        return count
    
    def _save_to_disk(self) -> None:
        """Persist buffer to disk."""
        if not self.persist_path:
            return
        
        try:
            path = Path(self.persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "items": [item.to_dict() for item in self.items],
                "saved_at": datetime.utcnow().isoformat()
            }
            
            # Write atomically via temp file
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, 'w') as f:
                json.dump(data, f)
            temp_path.replace(path)
            
        except Exception as e:
            logger.error(f"Failed to persist buffer to disk: {e}")
    
    def _load_from_disk(self) -> None:
        """Load buffer from disk."""
        if not self.persist_path:
            return
        
        path = Path(self.persist_path)
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.items = [BufferedItem.from_dict(d) for d in data.get("items", [])]
            saved_at = data.get("saved_at", "unknown")
            logger.info(f"Loaded {len(self.items)} buffered items from disk (saved: {saved_at})")
            
        except Exception as e:
            logger.error(f"Failed to load buffer from disk: {e}")
            self.items = []
    
    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self.items) == 0
    
    @property  
    def size(self) -> int:
        """Current number of buffered items."""
        return len(self.items)
