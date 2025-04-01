# Standard library imports
import asyncio
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

# Third-party imports
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv

# Local imports
from rtmt import RTMiddleTier, RTToolCall # Assuming RTToolCall is defined in rtmt
from job_search import JobSearchTool
from job_tools import get_tool_definitions, ToolDefinition
from ui_state import UIState, ViewMode

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
    client_ws: Optional[web.WebSocketResponse] = None # Renamed from state_ws, now holds the main client WS
    pending_tools: Dict[str, RTToolCall] = field(default_factory=dict)

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
        except Exception as e:
            logger.error(f"Session {self.session_id}: Error processing UI message '{message_type}': {e}")


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


# Global session management
SESSIONS: Dict[str, SessionState] = {}

def get_or_create_session(session_id: str) -> SessionState:
    """Retrieves an existing session or creates a new one."""
    if session_id not in SESSIONS:
        logger.info(f"Creating new session: {session_id}")
        SESSIONS[session_id] = SessionState(session_id=session_id)
    return SESSIONS[session_id]

def cleanup_session(session_id: str) -> None:
    """Removes a session when it's no longer needed."""
    if session_id in SESSIONS:
        logger.info(f"Cleaning up session: {session_id}")
        # Close the client WebSocket if it's still open
        if SESSIONS[session_id].client_ws and not SESSIONS[session_id].client_ws.closed:
            asyncio.create_task(SESSIONS[session_id].client_ws.close())
        del SESSIONS[session_id]

async def create_app() -> web.Application:
    """Create and configure the web application."""
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()

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

    # Add session cleanup task (optional, adjust frequency as needed)
    # asyncio.create_task(periodic_session_cleanup(interval=300)) # e.g., every 5 minutes

    return app

# async def periodic_session_cleanup(interval: int):
#     """Periodically cleans up inactive sessions."""
#     while True:
#         await asyncio.sleep(interval)
#         # Add logic here to identify and cleanup inactive sessions
#         # For example, check last activity time stored in SessionState
#         logger.info("Running periodic session cleanup...")
#         # ... cleanup logic ...

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
    app.router.add_get('/api/session/init', lambda _: web.json_response({"session_id": str(uuid.uuid4())}))
    
    # Realtime WebSocket (requires session ID) - Updated path
    rtmt.attach_to_app(app, "/api/ws")
    
    # Static files
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')

if __name__ == "__main__":
    web.run_app(create_app(), host=HOST, port=PORT)
