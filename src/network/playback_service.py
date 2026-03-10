"""Service for managing Spotify playback and devices."""

import time
from typing import Optional, List, Dict, Any
from src.core.constants import PlayerSettings
from src.network.base import SpotifyServiceBase


class PlaybackService(SpotifyServiceBase):
    """Manages active playback controls and state polling."""

    def __init__(self, sp=None):
        super().__init__(sp)
        self._last_playback_state = None
        self._last_state_time = 0
        self._state_cache_ttl = 1.5  # Forced internal TTL to prevent polling spam

    def get_current_playback(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch current playback state with strict deduplication."""
        now = time.time()
        if not force and (now - self._last_state_time < self._state_cache_ttl):
            return self._last_playback_state

        state = self._safe_api_call(self.sp.current_playback, track_name="current_playback")
        self._last_playback_state = state
        self._last_state_time = now
        return state

    def get_devices(self) -> List[Dict[str, Any]]:
        result = self._safe_api_call(self.sp.devices, default_return={}, track_name="devices")
        return result.get("devices", []) if result else []

    def find_fallback_device(self) -> Optional[str]:
        """Look for a suitable device without aggressive re-polling."""
        devices = self.get_devices()
        if not devices:
            return None

        # 1. Our player
        for d in devices:
            if d.get("name") == PlayerSettings.DEVICE_NAME:
                return d.get("id")

        # 2. Active device
        for d in devices:
            if d.get("is_active"):
                return d.get("id")

        # 3. First available
        return devices[0].get("id")

    def _execute_with_fallback(self, operation: callable, *args, **kwargs) -> Any:
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            if "No active device" in str(e):
                dev_id = self.find_fallback_device()
                if dev_id:
                    kwargs["device_id"] = dev_id
                    return operation(*args, **kwargs)
            raise

    def play_track(self, track_uri, device_id=None, context_uri=None, offset=None):
        params = {}
        if device_id:
            params["device_id"] = device_id
        if context_uri:
            params["context_uri"] = context_uri
        if offset is not None:
            params["offset"] = {"position": int(offset)}

        if isinstance(track_uri, str) and ":track:" in track_uri:
            params["uris"] = [track_uri]
            params["offset"] = {"uri": track_uri}
        elif isinstance(track_uri, list):
            params["uris"] = track_uri

        self._safe_api_call(self.sp.start_playback, track_name="play_track", **params)

    def pause(self):
        self._safe_api_call(self.sp.pause_playback, track_name="pause_playback")

    def resume(self):
        self._safe_api_call(
            self._execute_with_fallback, self.sp.start_playback, track_name="resume_playback"
        )

    def next(self):
        self._safe_api_call(
            self._execute_with_fallback, self.sp.next_track, track_name="next_track"
        )

    def previous(self):
        self._safe_api_call(
            self._execute_with_fallback, self.sp.previous_track, track_name="prev_track"
        )

    def toggle_shuffle(self, state: bool):
        self._safe_api_call(
            self._execute_with_fallback, self.sp.shuffle, state=state, track_name="toggle_shuffle"
        )

    def set_repeat(self, state: str):
        self._safe_api_call(
            self._execute_with_fallback, self.sp.repeat, state=state, track_name="set_repeat"
        )

    def transfer(self, device_id: str, force_play: bool = True):
        self._safe_api_call(
            self.sp.transfer_playback,
            device_id=device_id,
            force_play=force_play,
            track_name="transfer_playback",
        )
