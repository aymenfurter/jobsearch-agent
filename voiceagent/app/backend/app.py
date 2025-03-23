# Standard library imports
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Third-party imports
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Local imports
from rtmt import RTMiddleTier
from job_search import JobSearchTool
from job_tools import attach_job_tools
from ui_state import UIState

# Constants
HOST = "localhost"
PORT = 8765
SYSTEM_MESSAGE = """Start by greeting the user and asking what kind of job they're looking for.
You are a job search assistant. Help users search for jobs at Microsoft and display the results.
Before searching, make sure to ask:
1) What job role/title they're interested in
2) Which country they want to work in (optional)
"""

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobsearch")

async def handle_manual_search(data: Dict[str, Any], job_search: JobSearchTool) -> None:
    """Handle manual job search requests."""
    search_data = data.get('data', {})
    query = search_data.get('query')
    country = search_data.get('country')
    
    if query:
        job_search.search_jobs(query, country)

async def handle_job_selection(data: Dict[str, Any], job_search: JobSearchTool) -> None:
    """Handle job selection requests."""
    job_data = data.get('data', {})
    job_id = job_data.get('job_id')
    
    if job_id:
        job_search.display_job(job_id)

async def handle_view_change(ui_state: UIState) -> None:
    """Handle view mode changes."""
    ui_state.view_mode = "search"
    ui_state._notify_listeners()

async def ui_state_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle WebSocket connections for UI state updates."""
    # Create a WebSocket response
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Get references to our tools and state
    ui_state = request.app['ui_state']
    job_search = request.app['job_search']
    
    # Send the initial state
    await ws.send_json({
        'type': 'state_update',
        'data': ui_state.get_state()
    })
    
    # Set up a callback to send state updates
    async def on_state_update(state):
        if not ws.closed:
            await ws.send_json({
                'type': 'state_update',
                'data': state
            })
    
    # Register the callback
    ui_state.add_update_listener(on_state_update)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message_type = data.get('type')
                    
                    if message_type == 'reset_state':
                        ui_state.reset_state()
                    elif message_type == 'manual_search':
                        await handle_manual_search(data, job_search)
                    elif message_type == 'select_job':
                        await handle_job_selection(data, job_search)
                    elif message_type == 'view_search_results':
                        await handle_view_change(ui_state)
                        
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
                break
    finally:
        if on_state_update in ui_state._on_update_callbacks:
            ui_state._on_update_callbacks.remove(on_state_update)
    
    return ws

def setup_state_management(app: web.Application) -> None:
    """Initialize and configure state management."""
    app['ui_state'] = UIState()
    app['job_search'] = JobSearchTool()
    
    app['job_search'].ui_state = app['ui_state']
    
    original_reset = app['ui_state'].reset_state
    def reset_all_state():
        app['job_search'].reset_state()
        original_reset()
    app['ui_state'].reset_state = reset_all_state

async def create_app() -> web.Application:
    """Create and configure the web application."""
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()

    llm_credential = _get_credentials()
    app = web.Application()
    
    rtmt = RTMiddleTier(
        credentials=llm_credential,
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment=os.environ["AZURE_OPENAI_REALTIME_DEPLOYMENT"],
        voice_choice=os.environ.get("AZURE_OPENAI_REALTIME_VOICE_CHOICE") or "echo"
    )
    rtmt.system_message = SYSTEM_MESSAGE

    setup_state_management(app)
    attach_job_tools(rtmt, app['job_search'])
    _setup_routes(app, rtmt)

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
    app.router.add_get('/api/state/ws', ui_state_handler)
    rtmt.attach_to_app(app, "/realtime")
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')

if __name__ == "__main__":
    web.run_app(create_app(), host=HOST, port=PORT)
