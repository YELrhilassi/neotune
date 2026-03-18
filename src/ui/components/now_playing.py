from textual.app import ComposeResult
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from src.core.di import Container
from src.state.store import Store
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings
from src.network.spotify_network import SpotifyNetwork
from textual import on


class ClickableLabel(Label):
    """A label that can be clicked to trigger navigation."""

    def __init__(
        self, text: str = "", uri: str | None = None, nav_type: str | None = None, **kwargs
    ):
        super().__init__(text, **kwargs)
        self.uri: str | None = uri
        self.nav_type: str | None = nav_type

    def on_click(self) -> None:
        if self.uri and self.app:
            self.app.post_message(
                NavigateToEvent(
                    self.nav_type,
                    self.uri,
                    self.uri.split(":")[-1] if ":" in self.uri else self.uri,
                )
            )


class NavigateToEvent(Message):
    """Message sent when user clicks on a navigatable element."""

    def __init__(self, nav_type: str | None, uri: str, id: str):
        super().__init__()
        self.nav_type = nav_type
        self.uri = uri
        self.id = id


class NowPlaying(Static):
    """Compact now playing bar with track info, progress, and controls."""

    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", show=False),
        Binding("n", "next_track", "Next Track", show=False),
        Binding("p", "prev_track", "Previous Track", show=False),
        Binding("s", "toggle_shuffle", "Toggle Shuffle", show=False),
        Binding("r", "cycle_repeat", "Cycle Repeat", show=False),
        Binding("l", "toggle_like", "Like Track", show=False),
    ]

    current_track = reactive(None)
    current_artist = reactive(None)
    current_album = reactive(None)
    is_playing = reactive(False)
    progress_pct = reactive(0)
    volume_pct = reactive(0)
    shuffle_state = reactive(False)
    repeat_state = reactive("off")
    is_saved = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal(id="np-container"):
            # Left: Track Info (40%)
            with Vertical(id="np-info"):
                with Horizontal(id="np-track-row"):
                    yield Static(Icons.PAUSE, id="np-play-icon")
                    yield ClickableLabel(
                        Strings.PAUSED_OR_NOTHING, id="np-track-name", nav_type="track"
                    )
                with Horizontal(id="np-meta-row"):
                    yield ClickableLabel("", id="np-artist-name", nav_type="artist")
                    yield Static("•", id="np-meta-sep")
                    yield ClickableLabel("", id="np-album-name", nav_type="album")

            # Center: Progress (35%)
            with Horizontal(id="np-progress-section"):
                yield Label("--:--", id="np-time-current")
                yield ProgressBar(
                    id="np-progress-bar", total=100, show_percentage=False, show_eta=False
                )
                yield Label("--:--", id="np-time-total")

            # Right: Controls (25%)
            with Horizontal(id="np-controls"):
                yield Static(Icons.HEART_EMPTY, id="np-like-btn", classes="icon-btn")
                yield Static(Icons.SHUFFLE_OFF, id="np-shuffle-btn", classes="icon-btn")
                yield Static(Icons.SKIP_BACKWARD, id="np-prev-btn", classes="icon-btn")
                yield Static(Icons.PAUSE, id="np-play-btn", classes="icon-btn")
                yield Static(Icons.SKIP_FORWARD, id="np-next-btn", classes="icon-btn")
                yield Static(Icons.REPEAT_OFF, id="np-repeat-btn", classes="icon-btn")
                # Volume section
                with Horizontal(id="np-volume-section"):
                    yield Static(Icons.VOLUME_MED, id="np-volume-icon")
                    yield ProgressBar(
                        id="np-volume-bar", total=100, show_percentage=False, show_eta=False
                    )
                    yield Label("--%", id="np-volume-text")

    def on_mount(self):
        self.store = Store()
        self.network = Container.resolve(SpotifyNetwork)

        self.store.subscribe("current_playback", lambda val, **kw: self.safe_update_playback(val))
        self.store.subscribe(
            "preferred_device_name",
            lambda val, **kw: self.safe_update_playback(self.store.get("current_playback")),
        )

    def safe_update_playback(self, playback: dict | None):
        if not self.app:
            return

        import threading

        if threading.current_thread() is threading.main_thread():
            self.update_playback(playback)
        else:
            self.app.call_from_thread(self.update_playback, playback)

    def update_playback(self, playback: dict | None):
        try:
            play_icon_lbl = self.query_one("#np-play-icon", Static)
            track_lbl = self.query_one("#np-track-name", ClickableLabel)
            artist_lbl = self.query_one("#np-artist-name", ClickableLabel)
            album_lbl = self.query_one("#np-album-name", ClickableLabel)
            shuffle_btn = self.query_one("#np-shuffle-btn", Static)
            repeat_btn = self.query_one("#np-repeat-btn", Static)
            play_btn = self.query_one("#np-play-btn", Static)
            like_btn = self.query_one("#np-like-btn", Static)
            progress_bar = self.query_one("#np-progress-bar", ProgressBar)
            time_current = self.query_one("#np-time-current", Label)
            time_total = self.query_one("#np-time-total", Label)
        except Exception:
            return

        if playback and playback.get("item"):
            item = playback["item"]
            if not isinstance(item, dict):
                return

            artists_list = item.get("artists", [])
            artists = strip_icons(", ".join([a.get("name", "Unknown") for a in artists_list]))
            track_name = strip_icons(item.get("name", "Unknown Track"))

            track_uri = item.get("uri", "")
            artist_uris = [a.get("uri", "") for a in artists_list if a.get("uri")]
            artist_uri = artist_uris[0] if artist_uris else ""

            album_data = item.get("album", {})
            album_name = strip_icons(album_data.get("name", ""))
            album_uri = album_data.get("uri", "")

            is_playing = playback.get("is_playing", False)

            play_icon_lbl.update(Icons.PLAY if is_playing else Icons.PAUSE)

            if is_playing:
                track_lbl.update(f"{track_name}")
                track_lbl.styles.color = "#a6e3a1"
            else:
                track_lbl.update(f"{track_name}")
                track_lbl.styles.color = "#f38ba8"
            track_lbl.uri = track_uri
            track_lbl.nav_type = "track"

            artist_lbl.update(artists)
            artist_lbl.uri = artist_uri
            artist_lbl.nav_type = "artist"

            if album_name:
                album_lbl.update(album_name)
                album_lbl.uri = album_uri
                album_lbl.nav_type = "album"
                album_lbl.styles.display = "block"
                self.query_one("#np-meta-sep").styles.display = "block"
            else:
                album_lbl.styles.display = "none"
                self.query_one("#np-meta-sep").styles.display = "none"

            shuffle_state = playback.get("shuffle_state", False)
            shuffle_icon = Icons.SHUFFLE_ON if shuffle_state else Icons.SHUFFLE_OFF
            shuffle_btn.update(shuffle_icon)
            shuffle_btn.remove_class("active")
            if shuffle_state:
                shuffle_btn.add_class("active")

            repeat_state = playback.get("repeat_state", "off")
            repeat_btn.remove_class("active")
            repeat_btn.remove_class("track")
            if repeat_state == "context":
                repeat_icon = Icons.REPEAT_CONTEXT
                repeat_btn.add_class("active")
            elif repeat_state == "track":
                repeat_icon = Icons.REPEAT_TRACK
                repeat_btn.add_class("track")
            else:
                repeat_icon = Icons.REPEAT_OFF
            repeat_btn.update(repeat_icon)

            play_btn.update(Icons.PAUSE if is_playing else Icons.PLAY)

            self._check_saved_status(track_uri)

            progress_ms = playback.get("progress_ms", 0)
            duration_ms = item.get("duration_ms", 0)
            if duration_ms > 0:
                progress_bar.total = duration_ms
                progress_bar.progress = progress_ms

            current_min, current_sec = divmod(progress_ms // 1000, 60)
            total_min, total_sec = divmod(duration_ms // 1000, 60)
            time_current.update(f"{current_min}:{current_sec:02d}")
            time_total.update(f"{total_min}:{total_sec:02d}")
        else:
            device_name = self.store.get("preferred_device_name") or "No Device"
            play_icon_lbl.update(Icons.PAUSE)
            track_lbl.update(f"{Strings.PAUSED_OR_NOTHING}")
            track_lbl.styles.color = "#6c7086"
            track_lbl.uri = None
            artist_lbl.update("")
            artist_lbl.uri = None
            album_lbl.update("")
            album_lbl.uri = None
            self.query_one("#np-meta-sep").styles.display = "none"
            shuffle_btn.update(Icons.SHUFFLE_OFF)
            shuffle_btn.remove_class("active")
            repeat_btn.update(Icons.REPEAT_OFF)
            repeat_btn.remove_class("active")
            repeat_btn.remove_class("track")
            play_btn.update(Icons.PLAY)
            like_btn.update(Icons.HEART_EMPTY)
            like_btn.remove_class("liked")

            progress_bar.total = None
            progress_bar.progress = 0
            time_current.update("--:--")
            time_total.update("--:--")

    def _check_saved_status(self, track_uri: str):
        """Check if the current track is saved."""
        import threading

        def check():
            try:
                if not track_uri:
                    return
                track_id = track_uri.split(":")[-1]
                result = self.network.library.check_saved_tracks([track_id])
                is_saved = result[0] if result else False

                def update_ui():
                    like_btn = self.query_one("#np-like-btn", Static)
                    like_btn.update(Icons.HEART_FILL if is_saved else Icons.HEART_EMPTY)
                    like_btn.remove_class("liked")
                    if is_saved:
                        like_btn.add_class("liked")

                if self.app:
                    self.app.call_from_thread(update_ui)
            except Exception:
                pass

        threading.Thread(target=check, daemon=True).start()

    def on_static_click(self, event) -> None:
        """Handle clicks on Static widgets (icon buttons)."""
        widget_id = event.static.id

        if widget_id == "np-play-btn":
            self.action_toggle_play()
        elif widget_id == "np-next-btn":
            self.action_next_track()
        elif widget_id == "np-prev-btn":
            self.action_prev_track()
        elif widget_id == "np-shuffle-btn":
            self.action_toggle_shuffle()
        elif widget_id == "np-repeat-btn":
            self.action_cycle_repeat()
        elif widget_id == "np-like-btn":
            self.action_toggle_like()

    def action_toggle_play(self):
        from src.hooks.track_actions import play_pause

        play_pause(self.app)

    def action_next_track(self):
        from src.hooks.track_actions import next_track

        next_track(self.app)

    def action_prev_track(self):
        from src.hooks.track_actions import previous_track

        previous_track(self.app)

    def action_toggle_shuffle(self):
        from src.hooks.track_actions import toggle_shuffle

        toggle_shuffle(self.app)

    def action_cycle_repeat(self):
        from src.hooks.track_actions import cycle_repeat

        cycle_repeat(self.app)

    def action_toggle_like(self):
        playback = self.store.get("current_playback")
        if playback and playback.get("item"):
            track_uri = playback["item"].get("uri")
            if track_uri:
                from src.hooks.track_actions import toggle_saved

                toggle_saved(track_uri, self.app)
                self._check_saved_status(track_uri)

    def on_navigate_to_event(self, event: NavigateToEvent) -> None:
        """Handle navigation requests from clickable labels."""
        if event.nav_type and event.id:
            self._navigate_to(event.nav_type, event.id)

    def _navigate_to(self, nav_type: str, entity_id: str):
        """Navigate to artist, album, or track view."""
        import threading

        def navigate():
            try:
                if nav_type == "artist":
                    tracks = self.network.library.get_artist_top_tracks(entity_id)
                    self.app.call_from_thread(self.store.set, "current_tracks", tracks)
                elif nav_type == "album":
                    tracks = self.network.library.get_album_tracks(entity_id)
                    self.app.call_from_thread(self.store.set, "current_tracks", tracks)
                elif nav_type == "track":
                    from src.ui.components.track_table import TrackList

                    track_list = self.app.query_one(TrackList)
                    if track_list:
                        track_list.focus_item_by_uri(f"spotify:track:{entity_id}")
            except Exception:
                pass

        threading.Thread(target=navigate, daemon=True).start()
