from typing import Optional, List, Dict, Any

class UIState:
    """Manages the current state of the user interface"""
    def __init__(self):
        self.search_state = {
            "query": None,
            "country": None,
            "results": None,
            "total_count": 0
        }
        self.current_job = None
        self.view_mode = "search"  # Can be 'search' or 'detail'
    
    def update_search(self, query: str, country: Optional[str], results: List[Dict], total_count: int):
        """Update search results state"""
        self.search_state = {
            "query": query,
            "country": country,
            "results": results[:5],  # Only keep first 5 results
            "total_count": total_count
        }
        self.view_mode = "search"
    
    def update_job_detail(self, job: Dict[str, Any]):
        """Update the currently viewed job"""
        self.current_job = job
        self.view_mode = "detail"
    
    def get_state(self) -> Dict:
        """Get the complete UI state"""
        return {
            "search": self.search_state,
            "current_job": self.current_job,
            "view_mode": self.view_mode
        }
