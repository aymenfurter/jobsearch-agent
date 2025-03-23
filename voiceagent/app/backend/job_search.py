import json
import requests
from typing import Optional
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class JobSearchTool:
    """
    Tool for searching Microsoft jobs and managing job search state.
    """
    
    def __init__(self):
        self.current_job = None
        self.search_query = None
        self.search_country = None
        self.ui_state = None  # Will be set when tools are attached
        self.user_message = None  # For status messages only

    def search_jobs(self, query: str, country: Optional[str] = None) -> str:
        """
        Searches Microsoft job postings via an open API call.
        Returns a JSON string with the jobs that match the query.
        """
        with tracer.start_as_current_span("search_jobs") as span:
            span.set_attribute("query", query)
            if country:
                span.set_attribute("country", country)
            
            self.search_query = query
            self.search_country = country
            
            base_url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
            params = {
                "q": query,
                "l": "en_us",
                "pg": 1,
                "pgSz": 20,
                "o": "Relevance",
                "flt": "true"
            }
            
            if country:
                params["lc"] = country

            try:
                span.add_event("api_call_start")
                response = requests.get(base_url, params=params)
                span.add_event("api_call_end")
                
                span.set_attribute("http.status_code", response.status_code)
                
                response.raise_for_status()
                data = response.json()
                
                if "totalCount" in data:
                    span.set_attribute("result_count", data["totalCount"])
                
                operation_result = data.get("operationResult", {})
                result = operation_result.get("result", {})
                jobs = result.get("jobs", [])
                total_count = result.get("totalJobs", 0)
                
                # Update UI state instead of creating HTML
                self.ui_state.update_search(query, country, jobs, total_count)
                
                # Show status message
                self.user_message.set_message(f"Found {total_count} jobs matching your search", 5)
                
                return json.dumps(data, ensure_ascii=False)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                error_html = f'<div class="error">Error searching jobs: {str(e)}</div>'
                self.user_message.set_message(error_html, 10)
                return json.dumps({"error": str(e)})

    def display_job(self, job_id: str) -> str:
        """
        Displays a specific job's details. Expectects a jobID as an input.
        """
        with tracer.start_as_current_span("display_job") as span:
            span.set_attribute("job_id", job_id)
            
            base_url = f"https://gcsservices.careers.microsoft.com/search/api/v1/job/{job_id}"
            
            try:
                span.add_event("api_call_start")
                response = requests.get(base_url)
                span.add_event("api_call_end")
                
                span.set_attribute("http.status_code", response.status_code)
                
                response.raise_for_status()
                data = response.json()
                # Extract job details from the nested structure
                job_details = data.get("operationResult", {}).get("result", {})
                self.current_job = job_details
                
                # Update UI state
                self.ui_state.update_job_detail(job_details)
                
                # Show status message
                self.user_message.set_message(f"Displaying details for {job_details.get('title')}", 5)
                
                return json.dumps(job_details, ensure_ascii=False)
            except Exception as e:
                span.record_exception(e)
                span.set_attribute("error", str(e))
                error_html = f'<div class="error">Error fetching job details: {str(e)}</div>'
                self.user_message.set_message(error_html, 10)
                return json.dumps({"error": str(e)})