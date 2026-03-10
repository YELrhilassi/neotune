import json
import os
from pathlib import Path
from typing import Callable, Dict, Any, List


class Store:
    """
    A centralized, reactive state store with built-in persistence.
    Follows the Observer pattern to notify UI components of state transitions.
    """

    def __init__(self):

        self.config_dir = Path.home() / ".config" / "spotify-tui"
        self.state_file = self.config_dir / "state.json"

        self._state: Dict[str, Any] = {
            "playlists": [],
            "featured_playlists": [],
            "recently_played": [],
            "current_tracks": [],
            "current_playback": None,
            "devices": [],
            "preferred_device_id": None,
            "is_authenticated": False,
            "auth_error": None,
            "last_active_context": None,  # spotify:playlist:xxxx or spotify:album:xxxx
            "last_active_node_id": None,
            "user_profile": None,
            "browse_metadata": {
                "categories": [],
                "featured_message": "Featured",
                "featured_playlists": [],
            },
            "loading_states": {"sidebar": False, "track_list": False, "app": False},
            "nav_bindings": {
                "up": "k",
                "down": "j",
                "left": "h",
                "right": "l",
                "page_up": "U",
                "page_down": "D",
            },
        }

        # Keys to persist across sessions
        self._persistent_keys = {
            "last_active_context",
            "last_active_node_id",
            "preferred_device_id",
        }

        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self._global_subscribers: List[Callable] = []

        self._load_persistent_state()

    def _load_persistent_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    for k in self._persistent_keys:
                        if k in data:
                            self._state[k] = data[k]
            except Exception:
                pass

    def _save_persistent_state(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            data = {k: self._state[k] for k in self._persistent_keys}
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get(self, key: str) -> Any:
        return self._state.get(key)

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        if key not in self._state or self._state[key] != value:
            self._state[key] = value
            if persist or key in self._persistent_keys:
                if persist:
                    self._persistent_keys.add(key)
                self._save_persistent_state()
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
                pass
        for cb in self._global_subscribers:
            try:
                cb()
            except Exception:
                pass
