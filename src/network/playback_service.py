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
        self._state_cache_ttl = 10.0
        self._last_devices = []
        self._last_devices_time = 0
        self._devices_cache_ttl = 5.0
        self._lock = threading.Lock()

    def get_current_playback(self, force: bool = False) -> Optional[dict[str, Any]]:
        if not self.sp:
            return self._last_playback_state
        with self._lock:
            now = time.time()
            if (
                not force
                and self._last_playback_state
                and (now - self._last_state_time < self._state_cache_ttl)
            ):
                if self._last_playback_state.get("is_playing"):
                    elapsed_ms = int((now - self._last_state_time) * 1000)
                    predicted = self._last_playback_state.copy()
                    duration = predicted.get("item", {}).get("duration_ms", 0)
                    new_progress = predicted.get("progress_ms", 0) + elapsed_ms
                    if duration > 0 and new_progress >= duration:
                        pass
                    else:
                        predicted["progress_ms"] = new_progress
                        return predicted
                else:
                    return self._last_playback_state

            state = self._safe_api_call(
                self.sp.current_playback,
                track_name="current_playback",
                min_interval=None if force else 5.0,
            )
            if state is None:
                return self._last_playback_state

            self._record_activity_from_state(state)
            self._last_playback_state = state
            self._last_state_time = now

            try:
                from src.state.store import Store

                store = Store()
                store.set("current_playback", state)
                if state.get("device"):
                    store.set("preferred_device_name", state["device"].get("name"))
            except:
                pass
            return state

    def _record_activity_from_state(self, state: dict[str, Any]):
        if not state or not state.get("is_playing"):
            return
        device = state.get("device", {})
        if device.get("name") != PlayerSettings.DEVICE_NAME:
            return
        context = state.get("context")
        if not context:
            return
        uri = context.get("uri")
        ctype = context.get("type")
        if not uri or ctype not in ["playlist", "album"]:
            return

        from src.core.activity_service import ActivityService
        from src.state.store import Store

        store = Store()
        activity = Container.resolve(ActivityService)

        if store.get("last_recorded_uri") == uri:
            return
        store.set("last_recorded_uri", uri)

        def _fetch_meta_and_record():
            try:
                from src.network.library_service import LibraryService

                library = Container.resolve(LibraryService)
                context_id = uri.split(":")[-1]
                name = f"{ctype.capitalize()}: {context_id}"
                metadata = {}
                from src.config.user_prefs import UserPreferences

                prefs = Container.resolve(UserPreferences)
                for sp in prefs.special_playlists:
                    if sp.get("uri") == uri:
                        name = sp.get("name", name)
                        metadata["artists"] = sp.get("description", "")
                        break
                if ":" in name or name.lower() in ["album", "playlist"]:
                    meta = (
                        library.get_playlist_metadata(context_id)
                        if ctype == "playlist"
                        else library.get_album_metadata(context_id)
                    )
                    if meta:
                        name = meta.get("name", name)
                        if ctype == "playlist":
                            owner = meta.get("owner", {}).get("display_name", "")
                            if owner:
                                metadata["artists"] = f"by {owner}"
                        else:
                            artists = meta.get("artists", [])
                            if artists:
                                metadata["artists"] = ", ".join(
                                    [a.get("name", "") for a in artists]
                                )
                activity.record_context_play(uri, name, ctype, metadata)
            except:
                pass

        threading.Thread(target=_fetch_meta_and_record, daemon=True).start()

    def get_devices(self, force: bool = True) -> list[dict[str, Any]]:
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
            try:
                from src.state.store import Store

                Store().set("devices", devices)
            except:
                pass
            return devices

    def find_fallback_device(self) -> Optional[str]:
        devices = self.get_devices()
        if not devices:
            return None
        for d in devices:
            if d.get("name") == PlayerSettings.DEVICE_NAME:
                return d.get("id")
        for d in devices:
            if d.get("is_active"):
                return d.get("id")
        return devices[0].get("id")

    def _execute_with_fallback(self, operation: Callable, *args, **kwargs) -> Any:
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            if "No active device" in str(e) or "NO_ACTIVE_DEVICE" in str(e):
                dev_id = self.find_fallback_device()
                if dev_id:
                    self.transfer(dev_id, force_play=True)
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
        if not self.sp:
            return
        params = {}
        if device_id:
            params["device_id"] = device_id
        if isinstance(track_uri, str) and any(
            x in track_uri for x in [":playlist:", ":album:", ":station:"]
        ):
            if not context_uri:
                context_uri = track_uri
                track_uri = None
        if context_uri:
            params["context_uri"] = context_uri
        if offset_position is not None:
            params["offset"] = {"position": int(offset_position)}
        if context_uri:
            from src.network.discovery_service import DiscoveryService

            try:
                resolved = Container.resolve(DiscoveryService).resolve_special_context(context_uri)
                if resolved:
                    track_uri = resolved
                    params.pop("context_uri", None)
            except:
                pass
        if isinstance(track_uri, str):
            if ":track:" in track_uri:
                params["uris"] = [track_uri]
                if "offset" not in params:
                    params["offset"] = {"uri": track_uri}
            else:
                params["context_uri"] = track_uri
        elif isinstance(track_uri, list):
            params["uris"] = track_uri
        self._safe_api_call(self.sp.start_playback, track_name="play_track", **params)

    def pause(self):
        if self.sp:
            self._safe_api_call(self.sp.pause_playback, track_name="pause_playback")

    def resume(self):
        if not self.sp:
            return
        state = self.get_current_playback()
        if not state or not state.get("device", {}).get("is_active"):
            dev_id = self.find_fallback_device()
            if dev_id:
                self.transfer(dev_id, force_play=True)
                return
        self._safe_api_call(
            self._execute_with_fallback,
            self.sp.start_playback,
            track_name="resume_playback",
            suppress_status_codes=[404],
        )

    def next(self):
        if self.sp:
            self._safe_api_call(
                self._execute_with_fallback, self.sp.next_track, track_name="next_track"
            )

    def previous(self):
        if self.sp:
            self._safe_api_call(
                self._execute_with_fallback, self.sp.previous_track, track_name="prev_track"
            )

    def toggle_shuffle(self, state: bool):
        if self.sp:
            self._safe_api_call(
                self._execute_with_fallback,
                self.sp.shuffle,
                state=state,
                track_name="toggle_shuffle",
            )

    def set_repeat(self, state: str):
        if self.sp:
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
        try:
            from src.state.store import Store

            store = Store()
            devices = store.get("devices", [])
            name = next((d["name"] for d in devices if d["id"] == device_id), None)
            if name:
                store.set("preferred_device_name", name)
        except:
            pass
