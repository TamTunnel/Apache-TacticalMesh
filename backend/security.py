# Copyright 2024 Apache TacticalMesh Contributors
# SPDX-License-Identifier: Apache-2.0
"""
Security module for Apache TacticalMesh.

Provides rate limiting, password complexity validation, account lockout,
and token revocation mechanisms.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Set
from collections import defaultdict
import threading

from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting
# =============================================================================

def get_client_ip(request: Request) -> str:
    """Get client IP for rate limiting, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Create rate limiter instance
limiter = Limiter(key_func=get_client_ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    logger.warning(f"Rate limit exceeded for {get_client_ip(request)}")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please slow down.",
        headers={"Retry-After": "60"}
    )


# =============================================================================
# Password Complexity Validation
# =============================================================================

class PasswordValidator:
    """
    Password complexity validator enforcing security requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    
    MIN_LENGTH = 8
    SPECIAL_CHARS = r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/~`]"
    
    @classmethod
    def validate(cls, password: str) -> tuple[bool, list[str]]:
        """
        Validate password complexity.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long")
        
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(cls.SPECIAL_CHARS, password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_or_raise(cls, password: str) -> None:
        """Validate password and raise HTTPException if invalid."""
        is_valid, errors = cls.validate(password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet complexity requirements",
                    "errors": errors
                }
            )


# =============================================================================
# Account Lockout
# =============================================================================

class AccountLockoutManager:
    """
    In-memory account lockout manager.
    
    Tracks failed login attempts and locks accounts after threshold exceeded.
    For production, consider using Redis for distributed lockout tracking.
    """
    
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    def __init__(self):
        self._failed_attempts: dict[str, list[datetime]] = defaultdict(list)
        self._lockouts: dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def _cleanup_old_attempts(self, username: str) -> None:
        """Remove attempts older than lockout duration."""
        cutoff = datetime.utcnow() - timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
        self._failed_attempts[username] = [
            attempt for attempt in self._failed_attempts[username]
            if attempt > cutoff
        ]
    
    def is_locked_out(self, username: str) -> bool:
        """Check if account is currently locked out."""
        with self._lock:
            if username in self._lockouts:
                lockout_until = self._lockouts[username]
                if datetime.utcnow() < lockout_until:
                    return True
                else:
                    # Lockout expired, remove it
                    del self._lockouts[username]
                    self._failed_attempts[username] = []
            return False
    
    def get_lockout_remaining(self, username: str) -> Optional[int]:
        """Get remaining lockout time in seconds."""
        with self._lock:
            if username in self._lockouts:
                remaining = (self._lockouts[username] - datetime.utcnow()).total_seconds()
                if remaining > 0:
                    return int(remaining)
        return None
    
    def record_failed_attempt(self, username: str) -> bool:
        """
        Record a failed login attempt.
        
        Returns:
            True if account is now locked out, False otherwise
        """
        with self._lock:
            self._cleanup_old_attempts(username)
            self._failed_attempts[username].append(datetime.utcnow())
            
            if len(self._failed_attempts[username]) >= self.MAX_FAILED_ATTEMPTS:
                lockout_until = datetime.utcnow() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
                self._lockouts[username] = lockout_until
                logger.warning(f"Account locked: {username} until {lockout_until}")
                return True
            
            return False
    
    def clear_attempts(self, username: str) -> None:
        """Clear failed attempts after successful login."""
        with self._lock:
            self._failed_attempts[username] = []
            if username in self._lockouts:
                del self._lockouts[username]
    
    def get_remaining_attempts(self, username: str) -> int:
        """Get remaining login attempts before lockout."""
        with self._lock:
            self._cleanup_old_attempts(username)
            return max(0, self.MAX_FAILED_ATTEMPTS - len(self._failed_attempts[username]))


# Global lockout manager instance
lockout_manager = AccountLockoutManager()


# =============================================================================
# Token Revocation (Simple In-Memory Implementation)
# =============================================================================

class TokenRevocationList:
    """
    In-memory token revocation list.
    
    For production, use Redis or a database for persistence and scalability.
    Tokens are stored with their expiration time for automatic cleanup.
    """
    
    def __init__(self):
        self._revoked_tokens: dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def revoke(self, token_jti: str, expires_at: datetime) -> None:
        """Add a token to the revocation list."""
        with self._lock:
            self._revoked_tokens[token_jti] = expires_at
            self._cleanup_expired()
    
    def is_revoked(self, token_jti: str) -> bool:
        """Check if a token has been revoked."""
        with self._lock:
            return token_jti in self._revoked_tokens
    
    def _cleanup_expired(self) -> None:
        """Remove expired tokens from the revocation list."""
        now = datetime.utcnow()
        self._revoked_tokens = {
            jti: exp for jti, exp in self._revoked_tokens.items()
            if exp > now
        }


# Global token revocation list
token_revocation_list = TokenRevocationList()
