"""
Session Manager - Redis-backed session storage with TTL
Handles customer conversation state persistence

Author: Intynet Team
Version: 2.0.0
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import timedelta

import redis

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages customer sessions in Redis with automatic expiration.
    Falls back to in-memory storage if Redis is unavailable.
    """

    # Default session for new customers
    DEFAULT_SESSION = {
        "state": "detect",
        "collected_data": {},
        "message_count": 0
    }

    def __init__(self):
        """Initialize Redis connection"""
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # Session TTL - default 1 hour (shorter for better UX)
        ttl_hours = float(os.getenv("SESSION_TTL_HOURS", "1"))
        self.session_ttl = timedelta(hours=ttl_hours)

        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.redis_client.ping()
            logger.info(f"✅ Redis connected: {redis_host}:{redis_port}")
            self._use_redis = True
            
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable: {e}")
            logger.warning("Using in-memory storage (data lost on restart)")
            self.redis_client = None
            self._use_redis = False
            self._memory_store: Dict[str, str] = {}

    def _get_key(self, customer_id: str) -> str:
        """Generate Redis key"""
        return f"session:{customer_id}"

    def get_session(self, customer_id: str) -> Dict[str, Any]:
        """
        Get session for a customer.
        Returns default session if not found.
        """
        key = self._get_key(customer_id)

        try:
            if self._use_redis:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                if key in self._memory_store:
                    return json.loads(self._memory_store[key])
        except Exception as e:
            logger.error(f"Error getting session: {e}")

        return self.DEFAULT_SESSION.copy()

    def update_session(self, customer_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Update session for a customer with TTL.
        """
        key = self._get_key(customer_id)
        
        try:
            data = json.dumps(session_data)
            
            if self._use_redis:
                self.redis_client.setex(key, self.session_ttl, data)
            else:
                self._memory_store[key] = data
                
            logger.debug(f"Session updated: {customer_id} → {session_data.get('state')}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            return False

    def delete_session(self, customer_id: str) -> bool:
        """Delete/reset session for a customer"""
        key = self._get_key(customer_id)

        try:
            if self._use_redis:
                self.redis_client.delete(key)
            else:
                self._memory_store.pop(key, None)
            
            logger.info(f"Session deleted: {customer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    def check_health(self) -> bool:
        """Check Redis health"""
        if not self._use_redis:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    def get_all_sessions(self) -> Dict[str, Any]:
        """Get all active sessions (for admin/debug)"""
        sessions = {}

        try:
            if self._use_redis:
                keys = self.redis_client.keys("session:*")
                for key in keys:
                    customer_id = key.replace("session:", "")
                    data = self.redis_client.get(key)
                    if data:
                        sessions[customer_id] = json.loads(data)
            else:
                for key, data in self._memory_store.items():
                    customer_id = key.replace("session:", "")
                    sessions[customer_id] = json.loads(data)
                    
        except Exception as e:
            logger.error(f"Error getting all sessions: {e}")

        return sessions

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Redis and session statistics.
        Useful for monitoring.
        """
        stats = {
            "storage": "redis" if self._use_redis else "memory",
            "ttl_hours": self.session_ttl.total_seconds() / 3600,
            "healthy": self.check_health()
        }

        try:
            if self._use_redis:
                # Get Redis memory info
                info = self.redis_client.info("memory")
                stats.update({
                    "used_memory": info.get("used_memory_human", "N/A"),
                    "peak_memory": info.get("used_memory_peak_human", "N/A"),
                    "total_keys": self.redis_client.dbsize(),
                    "session_count": len(self.redis_client.keys("session:*"))
                })
            else:
                stats.update({
                    "session_count": len(self._memory_store),
                    "total_keys": len(self._memory_store)
                })
                
        except Exception as e:
            stats["error"] = str(e)

        return stats

    def cleanup_escalated(self, older_than_hours: float = 24) -> int:
        """
        Clean up escalated sessions older than specified hours.
        Call this periodically if needed.
        
        Returns number of cleaned sessions.
        """
        # With Redis TTL, this is handled automatically
        # This method is for manual cleanup if needed
        
        if not self._use_redis:
            return 0
            
        cleaned = 0
        try:
            keys = self.redis_client.keys("session:*")
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    session = json.loads(data)
                    if session.get("state") == "escalated":
                        ttl = self.redis_client.ttl(key)
                        # If TTL is very short, it will expire soon anyway
                        if ttl < 60:  # Less than 1 minute left
                            self.redis_client.delete(key)
                            cleaned += 1
                            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            
        return cleaned
