from dataclasses import dataclass
import json
import requests
from typing import Any, Dict, List, Optional
from opentelemetry import trace
from difflib import SequenceMatcher

# Constants
API_BASE_URL = "https://gcsservices.careers.microsoft.com/search/api/v1"
SEARCH_ENDPOINT = f"{API_BASE_URL}/search"
JOB_DETAIL_ENDPOINT = f"{API_BASE_URL}/job"
DEFAULT_PAGE_SIZE = 20
SIMILARITY_THRESHOLD = 0.3

# Custom exceptions
class JobSearchError(Exception):
    """Base exception for job search related errors."""
    pass

class JobAPIError(JobSearchError):
    """Raised when the job search API returns an error."""
    pass

@dataclass
class SearchParams:
    """Search parameters for job search API."""
    query: str
    country: Optional[str] = None
    language: str = "en_us"
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    order_by: str = "Relevance"
    filter_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to API format."""
        params = {
            "q": self.query,
            "l": self.language,
            "pg": self.page,
            "pgSz": self.page_size,
            "o": self.order_by,
            "flt": str(self.filter_enabled).lower()
        }
        if self.country:
            params["lc"] = self.country
        return params

tracer = trace.get_tracer(__name__)

class JobSearchTool:
    """
    Tool for searching Microsoft jobs and managing job search state.
    
    Attributes:
        current_job: Currently selected job details
        search_query: Last executed search query
        search_country: Country filter used in last search
        ui_state: Reference to UI state manager
    """
    
    def __init__(self, ui_state):
        """Initialize JobSearchTool with UI state manager.
        
        Args:
            ui_state: UI state manager instance for updating the interface
        """
        self.current_job: Optional[Dict[str, Any]] = None
        self.search_query: Optional[str] = None
        self.search_country: Optional[str] = None
        self.ui_state = ui_state

    def _make_api_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request with error handling and telemetry."""
        with tracer.start_as_current_span("api_request") as span:
            span.set_attribute("url", url)
            if params:
                span.set_attribute("params", str(params))
            
            try:
                span.add_event("api_call_start")
                response = requests.get(url, params=params)
                span.add_event("api_call_end")
                
                span.set_attribute("http.status_code", response.status_code)
                response.raise_for_status()
                
                return response.json()
            except requests.RequestException as e:
                span.record_exception(e)
                raise JobAPIError(f"API request failed: {str(e)}") from e

    def search_jobs(self, query: str, country: Optional[str] = None) -> str:
        """
        Search Microsoft job postings.
        
        Args:
            query: Search query string
            country: Optional country code filter
            
        Returns:
            JSON string containing search results
            
        Raises:
            JobAPIError: If the API request fails
        """
        with tracer.start_as_current_span("search_jobs") as span:
            span.set_attribute("query", query)
            if country:
                span.set_attribute("country", country)
            
            self.search_query = query
            self.search_country = country
            
            search_params = SearchParams(query=query, country=country)
            try:
                data = self._make_api_request(SEARCH_ENDPOINT, search_params.to_dict())
                
                # Extract relevant data
                operation_result = data.get("operationResult", {})
                result = operation_result.get("result", {})
                jobs = result.get("jobs", [])
                total_count = result.get("totalJobs", 0)
                
                # Update UI state
                self.ui_state.update_search(query, country, jobs, total_count)
                return json.dumps(data, ensure_ascii=False)
                
            except JobAPIError as e:
                return json.dumps({"error": str(e)})

    def display_job(self, job_id: str) -> str:
        """
        Display details for a specific job.
        
        Args:
            job_id: Unique identifier for the job
            
        Returns:
            JSON string containing job details
            
        Raises:
            JobAPIError: If the API request fails
        """
        with tracer.start_as_current_span("display_job") as span:
            span.set_attribute("job_id", job_id)
            
            try:
                job_url = f"{JOB_DETAIL_ENDPOINT}/{job_id}"
                data = self._make_api_request(job_url)
                
                job_details = data.get("operationResult", {}).get("result", {})
                self.current_job = job_details
                self.ui_state.update_job_detail(job_details)
                
                return json.dumps(job_details, ensure_ascii=False)
            except JobAPIError as e:
                return json.dumps({"error": str(e)})

    def find_and_display_job(self, title: str) -> str:
        """
        Find and display the best matching job by title.
        
        Args:
            title: Job title to match against
            
        Returns:
            JSON string containing job details or error message
        """
        with tracer.start_as_current_span("find_and_display_job") as span:
            span.set_attribute("search_title", title)
            
            # Get current search results from UI state's SearchState
            search_results = self.ui_state.search_state.results
            
            if not search_results:
                return json.dumps({"error": "No active search results. Please search for jobs first."})
            
            # Find best matching job using title similarity
            best_match = None
            highest_ratio = 0
            
            for job in search_results:
                ratio = SequenceMatcher(None, title.lower(), job["title"].lower()).ratio()
                if ratio > highest_ratio:
                    highest_ratio = ratio
                    best_match = job
            
            if not best_match or highest_ratio < SIMILARITY_THRESHOLD:
                return json.dumps({"error": f"No matching job found for title: {title}"})
            
            # Display the matched job
            return self.display_job(best_match["jobId"])

    def reset_state(self) -> None:
        """Reset all internal state to initial values."""
        self.current_job = None
        self.search_query = None
        self.search_country = None