"""
Session Manager - Handles user sessions with Redis
"""
import json
import os
from typing import Dict, Any, Optional
import redis
from datetime import timedelta


class SessionManager:
    """Manages user sessions in Redis"""
    
    def __init__(self):
        # Redis connection
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            print(f"✅ Redis connected: {redis_host}:{redis_port}")
        
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}")
            print("Using in-memory fallback (data will be lost on restart)")
            self.redis_client = None
            self._memory_store = {}
        
        # Session TTL (Time To Live)
        self.session_ttl = timedelta(hours=24)  # Sessions expire after 24 hours
    
    def _get_key(self, customer_id: str) -> str:
        """Generate Redis key for customer session"""
        return f"session:{customer_id}"
    
    def get_session(self, customer_id: str) -> Dict[str, Any]:
        """
        Get session data for a customer
        Returns default session if not found
        """
        key = self._get_key(customer_id)
        
        try:
            if self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                # Fallback to memory
                if key in self._memory_store:
                    return self._memory_store[key]
        
        except Exception as e:
            print(f"Error getting session for {customer_id}: {e}")
        
        # Return default session
        return {
            "state": "greeting",
            "collected_data": {},
            "message_count": 0
        }
    
    def update_session(self, customer_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Update session data for a customer
        Returns True if successful
        """
        key = self._get_key(customer_id)
        
        # Increment message count
        session_data["message_count"] = session_data.get("message_count", 0) + 1
        
        try:
            if self.redis_client:
                # Store in Redis with TTL
                self.redis_client.setex(
                    key,
                    self.session_ttl,
                    json.dumps(session_data)
                )
            else:
                # Fallback to memory
                self._memory_store[key] = session_data
            
            return True
        
        except Exception as e:
            print(f"Error updating session for {customer_id}: {e}")
            return False
    
    def delete_session(self, customer_id: str) -> bool:
        """
        Delete session for a customer
        Returns True if successful
        """
        key = self._get_key(customer_id)
        
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                if key in self._memory_store:
                    del self._memory_store[key]
            
            return True
        
        except Exception as e:
            print(f"Error deleting session for {customer_id}: {e}")
            return False
    
    def check_health(self) -> bool:
        """Check if Redis is healthy"""
        try:
            if self.redis_client:
                self.redis_client.ping()
                return True
            return False
        except:
            return False
    
    def get_all_sessions(self) -> Dict[str, Any]:
        """Get all active sessions (for debugging)"""
        sessions = {}
        
        try:
            if self.redis_client:
                keys = self.redis_client.keys("session:*")
                for key in keys:
                    customer_id = key.replace("session:", "")
                    data = self.redis_client.get(key)
                    if data:
                        sessions[customer_id] = json.loads(data)
            else:
                for key, data in self._memory_store.items():
                    customer_id = key.replace("session:", "")
                    sessions[customer_id] = data
        
        except Exception as e:
            print(f"Error getting all sessions: {e}")
        
        return sessions
