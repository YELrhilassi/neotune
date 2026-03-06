from typing import Callable, Dict, Any, List

class Store:
    """A simple reactive state store using the observer pattern."""
    
    def __init__(self):
        self._state: Dict[str, Any] = {
            "playlists": [],
            "featured_playlists": [],
            "recently_played": [],
            "current_tracks": [],
            "current_playback": None,
            "devices": [],
            "preferred_device_id": None,
            "is_authenticated": False,
            "auth_error": None
        }
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {k: [] for k in self._state.keys()}
        self._global_subscribers: List[Callable] = []

    def get(self, key: str) -> Any:
        return self._state.get(key)

    def set(self, key: str, value: Any) -> None:
        if key not in self._state or self._state[key] != value:
            self._state[key] = value
            self._notify(key, value)

    def subscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)
        # Notify immediately with current state
        callback(self._state.get(key))
        
    def subscribe_all(self, callback: Callable) -> None:
        self._global_subscribers.append(callback)

    def _notify(self, key: str, value: Any) -> None:
        for cb in self._subscribers.get(key, []):
            try:
                cb(value)
            except Exception:
                pass # Prevent subscriber crashes from propagating
        for cb in self._global_subscribers:
            try:
                cb()
            except Exception:
                pass
