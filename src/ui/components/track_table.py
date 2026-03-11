import uuid
from typing import Dict, Any, List, Optional, cast, TYPE_CHECKING
from textual.widgets import DataTable
from textual import on, events
from src.core.di import Container
from src.state.store import Store
from src.ui.modals.track_menu import TrackMenuPopup
from src.hooks.track_actions import (
    play_track,
    start_track_radio,
    save_track,
    remove_saved_track,
)
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings
from src.core.debug_logger import DebugLogger

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class TrackList(DataTable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.track_data_map: Dict[str, Any] = {}
        self.debug = DebugLogger()

    def on_mount(self):
        self.border_title = Strings.TRACKS_TITLE
        self.add_columns(
            f"{Icons.TRACK} Track",
            f"{Icons.ARTIST} Artist",
            f"{Icons.ALBUM} Album",
            f"{Icons.DURATION} Duration",
        )
        self.cursor_type = "row"
        self.store = Store()  # Singleton

        # Wrap in a lambda to safely pass only what we expect, dropping kwargs
        self.store.subscribe("current_tracks", lambda val, **kw: self.safe_load_tracks(val))
        self.store.subscribe("loading_states", lambda val, **kw: self._handle_ui_change(val))

    def _handle_ui_change(self, states):
        self._handle_loading(states)

    def safe_load_tracks(self, tracks: list):
        if not self.app:
            return

        # Ensure tracks is not None and is a valid list
        if tracks is None:
            tracks = []

        import threading

        if threading.current_thread() is threading.main_thread():
            self.load_tracks(tracks)
        else:
            self.app.call_from_thread(self.load_tracks, tracks)

    def _handle_loading(self, states):
        if states and self.app:
            loading = states.get("track_list", False)
            import threading

            if threading.current_thread() is threading.main_thread():
                self.loading = loading
            else:
                self.app.call_from_thread(setattr, self, "loading", loading)

    def load_tracks(self, tracks: list):
        self.debug.debug(
            "TrackList", f"load_tracks called with {len(tracks) if tracks else 0} items"
        )
        self.clear()
        self.track_data_map = {}

        if not tracks:
            self.refresh()
            return

        for item in tracks:
            try:
                if not item or not isinstance(item, dict):
                    continue

                # Context Type (Playlist/Album)
                if item.get("type") == "context":
                    uri = item.get("uri", "")
                    name = item.get("name", "Unknown Context")
                    ctype = item.get("context_type", "playlist")
                    metadata = item.get("metadata", {})
                    unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
                    self.track_data_map[unique_key] = item
                    icon = Icons.PLAYLIST if ctype == "playlist" else Icons.ALBUM
                    artist_display = metadata.get("artists") or f"[{ctype.capitalize()}]"
                    self.add_row(
                        f"{icon} {strip_icons(name)}",
                        artist_display,
                        "Playlist" if ctype == "playlist" else strip_icons(name),
                        "-",
                        key=unique_key,
                    )
                    continue

                # Track Type
                track = item.get("track") if "track" in item else item
                if not track or not isinstance(track, dict) or "name" not in track:
                    continue

                artists_list = track.get("artists", [])
                if isinstance(artists_list, list):
                    artists = ", ".join(
                        [strip_icons(a.get("name", "Unknown")) for a in artists_list]
                    )
                else:
                    artists = "Unknown Artist"

                duration_ms = track.get("duration_ms", 0)
                duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"

                uri = track.get("uri", "unknown")
                unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
                self.track_data_map[unique_key] = track

                album_name = "Unknown Album"
                if track.get("album"):
                    album_name = track["album"].get("name", "Unknown Album")

                self.add_row(
                    f"{Icons.TRACK} {strip_icons(track['name'])}",
                    artists,
                    strip_icons(album_name),
                    duration_str,
                    key=unique_key,
                )
            except Exception as e:
                self.debug.error("TrackList", f"Row load error: {e}")
                continue

        self.debug.debug("TrackList", f"Finished loading {len(self.track_data_map)} rows")
        self.refresh()

    @on(DataTable.RowSelected)
    def handle_row_selection(self, event: DataTable.RowSelected):
        key = event.row_key.value
        if not key:
            return
        item_data = self.track_data_map.get(key)
        if not item_data:
            return

        if item_data.get("type") == "context":
            uri = item_data.get("uri")

            def _play_context():
                if not uri or ":" not in uri:
                    return
                if play_track(uri, self.app):
                    app_ref = cast("TerminalRenderer", self.app)
                    if app_ref and hasattr(app_ref, "update_now_playing"):

                        def _update0():
                            app_ref.update_now_playing(force=True)

                        app_ref.call_from_thread(_update0)

            import threading

            threading.Thread(target=_play_context, daemon=True).start()
            return

        track_data = item_data
        artists = ", ".join([a.get("name", "") for a in track_data.get("artists", [])])
        display_name = f"{track_data.get('name', 'Unknown')} by {artists}"
        context_uri = self.store.get("last_active_context")

        def on_action_selected(action: Optional[str]):
            if not action:
                return

            def _worker():
                if action == "play":
                    if context_uri and context_uri not in ["liked_songs", "recently_played"]:
                        if play_track(track_data["uri"], self.app, context_uri=context_uri):
                            app_ref = cast("TerminalRenderer", self.app)
                            if app_ref and hasattr(app_ref, "update_now_playing"):

                                def _update1():
                                    app_ref.update_now_playing(force=True)

                                app_ref.call_from_thread(_update1)
                    else:
                        all_uris = [
                            t.get("uri") for t in self.track_data_map.values() if t.get("uri")
                        ]
                        try:
                            offset_pos = list(self.track_data_map.keys()).index(key)
                        except:
                            offset_pos = 0
                        if play_track(all_uris, self.app, offset_position=offset_pos):
                            app_ref = cast("TerminalRenderer", self.app)
                            if app_ref and hasattr(app_ref, "update_now_playing"):

                                def _update2():
                                    app_ref.update_now_playing(force=True)

                                app_ref.call_from_thread(_update2)
                elif action == "radio":
                    start_track_radio(track_data["uri"], self.app)
                elif action == "save":
                    save_track(track_data["uri"], self.app)
                elif action == "remove":
                    remove_saved_track(track_data["uri"], self.app)

            import threading

            threading.Thread(target=_worker, daemon=True).start()

        self.app.push_screen(TrackMenuPopup(track_data["uri"], display_name), on_action_selected)

    def get_highlighted_track_data(self) -> Optional[dict]:
        if self.cursor_row is not None:
            keys = list(self.track_data_map.keys())
            if 0 <= self.cursor_row < len(keys):
                return self.track_data_map[keys[self.cursor_row]]
        return None
