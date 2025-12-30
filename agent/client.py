# Copyright 2024 TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
HTTP client for TacticalMesh Node Agent.

Provides resilient communication with the Mesh Controller, including
retry logic, exponential backoff, and connection failover.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class CommandInfo:
    """Command information from controller."""
    id: str
    command_type: str
    payload: Optional[Dict[str, Any]]
    created_at: str


class ControllerClient:
    """
    HTTP client for communicating with the Mesh Controller.
    
    Features:
    - Automatic retry with exponential backoff
    - Controller URL failover
    - Connection pooling
    - Request/response logging
    """
    
    def __init__(self, config: AgentConfig):
        """
        Initialize the controller client.
        
        Args:
            config: Agent configuration
        """
        self.config = config
        self.auth_token: Optional[str] = config.auth_token
        self._current_url_index = 0
        self._session = self._create_session()
        
        # Build list of controller URLs
        self._controller_urls = [config.controller.primary_url]
        self._controller_urls.extend(config.controller.backup_urls)
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_base,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    @property
    def current_controller_url(self) -> str:
        """Get the current controller URL."""
        return self._controller_urls[self._current_url_index]
    
    def _switch_controller(self):
        """Switch to the next available controller URL."""
        self._current_url_index = (self._current_url_index + 1) % len(self._controller_urls)
        logger.warning(f"Switching to controller: {self.current_controller_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"TacticalMesh-Agent/{self.config.node_id}"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Make an HTTP request to the controller.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body data
            retry_count: Current retry attempt
            
        Returns:
            Response data or None if failed
        """
        url = f"{self.current_controller_url}{endpoint}"
        
        try:
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                headers=self._get_headers(),
                timeout=self.config.controller.timeout_seconds,
                verify=self.config.controller.verify_ssl
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            if len(self._controller_urls) > 1:
                self._switch_controller()
            return None
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout to {url}: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from {url}: {e.response.status_code} - {e.response.text}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in request to {url}: {e}")
            return None
    
    def register(
        self,
        ip_address: Optional[str] = None,
        mac_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Register this node with the controller.
        
        Args:
            ip_address: Node's IP address
            mac_address: Node's MAC address
            metadata: Additional metadata
            
        Returns:
            Authentication token if successful, None otherwise
        """
        logger.info(f"Registering node {self.config.node_id} with controller")
        
        data = {
            "node_id": self.config.node_id,
            "name": self.config.name,
            "node_type": self.config.node_type,
            "ip_address": ip_address,
            "mac_address": mac_address,
            "metadata": metadata
        }
        
        response = self._make_request("POST", "/api/v1/nodes/register", data)
        
        if response and "auth_token" in response:
            self.auth_token = response["auth_token"]
            logger.info(f"Node registered successfully: {response.get('id')}")
            return self.auth_token
        
        logger.error("Failed to register node")
        return None
    
    def heartbeat(
        self,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        disk_usage: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        custom_metrics: Optional[Dict] = None
    ) -> Optional[List[CommandInfo]]:
        """
        Send heartbeat with telemetry data.
        
        Args:
            cpu_usage: CPU usage percentage
            memory_usage: Memory usage percentage
            disk_usage: Disk usage percentage
            latitude: GPS latitude
            longitude: GPS longitude
            altitude: GPS altitude
            custom_metrics: Additional metrics
            
        Returns:
            List of pending commands if successful, None otherwise
        """
        data = {
            "node_id": self.config.node_id,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "disk_usage": disk_usage,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "custom_metrics": custom_metrics
        }
        
        response = self._make_request("POST", "/api/v1/nodes/heartbeat", data)
        
        if response:
            pending_commands = []
            for cmd in response.get("pending_commands", []):
                pending_commands.append(CommandInfo(
                    id=cmd["id"],
                    command_type=cmd["command_type"],
                    payload=cmd.get("payload"),
                    created_at=cmd["created_at"]
                ))
            return pending_commands
        
        return None
    
    def report_command_result(
        self,
        command_id: str,
        status: str,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Report command execution result to controller.
        
        Args:
            command_id: Command UUID
            status: Command status (acknowledged, completed, failed)
            result: Execution result data
            error_message: Error message if failed
            
        Returns:
            True if successful, False otherwise
        """
        data = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error_message": error_message
        }
        
        response = self._make_request("POST", f"/api/v1/commands/{command_id}/result", data)
        return response is not None
    
    def close(self):
        """Close the HTTP session."""
        self._session.close()
