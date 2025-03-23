from rtmt import RTMiddleTier, Tool, ToolResult, ToolResultDirection
from job_search import JobSearchTool

# Tool schemas
_search_jobs_schema = {
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
}

_display_job_schema = {
    "type": "function",
    "name": "display_job",
    "description": "Display details for a specific job. You must provide the job ID (e.g. 5787636).",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "The ID of the job to display"
            }
        },
        "required": ["job_id"],
        "additionalProperties": False
    }
}

# Tool implementation functions
async def _search_jobs(job_search: JobSearchTool, args):
    result = job_search.search_jobs(args["query"], args.get("country"))
    return ToolResult(result, ToolResultDirection.TO_SERVER)

async def _display_job(job_search: JobSearchTool, args):
    result = job_search.display_job(args["job_id"])
    return ToolResult(result, ToolResultDirection.TO_SERVER)

def attach_job_tools(rtmt: RTMiddleTier, job_search: JobSearchTool) -> None:
    """Attach all job search tools to the RTMiddleTier instance"""
    # Map each tool schema to its implementation
    tool_mappings = {
        "search_jobs": (_search_jobs_schema, _search_jobs),
        "display_job": (_display_job_schema, _display_job)
    }

    # Attach each tool to the RTMiddleTier instance
    for name, (schema, func) in tool_mappings.items():
        rtmt.tools[name] = Tool(
            schema=schema,
            target=lambda args, f=func: f(job_search, args)
        )