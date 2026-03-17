import threading
import uuid
from typing import Any

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable

from src.core.debug_logger import DebugLogger
from src.core.di import Container
from src.core.icons import Icons
from src.core.utils import strip_icons
from src.hooks.usePlayTrack import usePlayTrack as play_track
from src.network.spotify_network import SpotifyNetwork
from src.state.store import Store
from src.state.virtual_queue import VirtualQueueManager


class QueueTable(DataTable):
    BINDINGS = [
        Binding("x", "remove_from_queue", "Remove", show=True),
        Binding("delete", "remove_from_queue", "Remove", show=False),
        Binding("c", "clear_queue", "Clear", show=True),
        Binding("enter", "play_track", "Play", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.track_data_map: dict[str, Any] = {}
        self.debug = DebugLogger()
        self.store = Store()
        self.network = Container.resolve(SpotifyNetwork)


    def on_mount(self):
        self.add_columns(f"{Icons.TRACK} Track", f"{Icons.ARTIST} Artist", f"{Icons.DURATION} Duration")
        self.cursor_type = "row"
        self.show_header = True

        self.store.subscribe("queue", lambda val, **kw: self.safe_load_queue(val))

    def _update_dynamic_column_widths(self):
        if not self.columns:
            return
        cols = list(self.columns.values())
        if len(cols) == 3:
            total_w = max(10, self.size.width - 2)
            cols[2].auto_width = False
            cols[2].width = max(8, cols[2].content_width)

            remaining = max(5, total_w - cols[2].width - 4)
            c0_w = max(len("Track") + 2, cols[0].content_width)
            c1_w = max(len("Artist") + 2, cols[1].content_width)
            sum_c = c0_w + c1_w

            if sum_c > 0:
                cols[0].width = max(len("Track") + 2, int(remaining * (c0_w / sum_c)))
                cols[1].width = remaining - cols[0].width

            for c in cols[:2]:
                c.auto_width = False

            self.refresh()

    def on_resize(self, event: events.Resize):
        self.app.call_later(self._update_dynamic_column_widths)

    def safe_load_queue(self, queue_data: dict):
        if not self.app:
            return

        if threading.current_thread() is threading.main_thread():
            self.load_queue_data(queue_data)
        else:
            self.app.call_from_thread(self.load_queue_data, queue_data)

    def load_queue_data(self, queue_data: dict):
        if not queue_data:
            queue_data = {}

        saved_row = self.cursor_row

        self.clear()
        self.track_data_map = {}

        for c in self.columns.values():
            c.auto_width = True

        vq_manager = VirtualQueueManager()
        filtered_queue = vq_manager.filter_queue(queue_data)

        # 1. Currently Playing
        currently_playing = filtered_queue.get("currently_playing")
        if currently_playing and currently_playing.get("name"):
            uri = currently_playing.get("uri", "")
            unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = currently_playing

            track_name = strip_icons(currently_playing.get("name", ""))
            artists_list = currently_playing.get("artists", [])
            artists = ", ".join([strip_icons(a.get("name", "")) for a in artists_list])
            duration_ms = currently_playing.get("duration_ms", 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"

            col1 = f"[bold #a6e3a1]{Icons.PLAY} {track_name}[/]"
            col2 = f"[bold #a6e3a1]{artists}[/]"
            col3 = f"[bold #a6e3a1]{duration_str}[/]"
            self.add_row(col1, col2, col3, key=unique_key)

        # 2. Up Next
        for track in filtered_queue.get("queue", []):
            if not track or not track.get("name"):
                continue

            uri = track.get("uri", "")
            unique_key = f"{uri}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = track

            track_name = strip_icons(track.get("name", ""))
            artists_list = track.get("artists", [])
            artists = ", ".join([strip_icons(a.get("name", "")) for a in artists_list])
            duration_ms = track.get("duration_ms", 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"

            self.add_row(track_name, f"[dim]{artists}[/]", duration_str, key=unique_key)

        if saved_row is not None and len(self.track_data_map) > 0:
            row_to_restore = min(saved_row, len(self.track_data_map) - 1)
            self.move_cursor(row=row_to_restore, column=0, animate=False)

        self._update_dynamic_column_widths()
        self.refresh()

    def get_highlighted_track(self):
        if self.cursor_row is not None:
            keys = list(self.track_data_map.keys())
            if 0 <= self.cursor_row < len(keys):
                return self.track_data_map[keys[self.cursor_row]]
        return None

    def action_remove_from_queue(self):
        track = self.get_highlighted_track()
        if track and track.get("uri"):
            from src.state.virtual_queue import VirtualQueueManager
            VirtualQueueManager().mark_skipped(track["uri"])

            # Re-fetch queue or just trigger refresh
            def _worker():
                queue_data = self.network.get_queue()
                self.store.set("queue", queue_data)
            threading.Thread(target=_worker, daemon=True).start()

    def action_clear_queue(self):
        def _worker():
            queue_data = self.network.get_queue()
            if queue_data and queue_data.get("queue"):
                vq = VirtualQueueManager()
                for t in queue_data["queue"]:
                    uri = t.get("uri")
                    if uri:
                        vq.mark_skipped(uri)
                # Re-fetch
                new_q = self.network.get_queue()
                self.store.set("queue", new_q)
        threading.Thread(target=_worker, daemon=True).start()


    def action_play_track(self):
        track = self.get_highlighted_track()
        if not track or not track.get("uri"):
            return

        def _worker():
            # If it's the currently playing track, just seek to 0
            if track.get("name") and getattr(self, "track_data_map", None):
                # Find index of selected track
                try:
                    keys = list(self.track_data_map.keys())
                    selected_key = next(k for k, v in self.track_data_map.items() if v == track)
                    idx = keys.index(selected_key)
                except:
                    idx = -1

                if idx == 0:
                    # Seek to 0
                    try:
                        self.network.playback.sp.seek_track(0)
                        app_ref = self.app
                        if hasattr(app_ref, "update_now_playing"):
                            app_ref.call_from_thread(app_ref.update_now_playing, force=True)
                    except:
                        pass
                elif idx > 0:
                    # Skip to the track
                    import time
                    app_ref = self.app
                    if hasattr(app_ref, "notify"):
                        app_ref.call_from_thread(app_ref.notify, f"Skipping {idx} tracks...")

                    for i in range(idx):
                        try:
                            self.network.next_track()
                            if i < idx - 1:
                                time.sleep(0.3)
                        except:
                            pass

                    if hasattr(app_ref, "update_now_playing"):
                        time.sleep(0.5)
                        app_ref.call_from_thread(app_ref.update_now_playing, force=True)
                else:
                    # Fallback
                    if play_track(track["uri"], self.app):
                        app_ref = self.app
                        if hasattr(app_ref, "update_now_playing"):
                            app_ref.call_from_thread(app_ref.update_now_playing, force=True)

        threading.Thread(target=_worker, daemon=True).start()


    @on(DataTable.RowSelected)
    def handle_row_selection(self, event: DataTable.RowSelected):
        self.action_play_track()

class QueuePanel(Vertical):
    def compose(self) -> ComposeResult:
        yield QueueTable(id="queue-table")

    def on_mount(self):
        self.border_title = "🎵 Queue"
        self.store = Store()

        # We need to refresh the queue periodically or when requested
        self.store.subscribe("queue_visible", self.on_visibility_changed)

    def on_visibility_changed(self, is_visible, **kwargs):
        if is_visible:
            self.add_class("-visible")
            # Trigger a fetch
            def _worker():
                network = Container.resolve(SpotifyNetwork)
                q = network.get_queue()
                self.store.set("queue", q)
            threading.Thread(target=_worker, daemon=True).start()
        else:
            self.remove_class("-visible")
