from typing import Any, Dict, List, Optional
from src.state.base_store import BaseStore


class PlaybackStore(BaseStore[Optional[Dict[str, Any]]]):
    def __init__(self):
        super().__init__("playback", None)


class NetworkStore(BaseStore[Dict[str, Any]]):
    def __init__(self):
        super().__init__(
            "network", {"is_authenticated": False, "api_connected": False, "auth_error": None}
        )


class DeviceStore(BaseStore[Dict[str, Any]]):
    def __init__(self):
        super().__init__(
            "devices", {"available": [], "preferred_id": None, "preferred_name": "No Device"}
        )


class UIStore(BaseStore[Dict[str, Any]]):
    def __init__(self):
        super().__init__(
            "ui",
            {
                "loading_states": {"sidebar": False, "track_list": False, "app": False},
                "mode": "NORMAL",
                "current_tracks": [],
                "playlists": [],
                "special_playlists": [],
                "browse_metadata": {
                    "categories": [],
                    "featured_message": "Featured",
                    "featured_playlists": [],
                },
            },
        )


class ConfigStore(BaseStore[Dict[str, Any]]):
    def __init__(self):
        super().__init__(
            "config",
            {
                "audio": {"bitrate": "320", "backend": "pulseaudio"},
                "theme": "catppuccin",
                "leader": "space",
            },
        )
