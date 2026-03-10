import uuid
from typing import Dict, Any, List, Optional, cast, TYPE_CHECKING
from textual.widgets import DataTable
from textual import on, events
from textual.binding import Binding
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

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class TrackList(DataTable):
    """
    Main component for displaying track lists.
    """

    # We do NOT override BINDINGS with an empty list.
    # DataTable handles enter (select-row) by default.

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.track_data_map: Dict[str, Any] = {}

    def on_mount(self):
        self.border_title = Strings.TRACKS_TITLE
        self.add_columns(
            f"{Icons.TRACK} Track",
            f"{Icons.ARTIST} Artist",
            f"{Icons.ALBUM} Album",
            f"{Icons.DURATION} Duration",
        )
        self.cursor_type = "row"
        self.store = Container.resolve(Store)

        self.store.subscribe("current_tracks", self.load_tracks)
        self.store.subscribe("loading_states", self._handle_loading)

    def _handle_loading(self, states):
        if states:
            self.loading = states.get("track_list", False)

    def load_tracks(self, tracks: list):
        self.clear()
        if not tracks:
            return

        self.track_data_map = {}

        for item in tracks:
            if not item or not isinstance(item, dict):
                continue
            track = item.get("track", item)
            if not track or not isinstance(track, dict) or "name" not in track:
                continue

            artists = ", ".join([strip_icons(a.get("name", "")) for a in track.get("artists", [])])
            duration_ms = track.get("duration_ms", 0)
            duration_min = duration_ms // 60000
            duration_sec = (duration_ms % 60000) // 1000
            duration_str = f"{duration_min}:{duration_sec:02d}"

            # Use UUID to prevent DuplicateKey error
            t_uri = track.get("uri", "unknown")
            unique_key = f"{t_uri}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = track

            self.add_row(
                strip_icons(track["name"]),
                artists,
                strip_icons(track.get("album", {}).get("name", "Unknown")),
                duration_str,
                key=unique_key,
            )

    @on(DataTable.RowSelected)
    def handle_row_selection(self, event: DataTable.RowSelected):
        """Standard handler for Enter or Click on a row."""
        key = event.row_key.value
        if not key:
            return

        track_data = self.track_data_map.get(key)
        if not track_data:
            return

        artists = ", ".join([a.get("name", "") for a in track_data.get("artists", [])])
        display_name = f"{track_data.get('name', 'Unknown')} by {artists}"

        context_uri = self.store.get("last_active_context")

        def on_action_selected(action: Optional[str]):
            if not action:
                return

            import threading
            from src.ui.terminal_renderer import TerminalRenderer

            if not isinstance(self.app, TerminalRenderer):
                return
            app = cast(TerminalRenderer, self.app)

            def _worker():
                if action == "play":
                    if (
                        context_uri
                        and context_uri != "liked_songs"
                        and context_uri != "recently_played"
                    ):
                        if play_track(track_data["uri"], app, context_uri=context_uri):
                            app.call_from_thread(app.update_now_playing)
                    else:
                        # Fallback for search results or liked songs
                        all_uris = [
                            t.get("uri") for t in self.track_data_map.values() if t.get("uri")
                        ]
                        try:
                            keys_list = list(self.track_data_map.keys())
                            offset_pos = keys_list.index(key)
                        except ValueError:
                            offset_pos = 0
                        if play_track(all_uris, app, offset_position=offset_pos):
                            app.call_from_thread(app.update_now_playing)
                elif action == "radio":
                    start_track_radio(track_data["uri"], app)
                elif action == "save":
                    save_track(track_data["uri"], app)
                elif action == "remove":
                    remove_saved_track(track_data["uri"], app)

            threading.Thread(target=_worker, daemon=True).start()

        self.app.push_screen(TrackMenuPopup(track_data["uri"], display_name), on_action_selected)
