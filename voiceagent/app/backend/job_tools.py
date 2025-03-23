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

# Tool implementation functions
async def _search_jobs(job_search: JobSearchTool, args):
    result = job_search.search_jobs(args["query"], args.get("country"))
    print (f"Search result: {result}")
    return ToolResult(result, ToolResultDirection.TO_SERVER)

async def _display_job(job_search: JobSearchTool, args):
    result = job_search.find_and_display_job(args["title"])
    return ToolResult(result, ToolResultDirection.TO_SERVER)

def attach_job_tools(rtmt: RTMiddleTier, job_search: JobSearchTool) -> None:
    """Attach all job search tools to the RTMiddleTier instance"""
    tool_mappings = {
        "search_jobs": (_search_jobs_schema, _search_jobs),
        "display_job_details": (_display_job_schema, _display_job)
    }

    for name, (schema, func) in tool_mappings.items():
        rtmt.tools[name] = Tool(
            schema=schema,
            target=lambda args, f=func: f(job_search, args)
        )