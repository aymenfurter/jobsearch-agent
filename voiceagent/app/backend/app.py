# Standard library imports
import asyncio
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set, ClassVar

# Third-party imports
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv

# Local imports
from rtmt import RTMiddleTier, RTToolCall
from job_search import JobSearchTool
from job_tools import get_tool_definitions, ToolDefinition
from ui_state import UIState, ViewMode
from redis_session import RedisSessionManager

# Constants
HOST = "localhost"
PORT = random.randint(8766, 10000)
SYSTEM_MESSAGE = """Start by greeting the user and asking what kind of job they're looking for.
You are a job search assistant. Help users search for jobs at Microsoft and display the results.
Before searching, make sure to ask:
1) What job role/title they're interested in
2) Which country they want to work in (optional)
"""

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobsearch")

@dataclass
class SessionState:
    """Holds the state for a single user session."""
    session_id: str
    ui_state: UIState = field(default_factory=UIState)
    job_search: Optional[JobSearchTool] = None
    client_ws: Optional[web.WebSocketResponse] = None
    pending_tools: Dict[str, RTToolCall] = field(default_factory=dict)
    
    # Class variable to store the Redis session manager
    redis_manager: ClassVar[Optional[RedisSessionManager]] = None

    def __post_init__(self):
        # Initialize JobSearchTool after UIState is created
        self.job_search = JobSearchTool(self.ui_state)
        # Link reset methods
        original_reset = self.ui_state.reset_state
        def reset_all_state():
            if self.job_search:
                self.job_search.reset_state()
            original_reset()
        self.ui_state.reset_state = reset_all_state

    async def handle_ui_message(self, data: Dict[str, Any]) -> None:
        """Handle messages originating from the UI, received via the main WebSocket."""
        message_type = data.get('type')
        try:
            if message_type == 'reset_state':
                self.ui_state.reset_state()
            elif message_type == 'manual_search':
                await self.handle_manual_search(data)
            elif message_type == 'select_job':
                await self.handle_job_selection(data)
            elif message_type == 'view_search_results':
                await self.handle_view_change()
            # Add other UI message types here if needed
            else:
                logger.warning(f"Session {self.session_id}: Received unknown UI message type: {message_type}")
            
            # After handling a message, persist state to Redis
            self.save_to_redis()
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error processing UI message '{message_type}': {e}")

    def save_to_redis(self) -> None:
        """Serialize and save session state to Redis."""
        if not self.redis_manager:
            logger.warning(f"Session {self.session_id}: Cannot save to Redis - no manager configured")
            return
            
        try:
            # Create serializable session data
            session_data = {
                'session_id': self.session_id,
                'ui_state_data': self.ui_state.get_state(),
                'job_search_data': {
                    'current_job': self.job_search.current_job if self.job_search else None,
                    'search_query': self.job_search.search_query if self.job_search else None,
                    'search_country': self.job_search.search_country if self.job_search else None,
                },
                # We don't serialize pending_tools as they are ephemeral and client_ws which can't be serialized
                'pending_tools': {},  # Only keys stored, not actual tool call objects
                'last_activity': time.time(),
            }
            
            # Store pending tool IDs (not objects)
            if self.pending_tools:
                session_data['pending_tools'] = {k: True for k in self.pending_tools.keys()}
                
            # Save to Redis
            self.redis_manager.save_session(self.session_id, session_data)
        except Exception as e:
            logger.error(f"Session {self.session_id}: Failed to save to Redis: {e}")

    @classmethod
    def load_from_redis(cls, session_id: str) -> Optional['SessionState']:
        """
        Reconstruct session state from Redis data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Reconstructed SessionState object or None if not found
        """
        if not cls.redis_manager:
            logger.warning(f"Cannot load session {session_id} - no Redis manager configured")
            return None
            
        try:
            # Get raw data from Redis
            session_data = cls.redis_manager.get_session(session_id, create_if_missing=False)
            if not session_data:
                logger.info(f"No session data found in Redis for session {session_id}")
                return None
                
            # Create new SessionState
            session = cls(session_id=session_id)
            
            # Restore UI state using the new set_state_from_dict method
            if ui_state_data := session_data.get('ui_state_data'):
                session.ui_state.set_state_from_dict(ui_state_data)
            
            # Restore JobSearchTool state
            if job_search_data := session_data.get('job_search_data'):
                if job_search_data.get('current_job'):
                    session.job_search.current_job = job_search_data.get('current_job')
                if job_search_data.get('search_query'):
                    session.job_search.search_query = job_search_data.get('search_query')
                if 'search_country' in job_search_data:
                    session.job_search.search_country = job_search_data.get('search_country')
            
            logger.info(f"Successfully restored session {session_id} from Redis")
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id} from Redis: {e}", exc_info=True)
            return None

    async def handle_manual_search(self, data: Dict[str, Any]) -> None:
        """Handle manual job search requests."""
        search_data = data.get('data', {})
        query = search_data.get('query')
        country = search_data.get('country')
        
        if query and self.job_search:
            self.job_search.search_jobs(query, country)

    async def handle_job_selection(self, data: Dict[str, Any]) -> None:
        """Handle job selection requests."""
        job_data = data.get('data', {})
        job_id = job_data.get('job_id')
        
        if job_id and self.job_search:
            self.job_search.display_job(job_id)

    async def handle_view_change(self) -> None:
        """Handle view mode changes (e.g., back to search results)."""
        # Use the new reset_view method if available, otherwise set mode directly
        if hasattr(self.ui_state, 'reset_view'):
             self.ui_state.reset_view()
        else:
             self.ui_state.view_mode = ViewMode.SEARCH.value
             self.ui_state._notify_listeners() # Manually notify if reset_view doesn't exist

# Initialize Redis session manager
session_manager = None

# Import time here to avoid circular imports
import time

def get_or_create_session(session_id: str) -> SessionState:
    """Retrieves an existing session or creates a new one using Redis."""
    global session_manager
    
    # First, check if we have the session already loaded in memory
    session = _get_memory_cached_session(session_id)
    if session:
        return session
        
    # Try to load from Redis
    redis_session = SessionState.load_from_redis(session_id)
    if redis_session:
        # Cache in memory for faster access
        _cache_session(redis_session)
        return redis_session
        
    # Create a new session
    logger.info(f"Creating new session: {session_id}")
    new_session = SessionState(session_id=session_id)
    _cache_session(new_session)
    new_session.save_to_redis()
    return new_session

# Memory cache for active sessions (for performance)
# This is just a performance optimization; Redis is the source of truth
_MEMORY_CACHE: Dict[str, SessionState] = {}

def _get_memory_cached_session(session_id: str) -> Optional[SessionState]:
    """Get a session from the memory cache if available."""
    return _MEMORY_CACHE.get(session_id)

def _cache_session(session: SessionState) -> None:
    """Add a session to the memory cache."""
    _MEMORY_CACHE[session.session_id] = session

def cleanup_session(session_id: str) -> None:
    """Removes a session both from memory cache and Redis."""
    global session_manager
    
    if session_id in _MEMORY_CACHE:
        logger.info(f"Cleaning up session from memory cache: {session_id}")
        # Close the client WebSocket if it's still open
        if _MEMORY_CACHE[session_id].client_ws and not _MEMORY_CACHE[session_id].client_ws.closed:
            asyncio.create_task(_MEMORY_CACHE[session_id].client_ws.close())
        del _MEMORY_CACHE[session_id]
    
    # Also remove from Redis (if manager is available)
    if session_manager:
        logger.info(f"Removing session from Redis: {session_id}")
        session_manager.delete_session(session_id)

async def periodic_session_cleanup(interval: int = 3600):
    """
    Periodically cleans up expired sessions from Redis.
    
    Args:
        interval: Cleanup interval in seconds (default: 1 hour)
    """
    global session_manager
    
    while True:
        try:
            await asyncio.sleep(interval)
            if session_manager:
                logger.info("Running periodic Redis session cleanup...")
                removed = await session_manager.cleanup_expired_sessions()
                logger.info(f"Removed {removed} expired sessions from Redis")
                
                # Also clean memory cache of expired sessions
                # This matches what's in Redis after cleanup
                active_sessions = session_manager.get_active_sessions()
                expired = set(_MEMORY_CACHE.keys()) - set(active_sessions)
                for sid in expired:
                    if sid in _MEMORY_CACHE:
                        del _MEMORY_CACHE[sid]
                logger.info(f"Removed {len(expired)} expired sessions from memory cache")
        except Exception as e:
            logger.error(f"Error during periodic session cleanup: {e}")

async def create_app() -> web.Application:
    """Create and configure the web application."""
    global session_manager
    
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()

    # Configure Redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    session_expiry = int(os.environ.get("SESSION_EXPIRY_SECONDS", "86400"))
    
    # Initialize Redis session manager
    try:
        session_manager = RedisSessionManager(redis_url=redis_url, expiry_seconds=session_expiry)
        # Make available to SessionState class
        SessionState.redis_manager = session_manager
        logger.info(f"Connected to Redis at {redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.warning("Falling back to in-memory session storage only")
        
    llm_credential = _get_credentials()
    app = web.Application()
    
    # Get tool definitions
    tool_definitions = get_tool_definitions()
    
    rtmt = RTMiddleTier(
        credentials=llm_credential,
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment=os.environ["AZURE_OPENAI_REALTIME_DEPLOYMENT"],
        voice_choice=os.environ.get("AZURE_OPENAI_REALTIME_VOICE_CHOICE") or "echo",
        tool_definitions=tool_definitions,
        session_provider=get_or_create_session # Pass the session provider function
    )
    rtmt.config.system_message = SYSTEM_MESSAGE # Set system message on config

    _setup_routes(app, rtmt)

    # Start session cleanup task if Redis is available
    if session_manager:
        cleanup_interval = int(os.environ.get("SESSION_CLEANUP_INTERVAL_SECONDS", "3600"))
        asyncio.create_task(periodic_session_cleanup(interval=cleanup_interval))

    return app

def _get_credentials() -> AzureKeyCredential | DefaultAzureCredential:
    """Get Azure credentials based on environment configuration."""
    llm_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not llm_key:
        if tenant_id := os.environ.get("AZURE_TENANT_ID"):
            logger.info("Using AzureDeveloperCliCredential with tenant_id %s", tenant_id)
            return AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
        logger.info("Using DefaultAzureCredential")
        return DefaultAzureCredential()
    return AzureKeyCredential(llm_key)

def _setup_routes(app: web.Application, rtmt: RTMiddleTier) -> None:
    """Configure application routes."""
    current_directory = Path(__file__).parent
    
    # Add route for generating session ID
    async def init_session(request):
        """Initialize a new session and return the ID."""
        if session_manager:
            new_id = session_manager.generate_session_id()
            # Pre-create the session in Redis
            session_manager.get_session(new_id)
        else:
            new_id = str(uuid.uuid4())
        return web.json_response({"session_id": new_id})
        
    app.router.add_get('/api/session/init', init_session)
    
    # Add route for listing all active sessions from Redis
    async def list_sessions(request):
        """Get all active sessions from Redis."""
        if not session_manager:
            return web.json_response({"sessions": []})
        
        try:
            # Get active sessions from Redis
            session_ids = session_manager.get_active_sessions()
            sessions = []
            
            for sid in session_ids:
                session_data = session_manager.get_session(sid, create_if_missing=False)
                if session_data:
                    # Extract basic info about each session
                    created_at = session_data.get('created_at', 0)
                    last_activity = session_data.get('last_activity', 0)
                    search_query = None
                    
                    # Try to extract the current search query if available
                    if ui_state_data := session_data.get('ui_state_data'):
                        if search_data := ui_state_data.get('search'):
                            search_query = search_data.get('query')
                    
                    sessions.append({
                        "id": sid,
                        "created_at": created_at,
                        "last_activity": last_activity,
                        "search_query": search_query
                    })
            
            return web.json_response({"sessions": sessions})
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    app.router.add_get('/api/sessions', list_sessions)
    
    # Realtime WebSocket (requires session ID)
    rtmt.attach_to_app(app, "/api/ws")
    
    # Static files
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')

if __name__ == "__main__":
    web.run_app(create_app(), host=HOST, port=PORT)
