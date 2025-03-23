import logging
import os
from pathlib import Path
import json
import asyncio

from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
from openai import AsyncOpenAI

from rtmt import RTMiddleTier
from job_search import JobSearchTool
from job_tools import attach_job_tools
from ui_state import UIState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobsearch")

async def ui_state_handler(request):
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
        # Keep the connection open until client disconnects
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    message_type = data.get('type')
                    
                    if message_type == 'reset_state':
                        # Reset the UI state when requested by client
                        ui_state.reset_state()
                    
                    elif message_type == 'manual_search':
                        # Perform manual search
                        search_data = data.get('data', {})
                        query = search_data.get('query')
                        country = search_data.get('country')
                        
                        if query:
                            # Use our existing search function
                            job_search.search_jobs(query, country)
                    
                    elif message_type == 'select_job':
                        # Display job details
                        job_data = data.get('data', {})
                        job_id = job_data.get('job_id')
                        
                        if job_id:
                            # Use our existing display function
                            job_search.display_job(job_id)
                    
                    elif message_type == 'view_search_results':
                        # Switch back to search results view
                        ui_state.view_mode = "search"
                        ui_state._notify_listeners()
                        
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
                break
    finally:
        # Remove the callback when connection is closed
        if on_state_update in ui_state._on_update_callbacks:
            ui_state._on_update_callbacks.remove(on_state_update)
    
    return ws

async def create_app():
    if not os.environ.get("RUNNING_IN_PRODUCTION"):
        logger.info("Running in development mode, loading from .env file")
        load_dotenv()
    llm_key = os.environ.get("AZURE_OPENAI_API_KEY")
    credential = None
    if not llm_key:
        if tenant_id := os.environ.get("AZURE_TENANT_ID"):
            logger.info("Using AzureDeveloperCliCredential with tenant_id %s", tenant_id)
            credential = AzureDeveloperCliCredential(tenant_id=tenant_id, process_timeout=60)
        else:
            logger.info("Using DefaultAzureCredential")
            credential = DefaultAzureCredential()
    llm_credential = AzureKeyCredential(llm_key) if llm_key else credential
    app = web.Application()
    rtmt = RTMiddleTier(
        credentials=llm_credential,
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment=os.environ["AZURE_OPENAI_REALTIME_DEPLOYMENT"],
        voice_choice=os.environ.get("AZURE_OPENAI_REALTIME_VOICE_CHOICE") or "echo"
    )
    rtmt.system_message = """Start by greeting the user and asking what kind of job they're looking for.
You are a job search assistant. Help users search for jobs at Microsoft and display the results.
Before searching, make sure to ask:
1) What job role/title they're interested in
2) Which country they want to work in (optional)
"""
    # Initialize state management
    app['ui_state'] = UIState()
    app['job_search'] = JobSearchTool()
    
    # Connect the tools
    app['job_search'].ui_state = app['ui_state']
    
    # Connect the reset method of the job search tool to the UI state's reset
    original_reset = app['ui_state'].reset_state
    def reset_all_state():
        app['job_search'].reset_state()
        original_reset()
    app['ui_state'].reset_state = reset_all_state
    
    attach_job_tools(rtmt, app['job_search'])

    # Add routes - remove the REST API endpoint
    app.router.add_get('/api/state/ws', ui_state_handler)
    rtmt.attach_to_app(app, "/realtime")
    current_directory = Path(__file__).parent
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')

    return app

if __name__ == "__main__":
    host = "localhost"
    port = 8765
    web.run_app(create_app(), host=host, port=port)
