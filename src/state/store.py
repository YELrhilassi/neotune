import json
import os
import threading
import copy
from pathlib import Path
from typing import Callable, Dict, Any, List, Set, Optional
from src.state.pubsub import PubSub


class Store:
    """
    Centralized, thread-safe, and reactive state store.
    Uses pypubsub for instant notifications across the application.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Store, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config_dir = Path.home() / ".config" / "neotune"
        self.state_file = self.config_dir / "state.json"

        self._state: Dict[str, Any] = {
            "playlists": [],
            "featured_playlists": [],
            "recently_played": [],
            "current_tracks": [],
            "current_playback": None,
            "devices": [],
            "preferred_device_id": None,
            "preferred_device_name": "No Device",
            "is_authenticated": False,
            "api_connected": False,
            "auth_error": None,
            "last_active_context": None,
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
            "special_playlists": [],
            "mode": "NORMAL",
        }

        self._persistent_keys = {
            "last_active_context",
            "last_active_node_id",
            "preferred_device_id",
            "preferred_device_name",
        }

        self._state_lock = threading.RLock()
        self._listener_refs = []
        self._load_persistent_state()
        self._initialized = True

    def _load_persistent_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    with self._state_lock:
                        for k in self._persistent_keys:
                            if k in data:
                                self._state[k] = data[k]
            except Exception:
                pass

    def _save_persistent_state(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with self._state_lock:
                data = {k: self._state[k] for k in self._persistent_keys if k in self._state}
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._state_lock:
            val = self._state.get(key, default)
            # Return a copy for mutable types to prevent accidental in-place modification
            if isinstance(val, (list, dict)):
                return copy.deepcopy(val)
            return val

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """Update a state value and notify subscribers instantly."""
        changed = False
        with self._state_lock:
            current = self._state.get(key)
            if current != value:
                if isinstance(value, (list, dict)):
                    self._state[key] = copy.deepcopy(value)
                else:
                    self._state[key] = value

                changed = True
                if persist or key in self._persistent_keys:
                    if persist:
                        self._persistent_keys.add(key)
                    self._save_persistent_state()

        if changed:
            # Topic: state.<key>, keyword arg: value
            PubSub.publish(f"state.{key}", value=value)
            # Topic: state_changed, keyword args: key, value
            PubSub.publish("state_changed", key=key, value=value)

    def update(self, **kwargs) -> None:
        """Atomic multi-key update."""
        with self._state_lock:
            for k, v in kwargs.items():
                self.set(k, v)

    def subscribe(self, key: str, callback: Callable) -> None:
        """Subscribe to a specific state key. Callback receives the new value."""

        # Use a wrapper that matches pypubsub's requirements
        def listener(value=None, **kwargs):
            callback(value)

        # We MUST store the listener to prevent weakref garbage collection
        if not hasattr(self, "_listener_refs"):
            self._listener_refs = []
        self._listener_refs.append(listener)

        topic = f"state.{key}"
        PubSub.subscribe(topic, listener)
        # Immediate notification with current value
        val = self.get(key)
        callback(val)

    def subscribe_all(self, callback: Callable) -> None:
        """Subscribe to all state changes. Callback receives (key, value)."""

        def listener(key=None, value=None, **kwargs):
            callback(key, value)

        if not hasattr(self, "_listener_refs"):
            self._listener_refs = []
        self._listener_refs.append(listener)

        topic_name = "state_changed"
        PubSub.subscribe(topic_name, listener)
