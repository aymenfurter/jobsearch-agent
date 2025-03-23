# main.py

import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Azure identity and AI Project
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    BingGroundingTool,
    FunctionTool,
    ToolSet
)

# Our custom job functions
from job_functions import search_jobs, send_job_info_sms

# Import the Gradio chat interface creator
import gradio as gr
from chat_ui import create_chat_interface

# Import tracing setup
from tracing import setup_tracing, create_trace_span

# Import Real-time API components
from azure.core.credentials import AzureKeyCredential
from realtime_api import RealTimeMiddleTier
from job_display import JobDisplayTool
from realtime_tools import attach_realtime_tools
from realtime_ui import create_realtime_tab

# --------------------------------------------------
# 1) Initialize the Azure AI Project Client
# --------------------------------------------------
credential = DefaultAzureCredential()
project_client = AIProjectClient.from_connection_string(
    credential=credential,
    conn_str=os.environ["PROJECT_CONNECTION_STRING"]  # Set in your .env
)

# --------------------------------------------------
# 1.1) Setup OpenTelemetry Tracing
# --------------------------------------------------
tracer = setup_tracing(project_client)

# --------------------------------------------------
# 2) Setup the Bing Grounding Tool if desired
# --------------------------------------------------
bing_tool = None
bing_connection_name = os.environ.get("BING_CONNECTION_NAME")
if (bing_connection_name):
    try:
        with tracer.start_as_current_span("setup_bing_tool") as span:
            span.set_attribute("bing_connection_name", bing_connection_name)
            bing_connection = project_client.connections.get(connection_name=bing_connection_name)
            conn_id = bing_connection.id
            bing_tool = BingGroundingTool(connection_id=conn_id)
            print("bing > connected")
    except Exception as ex:
        print(f"bing > not connected: {ex}")

# --------------------------------------------------
# 3) Create/Update an Agent with Tools
# --------------------------------------------------
AGENT_NAME = "job-search-agent"

with tracer.start_as_current_span("setup_agent") as span:
    span.set_attribute("agent_name", AGENT_NAME)
    span.set_attribute("model", os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"))
    
    # Find existing agent
    found_agent = next(
        (a for a in project_client.agents.list_agents().data if a.name == AGENT_NAME),
        None
    )

    # Build toolset
    toolset = ToolSet()

    # Add Bing if connected
    if bing_tool:
        toolset.add(bing_tool)

    # Add our function tools (search_jobs, send_job_info_sms)
    toolset.add(FunctionTool({search_jobs, send_job_info_sms}))

    # Define the new instructions for the agent
    instructions = """
    You are a helpful Job Search assistant. Follow these rules:

    1. If the user asks general questions, use the Bing grounding tool.
    2. If the user wants to search for Microsoft job postings, call the `search_jobs` function.
       - They might specify a search keyword, and optionally a country.
       - For example: "search for job postings with 'Cloud Solution Architect' in Switzerland"
    3. If the user wants to send a specific job's info via SMS, call the `send_job_info_sms` function.
    4. Provide relevant answers to the user in a concise yet complete manner.
    5. Always ensure the user's request is properly addressed.
    """

    if found_agent:
        # Update existing
        span.set_attribute("agent_action", "update")
        agent = project_client.agents.update_agent(
            assistant_id=found_agent.id,
            model=found_agent.model,
            instructions=instructions,
            toolset=toolset
        )
    else:
        # Create new
        span.set_attribute("agent_action", "create")
        agent = project_client.agents.create_agent(
            model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"),
            name=AGENT_NAME,
            instructions=instructions,
            toolset=toolset
        )

# --------------------------------------------------
# 3.1) Setup Real-Time API Middleware
# --------------------------------------------------
with tracer.start_as_current_span("setup_realtime_api") as span:
    # Get OpenAI API key or use the same credential
    openai_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if openai_api_key:
        openai_credential = AzureKeyCredential(openai_api_key)
        span.set_attribute("auth_type", "api_key")
    else:
        openai_credential = credential
        span.set_attribute("auth_type", "azure_credential")
    
    # Set up the Real-Time API middleware
    rtmt = RealTimeMiddleTier(
        endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "https://aigonitbwl4kvmk.openai.azure.com/"),
        deployment=os.environ.get("AZURE_OPENAI_REALTIME_DEPLOYMENT", "gpt-4o"),
        credentials=openai_credential,
        voice_choice=os.environ.get("AZURE_OPENAI_VOICE_CHOICE", "alloy")
    )
    
    # Define system message for the Real-Time API
    rtmt.system_message = """
    You are a voice-enabled Job Search assistant specialized in Microsoft job postings.
    
    Help users find and interact with job postings by:
    1. Searching for jobs by keywords and optionally filtering by country
    2. Displaying specific job details when a user asks about a job ID
    3. Sending job details via SMS when requested
    
    Always speak in a professional, friendly tone. When users ask about job postings:
    - Use the search_jobs function to find matching jobs
    - Use the display_job function when users want to see details for a specific job ID
    - Use the send_job_info_sms function when users want to receive job details via SMS
    
    Before each interaction, use the show_message function to provide a status update to the user.
    """
    
    # Create job display tool
    job_display = JobDisplayTool()
    
    # Attach tools to the Real-Time API middleware
    attach_realtime_tools(rtmt, job_display)
    
    span.set_attribute("realtime_setup_complete", True)

# --------------------------------------------------
# 4) Create a Thread for conversation
# --------------------------------------------------
with tracer.start_as_current_span("create_thread") as span:
    thread = project_client.agents.create_thread()
    span.set_attribute("thread_id", thread.id)

# --------------------------------------------------
# 5) Build a Gradio interface
# --------------------------------------------------
with tracer.start_as_current_span("build_gradio_interface") as span:
    # Create the FastAPI app explicitly
    import fastapi
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    
    # Create the FastAPI app
    app = FastAPI()
    
    # Custom JS for handling events - using simpler approach
    custom_js = """
    document.addEventListener('DOMContentLoaded', function() {
        // Set up event listeners for our WebSocket-related events
        window.addEventListener('jobsearch_ws_message', function(e) {
            const data = e.detail;
            console.log('Received WebSocket message:', data);
            
            // Update the status message directly
            const statusEl = document.querySelector('#status-message');
            if (statusEl) {
                if (data.type === "connection_established") {
                    statusEl.textContent = "Connected to real-time API";
                } 
                else if (data.type === "session_created") {
                    statusEl.textContent = "Session created, ready for conversation";
                }
                else if (data.type === "error") {
                    statusEl.textContent = "Error: " + data.message;
                }
                else if (data.type === "connection_closed") {
                    statusEl.textContent = "Connection closed";
                }
            }
            
            // Trigger appropriate events based on message type
            const findTriggerButton = (name) => {
                return document.querySelector('button[value="' + name + '"]');
            };
            
            if (data.type === "assistant_message") {
                // Store the message content in a data attribute
                const btn = findTriggerButton("assistant_message");
                if (btn) {
                    btn.setAttribute('data-content', JSON.stringify({content: data.content}));
                    btn.click();  // Trigger the Gradio event
                }
            }
            else if (data.type === "assistant_message_complete") {
                const btn = findTriggerButton("assistant_message_complete");
                if (btn) btn.click();
            }
            else if (data.type === "tool_response") {
                const btn = findTriggerButton("tool_response");
                if (btn) {
                    btn.setAttribute('data-tool', JSON.stringify({
                        tool_name: data.tool_name,
                        result: data.tool_result
                    }));
                    btn.click();
                }
            }
            else if (data.type === "connection_established" || data.type === "connection_closed") {
                const btn = findTriggerButton("connection_update");
                if (btn) {
                    btn.setAttribute('data-connection', JSON.stringify({
                        connected: data.type === "connection_established",
                        client_id: data.client_id || "",
                    }));
                    btn.click();
                }
            }
        });
        
        // Error handler
        window.addEventListener('jobsearch_ws_error', function(e) {
            console.error('WebSocket error:', e.detail);
            const statusEl = document.querySelector('#status-message');
            if (statusEl) {
                statusEl.textContent = "WebSocket error: " + e.detail.error;
            }
        });
    });
    """
    
    # Create the Gradio interface
    with gr.Blocks(title="Azure AI - Job Search Sample", js=custom_js) as demo:
        gr.Markdown("# Azure AI - Microsoft Job Search Assistant")
        
        with gr.Tabs() as tabs:
            # Tab 1: Azure AI Agent
            with gr.Tab("AI Agent"):
                azure_job_chat = create_chat_interface(project_client, agent, thread, tracer)
                
                chatbot = gr.Chatbot(type="messages")
                input_box = gr.Textbox(label="Ask your Job Search assistant...")

                def clear_history():
                    with tracer.start_as_current_span("clear_chat_history") as span:
                        global thread  # Use nonlocal to access the thread from outer scope
                        thread = project_client.agents.create_thread()
                        span.set_attribute("new_thread_id", thread.id)
                        return []

                # Buttons
                with gr.Row():
                    clear_button = gr.Button("Clear Chat")

                # Example questions
                gr.Markdown("### Example Questions")
                with gr.Row():
                    q1 = gr.Button("Search for 'Cloud Solution Architect' jobs")
                    q2 = gr.Button("Send me job 1814380 via SMS")

                # Handle clearing chat
                clear_button.click(fn=clear_history, outputs=chatbot)

                # Helper function to set example question
                def set_example_question(question):
                    with tracer.start_as_current_span("select_example_question") as span:
                        span.set_attribute("example_question", question)
                        return question

                # Wire example question buttons
                for btn in [q1, q2]:
                    btn.click(fn=set_example_question, inputs=btn, outputs=input_box) \
                       .then(azure_job_chat, inputs=[input_box, chatbot], outputs=[chatbot, input_box]) \
                       .then(lambda: "", outputs=input_box)

                # Submit the user input
                input_box.submit(azure_job_chat, inputs=[input_box, chatbot], outputs=[chatbot, input_box]) \
                         .then(lambda: "", outputs=input_box)
            
            # Tab 2: Real-time API
            # Create the real-time API tab
            realtime_components = create_realtime_tab(rtmt, job_display)
            
            # Get the status message and websocket state components
            status_msg = realtime_components["status_msg"]
            websocket_state = realtime_components["websocket_state"]
            
            # Initialize a message - this isn't using a method that doesn't exist
            status_msg.value = "Ready to connect to real-time API"
    
    # Add the realtime API middleware to the FastAPI app
    rtmt.attach_to_app(app, "/realtime")
    
    # Basic health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    # Mount Gradio app to FastAPI app
    # First, create the Gradio ASGI app
    gradio_app = gr.routes.App.create_app(demo)
    
    # Mount it to the FastAPI app at the root path
    app.mount("/", gradio_app)
    
    # Now launch the app
    import uvicorn
    
    # For local development, use this method to launch
    if __name__ == "__main__":
        # Use queue for better performance with Gradio
        demo.queue()
        
        # Launch using uvicorn with the FastAPI app
        uvicorn.run(app, host="0.0.0.0", port=7860)
    else:
        # For Gradio deployment environments, provide the queue option
        demo.queue()
        # Let the hosting environment handle the server launch
