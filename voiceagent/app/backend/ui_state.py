from typing import Optional, List, Dict, Any, Callable
import asyncio

class UIState:
    """Manages the current state of the user interface"""
    def __init__(self):
        self._search_state = {
            "query": None,
            "country": None,
            "results": None,
            "total_count": 0
        }
        self._current_job = None
        self._view_mode = "search"  # Can be 'search' or 'detail'
        self._on_update_callbacks = []
    
    @property
    def search_state(self):
        return self._search_state
    
    @search_state.setter
    def search_state(self, value):
        self._search_state = value
    
    @property
    def current_job(self):
        return self._current_job
    
    @current_job.setter
    def current_job(self, value):
        self._current_job = value
    
    @property
    def view_mode(self):
        return self._view_mode
    
    @view_mode.setter
    def view_mode(self, value):
        if value in ["search", "detail"]:
            self._view_mode = value
    
    def add_update_listener(self, callback: Callable[[Dict], None]):
        """Add a callback to be called when state changes"""
        self._on_update_callbacks.append(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of state change"""
        state = self.get_state()
        for callback in self._on_update_callbacks:
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(state))
            else:
                callback(state)
    
    def update_search(self, query: str, country: Optional[str], results: List[Dict], total_count: int):
        """Update search results state"""
        self._search_state = {
            "query": query,
            "country": country,
            "results": results[:5],  # Only keep first 5 results
            "total_count": total_count
        }
        self._view_mode = "search"
        self._notify_listeners()
    
    def update_job_detail(self, job: Dict[str, Any]):
        """Update the currently viewed job"""
        self._current_job = job
        self._view_mode = "detail"
        self._notify_listeners()
    
    def reset_state(self):
        """Reset the state to its initial values"""
        self._search_state = {
            "query": None,
            "country": None,
            "results": None,
            "total_count": 0
        }
        self._current_job = None
        self._view_mode = "search"
        self._notify_listeners()
    
    def get_state(self) -> Dict:
        """Get the complete UI state"""
        return {
            "search": self._search_state,
            "current_job": self._current_job,
            "view_mode": self._view_mode
        }
