"""
Redis-based session storage for the job search agent.
Allows for distributed state management across multiple app instances.
"""

import asyncio
import json
import logging
import pickle
import uuid
import time
from typing import Dict, Any, Optional, Set, List, Callable

import redis
from redis.exceptions import RedisError

# Configure logging
logger = logging.getLogger("redis_session")

class RedisSessionManager:
    """
    Manages application sessions using Redis for distributed state storage.
    
    Provides persistent storage for session data across multiple application 
    instances, enabling horizontal scaling.
    """
    
    # Redis key prefixes
    SESSION_PREFIX = "jobsearch:session:"
    ACTIVE_SESSIONS_KEY = "jobsearch:active_sessions"
    
    # Default session expiration (24 hours)
    DEFAULT_EXPIRY = 86400
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379/0", 
                 expiry_seconds: int = DEFAULT_EXPIRY):
        """
        Initialize Redis session manager.
        
        Args:
            redis_url: Redis connection string
            expiry_seconds: Session expiration time in seconds
        """
        # Create Redis connection pool for better performance
        self.redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            decode_responses=False,  # Keep raw bytes for pickle data
            socket_timeout=5.0,      # Connection timeout
            socket_connect_timeout=5.0
        )
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.expiry = expiry_seconds
        logger.info(f"Initialized Redis session manager with {redis_url}")
        
        # Test connection
        try:
            self.redis.ping()
            logger.info("Successfully connected to Redis")
        except RedisError as e:
            logger.error(f"Redis connection test failed: {e}")
    
    def generate_session_id(self) -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())
    
    def _session_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"{self.SESSION_PREFIX}{session_id}"
    
    def get_session(self, session_id: str, create_if_missing: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get session data from Redis.
        
        Args:
            session_id: Session identifier
            create_if_missing: Create new session if not found
            
        Returns:
            Session data or None if not found and create_if_missing is False
        """
        try:
            key = self._session_key(session_id)
            data = self.redis.get(key)
            
            if data:
                try:
                    # Update expiration and last activity time
                    session = pickle.loads(data)
                    session['last_activity'] = time.time()
                    self.save_session(session_id, session)
                    return session
                except pickle.PickleError as e:
                    logger.error(f"Failed to deserialize session {session_id}: {e}")
                    if create_if_missing:
                        logger.info(f"Creating new session to replace corrupt data: {session_id}")
                        # Delete corrupt data
                        self.redis.delete(key)
                        return self._create_new_session(session_id)
                    return None
            elif create_if_missing:
                return self._create_new_session(session_id)
            return None
        except RedisError as e:
            logger.error(f"Redis error while getting session {session_id}: {e}")
            # Fall back to returning a new session
            if create_if_missing:
                return {
                    'session_id': session_id,
                    'created_at': time.time(),
                    'last_activity': time.time(),
                    'ui_state_data': {},
                    'job_search_data': {},
                    'pending_tools': {}
                }
            return None
    
    def _create_new_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new session and store it in Redis."""
        logger.info(f"Creating new session in Redis: {session_id}")
        session = {
            'session_id': session_id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ui_state_data': {},
            'job_search_data': {},
            'pending_tools': {}
        }
        self.save_session(session_id, session)
        
        # Add to active sessions set
        try:
            self.redis.sadd(self.ACTIVE_SESSIONS_KEY, session_id)
        except RedisError as e:
            logger.error(f"Failed to add session {session_id} to active sessions set: {e}")
        
        return session
    
    def save_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Save session data to Redis.
        
        Args:
            session_id: Session identifier
            data: Session data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._session_key(session_id)
            # Add session_id to the data if it's not already there
            if 'session_id' not in data:
                data['session_id'] = session_id
            
            # Update last_activity time
            data['last_activity'] = time.time()
            
            # Serialize and save with expiration
            serialized = pickle.dumps(data)
            result = self.redis.setex(key, self.expiry, serialized)
            
            # Add to active sessions set (in case it wasn't added before)
            self.redis.sadd(self.ACTIVE_SESSIONS_KEY, session_id)
            
            return result
        except pickle.PickleError as e:
            logger.error(f"Failed to serialize session {session_id}: {e}")
            return False
        except RedisError as e:
            logger.error(f"Redis error while saving session {session_id}: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._session_key(session_id)
            self.redis.delete(key)
            self.redis.srem(self.ACTIVE_SESSIONS_KEY, session_id)
            logger.info(f"Deleted session {session_id}")
            return True
        except RedisError as e:
            logger.error(f"Redis error while deleting session {session_id}: {e}")
            return False
    
    def get_active_sessions(self) -> List[str]:
        """
        Get list of all active session IDs.
        
        Returns:
            List of session IDs
        """
        try:
            sessions = self.redis.smembers(self.ACTIVE_SESSIONS_KEY)
            return [s.decode('utf-8') if isinstance(s, bytes) else s for s in sessions]
        except RedisError as e:
            logger.error(f"Redis error while getting active sessions: {e}")
            return []
    
    def check_session_exists(self, session_id: str) -> bool:
        """
        Check if a session exists in Redis.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if the session exists, False otherwise
        """
        try:
            key = self._session_key(session_id)
            return bool(self.redis.exists(key))
        except RedisError as e:
            logger.error(f"Redis error while checking session {session_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from Redis.
        
        Returns:
            Number of sessions removed
        """
        try:
            count = 0
            cutoff_time = time.time() - self.expiry
            for session_id in self.get_active_sessions():
                try:
                    key = self._session_key(session_id)
                    data = self.redis.get(key)
                    if not data:
                        # Session key doesn't exist but ID is in active set
                        self.redis.srem(self.ACTIVE_SESSIONS_KEY, session_id)
                        count += 1
                        continue
                        
                    session = pickle.loads(data)
                    if session.get('last_activity', 0) < cutoff_time:
                        self.delete_session(session_id)
                        count += 1
                except (pickle.PickleError, RedisError) as e:
                    logger.error(f"Error processing session {session_id} during cleanup: {e}")
                    # Remove problematic session
                    self.delete_session(session_id)
                    count += 1
            
            return count
        except RedisError as e:
            logger.error(f"Redis error during expired session cleanup: {e}")
            return 0