import json
import pytest
from job_search import JobSearchTool

@pytest.fixture
def job_search():
    """Create a JobSearchTool instance with mocked user message for message display"""
    tool = JobSearchTool()
    # Update mock to handle three arguments (self, message, duration)
    tool.user_message = type('MockMessage', (), {
        'set_message': lambda x, y, z: None
    })()
    return tool

def test_search_jobs_success(job_search):
    """Test successful job search using real API"""
    result = json.loads(job_search.search_jobs("software engineer"))
    
    # Basic validation of API response structure
    assert "operationResult" in result
    assert "result" in result["operationResult"]
    assert "totalJobs" in result["operationResult"]["result"]
    assert "jobs" in result["operationResult"]["result"]
    
    # Verify we got actual job results
    jobs = result["operationResult"]["result"]["jobs"]
    assert len(jobs) > 0
    
    # Verify job structure
    first_job = jobs[0]
    assert "jobId" in first_job
    assert "title" in first_job
    assert "properties" in first_job
    assert "locations" in first_job["properties"]

def test_search_jobs_with_country(job_search):
    """Test job search with country filter using real API"""
    result = json.loads(job_search.search_jobs("software engineer", "United States"))
    
    # Verify we got results
    assert "operationResult" in result
    jobs = result["operationResult"]["result"]["jobs"]
    
    # Check that at least some jobs are in the specified country
    us_jobs = [job for job in jobs if any("United States" in loc for loc in job["properties"]["locations"])]
    assert len(us_jobs) > 0, "Should find jobs in the United States"

def test_search_jobs_no_results(job_search):
    """Test search with query that should return no results"""
    # Using a very specific query that's unlikely to match any jobs
    result = json.loads(job_search.search_jobs("xyznotarealjobposition123456789"))
    
    assert "operationResult" in result
    assert "result" in result["operationResult"]
    assert "jobs" in result["operationResult"]["result"]
    assert len(result["operationResult"]["result"]["jobs"]) == 0

def test_display_job_details(job_search):
    """Test fetching specific job details using real API"""
    # First get a real job ID from a search
    search_result = json.loads(job_search.search_jobs("software engineer"))
    job_id = search_result["operationResult"]["result"]["jobs"][0]["jobId"]
    
    # Now get the details for this job
    result = json.loads(job_search.display_job(job_id))
    
    # Updated assertions to match actual response structure
    assert "jobId" in result
    assert result["jobId"] == job_id
    assert "title" in result
    assert "description" in result
    # Remove 'properties' and 'locations' assertions as they're not in the current structure
    assert "primaryWorkLocation" in result  # This is the new location field

def test_html_formatting(job_search):
    """Test HTML formatting with real API data"""
    # Get real job data
    search_result = json.loads(job_search.search_jobs("software engineer"))
    job_id = search_result["operationResult"]["result"]["jobs"][0]["jobId"]
    job_details = json.loads(job_search.display_job(job_id))
    
    # Test search results HTML formatting
    search_html = job_search._format_jobs_as_html(search_result)  # Pass the full response
    assert "Found" in search_html
    assert "jobs" in search_html
    assert job_details["title"] in search_html  # This should work with the full response
    assert 'onclick="selectJob(' in search_html

    # Test job details HTML formatting
    details_html = job_search._format_job_details_as_html(job_details)
    assert job_details["title"] in details_html
    assert '<div class="job-details">' in details_html
    assert '<div class="job-meta">' in details_html