"""
Job search tool definitions and implementations for the Microsoft Careers API.
This module provides the integration between the RTMiddleTier and JobSearchTool.
"""

from dataclasses import dataclass
from enum import Enum, auto
import json
from typing import Any, Callable, Dict, Optional, TypeVar, Tuple, List

# Local imports
from job_search import JobSearchTool

# Define ToolResultDirection and ToolResult here
class ToolResultDirection(Enum):
    """Direction to send tool execution results."""
    TO_SERVER = auto()  # Results go to the LLM
    TO_CLIENT = auto()  # Results go to the client UI

@dataclass
class ToolResult:
    """Result from a tool execution."""
    text: str
    destination: ToolResultDirection

    def to_text(self) -> str:
        """Convert tool result to text format."""
        if self.text is None:
            return ""
        return self.text if isinstance(self.text, str) else json.dumps(self.text)

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
    # Result goes to server (LLM) to inform the user, not directly to client UI
    return ToolResult(result, ToolResultDirection.TO_SERVER)

async def _display_job(job_search: JobSearchTool, args: Dict[str, Any]) -> ToolResult:
    """Display specific job details based on title match."""
    result = job_search.find_and_display_job(args["title"])
    # Result goes to server (LLM) to inform the user, not directly to client UI
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

def get_tool_definitions() -> Dict[str, ToolDefinition]:
    """Return the dictionary of tool definitions."""
    return TOOL_DEFINITIONS