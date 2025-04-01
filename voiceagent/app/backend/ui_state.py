from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set

# View mode constants
class ViewMode(Enum):
    SEARCH = "search"
    DETAIL = "detail"

@dataclass
class SearchState:
    """State for job search results."""
    query: Optional[str] = None
    country: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    total_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class StateUpdateError(Exception):
    """Raised when state update fails."""
    pass

class UIState:
    """
    Manages the current state of the user interface.
    
    Attributes:
        _search_state: Current search parameters and results
        _current_job: Currently selected job details
        _view_mode: Current view mode (search/detail)
        _on_update_callbacks: Registered state change listeners
    """
    
    MAX_RESULTS = 5  # Maximum number of results to store
    
    def __init__(self):
        self._search_state = SearchState()
        self._current_job: Optional[Dict[str, Any]] = None
        self._view_mode: ViewMode = ViewMode.SEARCH
        self._on_update_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    @property
    def search_state(self) -> SearchState:
        """Get current search state."""
        return self._search_state
    
    @search_state.setter
    def search_state(self, value: Dict[str, Any]) -> None:
        """Update search state with validation."""
        try:
            self._search_state = SearchState(**value)
        except (TypeError, ValueError) as e:
            raise StateUpdateError(f"Invalid search state: {str(e)}")

    @property
    def current_job(self) -> Optional[Dict[str, Any]]:
        """Get current job details."""
        return self._current_job
    
    @current_job.setter
    def current_job(self, value: Dict[str, Any]) -> None:
        """Update current job details."""
        self._current_job = value

    @property
    def view_mode(self) -> str:
        """Get current view mode."""
        return self._view_mode.value
    
    @view_mode.setter
    def view_mode(self, value: str) -> None:
        """Update view mode with validation."""
        try:
            self._view_mode = ViewMode(value)
        except ValueError:
            raise StateUpdateError(f"Invalid view mode: {value}")

    def add_update_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback to be called when state changes."""
        self._on_update_callbacks.append(callback)
    
    async def _notify_listeners_async(self, state: Dict[str, Any]) -> None:
        """Notify async listeners of state changes."""
        for callback in self._on_update_callbacks:
            if asyncio.iscoroutinefunction(callback):
                await callback(state)

    def _notify_listeners(self) -> None:
        """Notify all listeners of state change."""
        state = self.get_state()
        sync_callbacks = [cb for cb in self._on_update_callbacks 
                         if not asyncio.iscoroutinefunction(cb)]
        
        # Handle synchronous callbacks
        for callback in sync_callbacks:
            callback(state)
            
        # Schedule async callbacks
        if any(asyncio.iscoroutinefunction(cb) for cb in self._on_update_callbacks):
            asyncio.create_task(self._notify_listeners_async(state))

    def update_search(self, query: str, country: Optional[str], 
                     results: List[Dict[str, Any]], total_count: int) -> None:
        """
        Update search results state.
        
        Args:
            query: Search query string
            country: Optional country filter
            results: List of job results
            total_count: Total number of matches
        """
        self._search_state = SearchState(
            query=query,
            country=country,
            results=results[:self.MAX_RESULTS],
            total_count=total_count
        )
        self._view_mode = ViewMode.SEARCH
        self._notify_listeners()

    def update_job_detail(self, job: Dict[str, Any]) -> None:
        """Update the currently viewed job."""
        self._current_job = job
        self._view_mode = ViewMode.DETAIL
        self._notify_listeners()
    
    def reset_view(self) -> None:
        """Reset the view to search mode without clearing results."""
        self._view_mode = ViewMode.SEARCH
        self._current_job = None # Clear selected job when going back to search
        self._notify_listeners()

    def reset_state(self) -> None:
        """Reset all state to initial values."""
        self._search_state = SearchState()
        self._current_job = None
        self._view_mode = ViewMode.SEARCH
        self._notify_listeners()
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete UI state as dictionary."""
        return {
            "search": self._search_state.to_dict(),
            "current_job": self._current_job,
            "view_mode": self._view_mode.value
        }
        
    def set_state_from_dict(self, state: Dict[str, Any]) -> None:
        """
        Restore UI state from a dictionary (for Redis loading).
        
        Args:
            state: Dictionary containing the state to restore
        """
        if "search" in state:
            search_data = state["search"]
            # Handle case where results might be None but the rest is valid
            if search_data.get("query"):
                results = search_data.get("results") or []
                self._search_state = SearchState(
                    query=search_data.get("query"),
                    country=search_data.get("country"),
                    results=results,
                    total_count=search_data.get("total_count", 0)
                )
        
        if "current_job" in state and state["current_job"]:
            self._current_job = state["current_job"]
            
        if "view_mode" in state:
            try:
                self._view_mode = ViewMode(state["view_mode"])
            except ValueError:
                # Default to search view if invalid
                self._view_mode = ViewMode.SEARCH
