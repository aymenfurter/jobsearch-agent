"""
Job search tool definitions and implementations for the Microsoft Careers API.
This module provides the integration between the RTMiddleTier and JobSearchTool.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple

from rtmt import RTMiddleTier, Tool, ToolResult, ToolResultDirection
from job_search import JobSearchTool

# Type definitions
ToolFunc = Callable[[JobSearchTool, Dict[str, Any]], ToolResult]
SchemaType = Dict[str, Any]
T = TypeVar('T')

@dataclass
class ToolDefinition:
    """Configuration for a job search tool."""
    schema: SchemaType
    handler: ToolFunc
    name: str
    description: str

# Schema definitions
SCHEMAS = {
    "search_jobs": {
        "type": "function",
        "name": "search_jobs",
        "description": "Search for jobs at Microsoft",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The job search query (e.g., job title, skills, etc.)"
                },
                "country": {
                    "type": "string",
                    "description": "Optional country to filter jobs by"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    "display_job": {
        "type": "function",
        "name": "display_job_details",
        "description": "Display details for a specific job by its title. Will match the closest title from current search results.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title or partial title of the job to display"
                }
            },
            "required": ["title"],
            "additionalProperties": False
        }
    }
}

async def _search_jobs(job_search: JobSearchTool, args: Dict[str, Any]) -> ToolResult:
    """Execute job search and return results."""
    result = job_search.search_jobs(args["query"], args.get("country"))
    print(f"Search result: {result}")
    return ToolResult(result, ToolResultDirection.TO_SERVER)

async def _display_job(job_search: JobSearchTool, args: Dict[str, Any]) -> ToolResult:
    """Display specific job details based on title match."""
    result = job_search.find_and_display_job(args["title"])
    return ToolResult(result, ToolResultDirection.TO_SERVER)

# Tool configuration mapping
TOOL_DEFINITIONS = {
    "search_jobs": ToolDefinition(
        schema=SCHEMAS["search_jobs"],
        handler=_search_jobs,
        name="search_jobs",
        description="Search for jobs at Microsoft"
    ),
    "display_job_details": ToolDefinition(
        schema=SCHEMAS["display_job"],
        handler=_display_job,
        name="display_job_details",
        description="Display details for a specific job"
    )
}

def attach_job_tools(rtmt: RTMiddleTier, job_search: JobSearchTool) -> None:
    """
    Attach all job search tools to the RTMiddleTier instance.
    
    Args:
        rtmt: The real-time middle tier instance
        job_search: The job search tool instance
    """
    for tool_def in TOOL_DEFINITIONS.values():
        rtmt.tools[tool_def.name] = Tool(
            schema=tool_def.schema,
            target=lambda args, f=tool_def.handler: f(job_search, args)
        )