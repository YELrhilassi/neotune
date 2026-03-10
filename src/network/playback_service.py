"""Service for managing Spotify playback and devices."""

import time
import threading
from typing import Optional, List, Dict, Any
from src.core.constants import PlayerSettings
from src.network.base import SpotifyServiceBase


class PlaybackService(SpotifyServiceBase):
    """Manages active playback controls and state polling with strict deduplication."""

    def __init__(self, sp=None):
        super().__init__(sp)
        self._last_playback_state = None
        self._last_state_time = 0
        self._state_cache_ttl = 10.0  # Increased TTL significantly for smart sync

        self._last_devices = []
        self._last_devices_time = 0
        self._devices_cache_ttl = 30.0  # Devices change very rarely

        self._lock = threading.Lock()

    def get_current_playback(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch current playback state with predictive local sync."""
        with self._lock:
            now = time.time()

            # If not forcing and within TTL, return predictive state or cached state
            if not force and (now - self._last_state_time < self._state_cache_ttl):
                if self._last_playback_state and self._last_playback_state.get("is_playing"):
                    # Predict progress
                    elapsed_ms = int((now - self._last_state_time) * 1000)
                    predicted = self._last_playback_state.copy()
                    predicted["progress_ms"] = (
                        self._last_playback_state.get("progress_ms", 0) + elapsed_ms
                    )
                    return predicted
                return self._last_playback_state

            # Actual API call
            state = self._safe_api_call(self.sp.current_playback, track_name="current_playback")

            # Update cache
            self._last_playback_state = state
            self._last_state_time = now
            return state

    def get_devices(self, force: bool = False) -> List[Dict[str, Any]]:
        """Fetch available devices with aggressive caching."""
        with self._lock:
            now = time.time()
            if not force and (now - self._last_devices_time < self._devices_cache_ttl):
                return self._last_devices

            result = self._safe_api_call(self.sp.devices, default_return={}, track_name="devices")
            devices = result.get("devices", []) if result else []
            self._last_devices = devices
            self._last_devices_time = now
            return devices

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

    def play_track(
        self,
        track_uri: Any,
        device_id: Optional[str] = None,
        context_uri: Optional[str] = None,
        offset_position: Optional[int] = None,
    ):
        """Start playback with consistent parameter naming."""
        params = {}
        if device_id:
            params["device_id"] = device_id
        if context_uri:
            params["context_uri"] = context_uri
        if offset_position is not None:
            params["offset"] = {"position": int(offset_position)}

        if isinstance(track_uri, str) and ":track:" in track_uri:
            params["uris"] = [track_uri]
            # If playing a single track, offset to it
            if "offset" not in params:
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
