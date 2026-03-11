"""Service for managing Spotify playback and devices."""

import time
import threading
from typing import Optional, Any, Dict, List, Callable
from src.core.constants import PlayerSettings
from src.network.base import SpotifyServiceBase
from src.core.di import Container


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
        if not self.sp:
            return self._last_playback_state

        with self._lock:
            now = time.time()

            # 1. Smart Sync Logic
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

            # Record activity if context changed
            self._record_activity_from_state(state)

            # Update cache
            self._last_playback_state = state
            self._last_state_time = now
            return state

    def _record_activity_from_state(self, state: dict[str, Any]):
        """Record recently played contexts from playback state."""
        if not state or not state.get("is_playing"):
            return

        # Record if this device is active (regardless of name) OR if it's our specific player
        device = state.get("device", {})
        is_tui_player = device.get("name") == PlayerSettings.DEVICE_NAME

        # User requested: register if it's the selected output device (TUI Player)
        if not is_tui_player:
            return

        context = state.get("context")
        if not context:
            return

        uri = context.get("uri")
        ctype = context.get("type")

        if not uri or ctype not in ["playlist", "album"]:
            return

        # Check if we should (re)record
        # We record if it's a new URI OR if we only have a placeholder name for the current one
        from src.core.activity_service import ActivityService
        from src.core.di import Container as DIContainer

        activity = Container.resolve(ActivityService)
        history = activity.get_recent_contexts()
        existing = next((item for item in history if item["uri"] == uri), None)

        # If it's a new URI or the existing one has a placeholder name
        is_placeholder = existing and (
            ":" in existing["name"]
            or existing["name"].lower() in ["playlist", "album", "unknown context"]
        )

        if not existing or is_placeholder:
            # Use a background task to fetch metadata
            def _fetch_meta_and_record():
                try:
                    from src.network.library_service import LibraryService

                    library = DIContainer.resolve(LibraryService)

                    # Start with a placeholder based on URI
                    context_id = uri.split(":")[-1]
                    name = f"{ctype.capitalize()}: {context_id}"
                    metadata = {}

                    # 0. Check Lua Special Playlists first (highest priority)
                    from src.config.user_prefs import UserPreferences

                    try:
                        prefs = Container.resolve(UserPreferences)
                        for sp in prefs.special_playlists:
                            if sp.get("uri") == uri:
                                name = sp.get("name", name)
                                metadata["artists"] = sp.get("description", "")
                                break
                    except:
                        pass

                    # 1. Fetch full metadata if name is still a placeholder
                    if ":" in name or name.lower() in ["album", "playlist"]:
                        try:
                            if ctype == "playlist":
                                # Use fields to reduce response size and potential errors
                                meta = library.get_playlist_metadata(context_id)
                                if meta:
                                    name = meta.get("name", name)
                                    owner = meta.get("owner", {}).get("display_name", "")
                                    if owner:
                                        metadata["artists"] = f"by {owner}"
                            elif ctype == "album" and not metadata:
                                meta = library.get_album_metadata(context_id)
                                if meta:
                                    name = meta.get("name", name)
                                    artists = meta.get("artists", [])
                                    if artists:
                                        metadata["artists"] = ", ".join(
                                            [a.get("name", "") for a in artists]
                                        )
                        except:
                            pass  # Keep the placeholder if fetch fails

                    activity.record_context_play(uri, name, ctype, metadata)
                    self._debug.info("Activity", f"Recorded context: {name} ({uri})")
                except Exception as e:
                    self._debug.error("Activity", f"Failed to fetch metadata for {uri}: {e}")

            import threading

            threading.Thread(target=_fetch_meta_and_record, daemon=True).start()

    def get_devices(self, force: bool = True) -> list[dict[str, Any]]:
        """Fetch available devices. Defaults to forcing a fresh fetch for accuracy."""
        if not self.sp:
            return self._last_devices

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

    def _execute_with_fallback(self, operation: Callable, *args, **kwargs) -> Any:
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
        """Start playback with consistent parameter naming and special context resolution."""
        if not self.sp:
            return

        params = {}
        if device_id:
            params["device_id"] = device_id

        # Normalize context_uri: if track_uri is a context, move it to context_uri
        if isinstance(track_uri, str) and (
            ":playlist:" in track_uri or ":album:" in track_uri or ":station:" in track_uri
        ):
            if not context_uri:
                context_uri = track_uri
                track_uri = None

        if context_uri:
            params["context_uri"] = context_uri

        if offset_position is not None:
            params["offset"] = {"position": int(offset_position)}

        # 1. Resolve Special Contexts (Radio, Ghost Playlists)
        if context_uri:
            from src.network.discovery_service import DiscoveryService
            from src.core.di import Container as DIContainer

            try:
                disc = DIContainer.resolve(DiscoveryService)
                resolved_uris = disc.resolve_special_context(context_uri)
                if resolved_uris:
                    # Switch from context_uri to a list of uris (reconstructed locally)
                    track_uri = resolved_uris
                    if "context_uri" in params:
                        del params["context_uri"]
            except:
                pass

        if isinstance(track_uri, str):
            if ":track:" in track_uri:
                params["uris"] = [track_uri]
                if "offset" not in params:
                    params["offset"] = {"uri": track_uri}
            elif ":playlist:" in track_uri or ":album:" in track_uri:
                params["context_uri"] = track_uri
        elif isinstance(track_uri, list):
            params["uris"] = track_uri

        self._safe_api_call(self.sp.start_playback, track_name="play_track", **params)

    def pause(self):
        if not self.sp:
            return
        self._safe_api_call(self.sp.pause_playback, track_name="pause_playback")

    def resume(self):
        """Resume playback with proactive device check to avoid 404s."""
        if not self.sp:
            return

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
        if not self.sp:
            return
        self._safe_api_call(
            self._execute_with_fallback, self.sp.next_track, track_name="next_track"
        )

    def previous(self):
        if not self.sp:
            return
        self._safe_api_call(
            self._execute_with_fallback, self.sp.previous_track, track_name="prev_track"
        )

    def toggle_shuffle(self, state: bool):
        if not self.sp:
            return
        self._safe_api_call(
            self._execute_with_fallback, self.sp.shuffle, state=state, track_name="toggle_shuffle"
        )

    def set_repeat(self, state: str):
        if not self.sp:
            return
        self._safe_api_call(
            self._execute_with_fallback, self.sp.repeat, state=state, track_name="set_repeat"
        )

    def transfer(self, device_id: str, force_play: bool = True):
        if not self.sp:
            return
        self._safe_api_call(
            self.sp.transfer_playback,
            device_id=device_id,
            force_play=force_play,
            track_name="transfer_playback",
        )
