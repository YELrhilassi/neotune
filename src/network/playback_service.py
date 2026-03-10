"""Service for managing Spotify playback and devices."""

import time
import threading
from typing import Optional, Any
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

    def get_current_playback(self, force: bool = False) -> Optional[dict[str, Any]]:
        """Fetch current playback state with predictive local sync."""
        with self._lock:
            now = time.time()

            # 1. Smart Sync Logic
            # If we have a state and we're within the TTL window, return predicted progress
            if (
                not force
                and self._last_playback_state
                and (now - self._last_state_time < self._state_cache_ttl)
            ):
                if self._last_playback_state.get("is_playing"):
                    # Calculate local progress prediction
                    elapsed_ms = int((now - self._last_state_time) * 1000)
                    predicted = self._last_playback_state.copy()

                    # Ensure we don't predict past the track duration
                    duration = predicted.get("item", {}).get("duration_ms", 0)
                    new_progress = predicted.get("progress_ms", 0) + elapsed_ms

                    if duration > 0 and new_progress >= duration:
                        # Near end: fall through to actual API call
                        pass
                    else:
                        predicted["progress_ms"] = new_progress
                        return predicted
                else:
                    # If paused, cache is 100% accurate
                    return self._last_playback_state

            # 2. Actual API Call (Throttled by Base Service min_interval)
            # Use a slightly longer interval here to strictly control traffic
            state = self._safe_api_call(
                self.sp.current_playback, track_name="current_playback", min_interval=5.0
            )

            # If API returns None (due to throttling or error), use last known
            if state is None:
                return self._last_playback_state

            # Update cache
            self._last_playback_state = state
            self._last_state_time = now
            return state

    def get_devices(self, force: bool = True) -> list[dict[str, Any]]:
        """Fetch available devices. Defaults to forcing a fresh fetch for accuracy."""
        with self._lock:
            now = time.time()
            if not force and (now - self._last_devices_time < self._devices_cache_ttl):
                return self._last_devices

            result = self._safe_api_call(
                self.sp.devices, default_return={}, track_name="devices", min_interval=0.5
            )
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
            # Handle NO_ACTIVE_DEVICE specifically
            if "No active device" in str(e) or "NO_ACTIVE_DEVICE" in str(e):
                self._debug.warning("Playback", "No active device. Attempting auto-recovery...")
                dev_id = self.find_fallback_device()
                if dev_id:
                    self._debug.info("Playback", f"Auto-transferring playback to device: {dev_id}")
                    self.transfer(dev_id, force_play=True)
                    # Retry the original operation after a short settle time
                    time.sleep(1.0)
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
        """Resume playback with proactive device check to avoid 404s."""
        # 1. Proactive check with FRESH device list
        state = self.get_current_playback()
        if not state or not state.get("device", {}).get("is_active"):
            # Try to recover before even calling the API
            # force=True to ensure we see the local player if it just started
            dev_id = self.find_fallback_device()
            if dev_id:
                self._debug.info("Playback", f"Activating device {dev_id} before resume")
                self.transfer(dev_id, force_play=True)
                return

        # 2. Standard call with fallback recovery
        self._safe_api_call(
            self._execute_with_fallback,
            self.sp.start_playback,
            track_name="resume_playback",
            suppress_status_codes=[404],  # Suppress 404 if recovery still fails
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
