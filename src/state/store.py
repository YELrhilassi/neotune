import json
import os
from pathlib import Path
from typing import Callable, Dict, Any, List


from src.core.di import Container
from src.state.pubsub import PubSub


class Store:
    """
    A centralized, reactive state store with built-in persistence.
    Follows the Observer pattern to notify UI components of state transitions.
    """

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "spotify-tui"
        self.state_file = self.config_dir / "state.json"
        self._pubsub = PubSub()

        self._state: Dict[str, Any] = {
            "playlists": [],
            "featured_playlists": [],
            "recently_played": [],
            "current_tracks": [],
            "current_playback": None,
            "devices": [],
            "preferred_device_id": None,
            "is_authenticated": False,
            "api_connected": False,
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
            "special_playlists": [],
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

            # Bridge to Feature Stores
            try:
                from src.state.feature_stores import (
                    PlaybackStore,
                    NetworkStore,
                    DeviceStore,
                    UIStore,
                )

                if key == "current_playback":
                    Container.resolve(PlaybackStore).set(value)
                    if value and value.get("device"):
                        Container.resolve(DeviceStore).update(
                            preferred_name=value["device"].get("name")
                        )
                elif key == "api_connected":
                    Container.resolve(NetworkStore).update(api_connected=value)
                elif key == "is_authenticated":
                    Container.resolve(NetworkStore).update(is_authenticated=value)
                elif key == "current_tracks":
                    # Deep update for tracks to ensure reactivity
                    Container.resolve(UIStore).update(current_tracks=list(value) if value else [])
                elif key == "playlists":
                    Container.resolve(UIStore).update(playlists=list(value) if value else [])
                elif key == "special_playlists":
                    Container.resolve(UIStore).update(
                        special_playlists=list(value) if value else []
                    )
                elif key == "browse_metadata":
                    Container.resolve(UIStore).update(browse_metadata=dict(value) if value else {})
                elif key == "loading_states":
                    Container.resolve(UIStore).update(loading_states=dict(value) if value else {})
                elif key == "preferred_device_name":
                    Container.resolve(DeviceStore).update(preferred_name=value)
                elif key == "devices":
                    Container.resolve(DeviceStore).update(available=list(value) if value else [])
            except:
                pass

            # Use PubSub for notifications
            self._pubsub.publish(f"store:{key}", value)
            self._pubsub.publish("store:*", (key, value))

    def subscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        self._pubsub.subscribe(f"store:{key}", callback)
        # Notify immediately with current state
        callback(self._state.get(key))

    def subscribe_all(self, callback: Callable) -> None:
        self._pubsub.subscribe_all(
            lambda topic, data: callback() if topic.startswith("store:") else None
        )

    def _notify(self, key: str, value: Any) -> None:
        # Legacy method, now handled by set() via PubSub
        pass
