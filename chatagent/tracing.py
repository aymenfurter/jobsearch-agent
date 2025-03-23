import os
from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.projects.telemetry.agents import AIAgentsInstrumentor
from contextlib import contextmanager

def setup_tracing(project_client):
    """
    Set up Azure Monitor OpenTelemetry tracing for the job search agent.
    
    Args:
        project_client: The Azure AI Project client
    
    Returns:
        The configured OpenTelemetry tracer
    """
    # Get connection string from the project
    application_insights_connection_string = project_client.telemetry.get_connection_string()
    if not application_insights_connection_string:
        print("Application Insights not enabled - enable it in your AI Foundry project's 'Tracing' tab")
        return trace.get_tracer(__name__)
    
    # Configure Azure Monitor with the connection string
    configure_azure_monitor(connection_string=application_insights_connection_string)
    
    # Configure tracing
    instrumentor = AIAgentsInstrumentor()
    instrumentor.instrument(enable_content_recording=True)
    
    print("Azure Monitor tracing configured successfully")
    
    # Create and return a tracer
    return trace.get_tracer(__name__)

def create_trace_span(name, tracer=None):
    """
    Helper function to create a trace span with proper handling when tracer is None.
    
    Args:
        name: Name of the span
        tracer: Optional tracer instance
        
    Returns:
        A context manager for the span or a nullcontext if tracer is None
    """
    if tracer:
        return tracer.start_as_current_span(name)
    else:
        return nullcontext()

# Helper context manager for when no tracer is provided
@contextmanager
def nullcontext(enter_result=None):
    """
    Improved nullcontext implementation compatible with OpenTelemetry spans.
    This allows code to work with or without a tracer being configured.
    
    Args:
        enter_result: The value to return from __enter__
        
    Yields:
        The enter_result value
    """
    yield enter_result
