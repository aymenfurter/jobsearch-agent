import logging
import os
from pathlib import Path
import json

from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, DefaultAzureCredential
from dotenv import load_dotenv
from openai import AsyncOpenAI

from rtmt import RTMiddleTier
from job_search import JobSearchTool
from job_tools import attach_job_tools
from user_message import UserMessageTool
from user_message_tools import attach_user_message_tools
from ui_state import UIState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobsearch")

async def get_state(request):
    job_search = request.app['job_search']
    user_message = request.app['user_message']
    ui_state = request.app['ui_state']
    
    state = {
        'ui': ui_state.get_state(),
        'status_message': user_message.get_current_message()
    }
    return web.json_response(state)

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

You must show a high fidelity HTML-based menu using the show_message function to display job search options and results.
"""

    # Initialize state management
    app['ui_state'] = UIState()
    app['job_search'] = JobSearchTool()
    app['user_message'] = UserMessageTool()
    
    # Connect the tools
    app['job_search'].ui_state = app['ui_state']
    app['job_search'].user_message = app['user_message']
    
    attach_job_tools(rtmt, app['job_search'])
    attach_user_message_tools(rtmt, app['user_message'])

    # Add routes
    app.router.add_get('/api/state', get_state)

    rtmt.attach_to_app(app, "/realtime")

    current_directory = Path(__file__).parent
    app.add_routes([web.get('/', lambda _: web.FileResponse(current_directory / 'static/index.html'))])
    app.router.add_static('/', path=current_directory / 'static', name='static')
    
    return app

if __name__ == "__main__":
    host = "localhost"
    port = 8765
    web.run_app(create_app(), host=host, port=port)
