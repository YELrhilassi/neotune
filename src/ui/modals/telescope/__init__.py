from textual.app import ComposeResult
from textual.widgets import OptionList, Input, TabbedContent, TabPane
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive
from textual import work, events

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.core.strings import Strings
from src.ui.modals.track_menu import TrackMenuPopup
from src.core.utils import strip_icons
from src.core.cache import CacheStore

# Components
from src.ui.modals.telescope.header import TelescopeHeader, TelescopeInput
from src.ui.modals.telescope.results import TelescopeResults
from src.ui.modals.telescope.preview import TelescopePreview

# Hooks
from src.hooks.useSpotifySearch import useSpotifySearch
from src.hooks.useFetchAlbumTracks import useFetchAlbumTracks
from src.hooks.useFetchPlaylistTracks import useFetchPlaylistTracks


class TelescopePrompt(BaseModal[str]):
    BINDINGS = [
        Binding("escape", "handle_escape", "Normal Mode / Close"),
        Binding("tab", "focus_next", "Focus Next"),
        Binding("shift+tab", "focus_previous", "Focus Previous"),
        Binding("H", "prev_category", "Previous Category"),
        Binding("L", "next_category", "Next Category"),
    ]

    input_mode = reactive("NORMAL")

    def __init__(self, initial_query: str = ""):
        super().__init__()
        self.cache = Container.resolve(CacheStore)

        saved_state = self.cache.get("telescope_state") or {}

        if not initial_query and saved_state.get("query"):
            self.initial_query = saved_state["query"]
            self.results_data = saved_state.get("results") or {
                "tracks": [],
                "albums": [],
                "playlists": [],
            }
        else:
            self.initial_query = initial_query
            self.results_data = {"tracks": [], "albums": [], "playlists": []}

        self.preview_data = []

    def on_mount(self):
        self.header = self.query_one(TelescopeHeader)
        self.input = self.header.query_one(TelescopeInput)

        self.input.focus()
        if self.initial_query:
            self.input.value = self.initial_query
            self.input.cursor_position = len(self.initial_query)

        self.search_timer = None
        self.fetch_timer = None

        if self.results_data and any(self.results_data.values()):
            self.set_timer(0.1, self._refresh_all_lists)

    def compose(self) -> ComposeResult:
        with Vertical(id="telescope-wrapper"):
            yield TelescopeHeader(id="telescope-header")
            with TabbedContent(initial="tracks", id="telescope-tabs"):
                with TabPane("Songs", id="tracks"):
                    with Horizontal(classes="telescope-body"):
                        yield TelescopeResults(classes="telescope-results", id="results-tracks")
                        yield TelescopePreview(classes="telescope-preview", id="preview-tracks")
                with TabPane("Albums", id="albums"):
                    with Horizontal(classes="telescope-body"):
                        yield TelescopeResults(classes="telescope-results", id="results-albums")
                        yield TelescopePreview(classes="telescope-preview", id="preview-albums")
                with TabPane("Playlists", id="playlists"):
                    with Horizontal(classes="telescope-body"):
                        yield TelescopeResults(classes="telescope-results", id="results-playlists")
                        yield TelescopePreview(classes="telescope-preview", id="preview-playlists")

    @property
    def active_category(self) -> str:
        try:
            return self.query_one(TabbedContent).active
        except Exception:
            return "tracks"

    @property
    def results_list(self) -> OptionList:
        return self.query_one(
            f"#results-{self.active_category} .telescope-results-list", OptionList
        )

    @property
    def preview(self) -> TelescopePreview:
        return self.query_one(f"#preview-{self.active_category}", TelescopePreview)

    @property
    def preview_list(self) -> OptionList:
        return self.preview.query_one(".telescope-preview-tracks", OptionList)

    def action_handle_escape(self):
        if self.input_mode == "NORMAL":
            self.dismiss()

    def on_telescope_input_mode_changed(self, message: TelescopeInput.ModeChanged):
        self.input_mode = message.mode

    def on_telescope_input_navigate(self, message: TelescopeInput.Navigate):
        try:
            results_list = self.results_list
            preview_list = self.preview_list
        except Exception:
            return

        if message.direction == "next":
            results_list.focus()
        elif message.direction == "prev":
            if preview_list.display:
                preview_list.focus()
            else:
                results_list.focus()
        elif message.direction == "down":
            results_list.focus()
        elif message.direction == "right":
            if preview_list.display:
                preview_list.focus()
        elif message.direction == "tab_prev":
            self.action_prev_category()
        elif message.direction == "tab_next":
            self.action_next_category()

    def action_focus_next(self):
        try:
            if self.input.has_focus:
                self.results_list.focus()
            else:
                self.input.focus()
        except Exception:
            pass

    def action_focus_previous(self):
        try:
            if self.input.has_focus:
                if self.preview_list.display:
                    self.preview_list.focus()
                else:
                    self.results_list.focus()
            else:
                self.input.focus()
        except Exception:
            pass

    def action_next_category(self):
        cats = ["tracks", "albums", "playlists"]
        idx = cats.index(self.active_category)
        self.query_one(TabbedContent).active = cats[(idx + 1) % 3]

    def action_prev_category(self):
        cats = ["tracks", "albums", "playlists"]
        idx = cats.index(self.active_category)
        self.query_one(TabbedContent).active = cats[(idx - 1) % 3]

    def on_tabbed_content_tab_activated(self, event):
        # When tab changes, populate if needed.
        self._refresh_results_list()

    def watch_input_mode(self, mode: str):
        if hasattr(self, "header"):
            hints = self.header.query_one("#telescope-hints")
            if mode == "INSERT":
                hints.update("[bold #a6e3a1]-- INSERT --[/] [dim] esc: Normal [/]")
                self.header.add_class("insert-mode")
            else:
                hints.update("[dim] [i/a] Insert • [H/L] Tabs • [h/l] Panels • [j/k] Move [/]")
                self.header.remove_class("insert-mode")
            if self.input.mode != mode:
                self.input.mode = mode

    def on_input_changed(self, event: Input.Changed):
        query = event.value
        if self.search_timer:
            self.search_timer.stop()
        if query:
            for cat in ["tracks", "albums", "playlists"]:
                try:
                    res_container = self.query_one(f"#results-{cat}", TelescopeResults)
                    res_container.show_loading()
                except Exception:
                    pass
            self.search_timer = self.set_timer(0.3, lambda: self.perform_search(query))
        else:
            self.results_data = {"tracks": [], "albums": [], "playlists": []}
            self._refresh_all_lists()

    @work(exclusive=True, thread=True)
    def perform_search(self, query: str):
        results = useSpotifySearch(query)
        self.app.call_from_thread(self._handle_search_results, results)

    def _handle_search_results(self, results):
        self.results_data = results
        self.cache.set("telescope_state", {"query": self.input.value, "results": results})
        self._refresh_all_lists()

    def _refresh_all_lists(self):
        for cat in ["tracks", "albums", "playlists"]:
            data = self.results_data.get(cat, [])
            try:
                # Update list first, then remove loading from inner OptionList
                res_container = self.query_one(f"#results-{cat}", TelescopeResults)
                res_container.update_list(cat, data)
                lst = res_container.query_one(".telescope-results-list", OptionList)
                lst.loading = False
            except Exception:
                pass

    def _refresh_results_list(self):
        # We don't need to rebuild options every time a tab is switched now.
        pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        # We only care about the currently active results list
        try:
            results_list = self.results_list
            preview = self.preview
        except Exception:
            return

        if event.option_list != results_list:
            return

        current_data = self.results_data.get(self.active_category, [])
        if (
            not current_data
            or event.option_index is None
            or event.option_index >= len(current_data)
        ):
            return

        data = current_data[event.option_index]
        preview.update_preview(self.active_category, data)

        if self.fetch_timer:
            self.fetch_timer.stop()

        if self.active_category in ["albums", "playlists"]:
            try:
                preview.query_one(".telescope-preview-tracks", OptionList).loading = True
            except Exception:
                pass

        if self.active_category == "albums":
            self.fetch_timer = self.set_timer(0.4, lambda: self.fetch_album_details(data.get("id")))
        elif self.active_category == "playlists":
            self.fetch_timer = self.set_timer(
                0.4, lambda: self.fetch_playlist_details(data.get("id"))
            )

    @work(exclusive=True, thread=True)
    def fetch_album_details(self, album_id: str):
        if not album_id:
            return
        tracks = useFetchAlbumTracks(album_id)
        self.app.call_from_thread(self._handle_preview_tracks, tracks)

    @work(exclusive=True, thread=True)
    def fetch_playlist_details(self, playlist_id: str):
        if not playlist_id:
            return
        tracks = useFetchPlaylistTracks(playlist_id)
        self.app.call_from_thread(self._handle_preview_tracks, tracks)

    def _handle_preview_tracks(self, tracks):
        self.preview_data = tracks
        try:
            preview_tracks_list = self.preview.query_one(".telescope-preview-tracks", OptionList)
            preview_tracks_list.loading = False
            self.preview.update_tracks(tracks)
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        try:
            preview_list = self.preview_list
            results_list = self.results_list
        except Exception:
            return

        if event.option_list == preview_list:
            if not self.preview_data or event.option_index >= len(self.preview_data):
                return

            track_data = self.preview_data[event.option_index]
            uri = track_data.get("uri")
            if uri:
                context_uri = None
                # If previewing an album or playlist, extract the parent context URI
                if self.active_category in ["albums", "playlists"]:
                    try:
                        results_idx = results_list.highlighted
                        if results_idx is not None:
                            parent_data = self.results_data.get(self.active_category, [])[
                                results_idx
                            ]
                            context_uri = parent_data.get("uri")
                    except Exception:
                        pass

                from src.hooks.usePlayTrack import usePlayTrack

                if usePlayTrack(uri, self.app, context_uri=context_uri):
                    self.app.update_now_playing()
            return

        if event.option_list == results_list:
            self._handle_selection(event.option_index)

    def _handle_selection(self, index: int):
        current_data = self.results_data.get(self.active_category, [])
        if not current_data or index >= len(current_data):
            return
        data = current_data[index]
        uri = data.get("uri")
        if not uri:
            return

        def generic_action_handler(action: str, uri: str):
            import threading

            def _worker():
                if not action:
                    return
                from src.hooks.usePlayTrack import usePlayTrack
                from src.hooks.useTrackRadio import useTrackRadio
                from src.hooks.useSaveTrack import useSaveTrack
                from src.hooks.useRemoveTrack import useRemoveTrack

                if action == "play":
                    # Use properly engineered native playback. If it's a playlist or album,
                    # Spotify will natively handle continuous playback using the context_uri.
                    # If it's a single track from search, it plays just that track.
                    context_uri = uri if self.active_category in ["albums", "playlists"] else None
                    if context_uri:
                        if usePlayTrack(uri, self.app, context_uri=context_uri):
                            self.app.call_from_thread(self.app.update_now_playing)
                    else:
                        if usePlayTrack(uri, self.app):
                            self.app.call_from_thread(self.app.update_now_playing)
                elif action == "radio":
                    useTrackRadio(uri, self.app)
                elif action == "save":
                    useSaveTrack(uri, self.app)
                elif action == "remove":
                    useRemoveTrack(uri, self.app)

            threading.Thread(target=_worker, daemon=True).start()

        name = data.get("name", "Unknown")
        if self.active_category == "tracks":
            artists = ", ".join([a["name"] for a in data.get("artists", [])])
            display_name = f"{strip_icons(name)} by {strip_icons(artists)}"
        else:
            display_name = strip_icons(name)

        self.app.push_screen(
            TrackMenuPopup(uri, display_name), lambda act: generic_action_handler(act, uri)
        )

    def on_unmount(self):
        try:
            from src.state.store import Store

            Store().set("mode", "NORMAL")
        except Exception:
            pass

    def on_key(self, event: events.Key):
        if self.input.has_focus:
            return

        focused_widget = self.focused
        if focused_widget is None:
            return

        if event.character == "j":
            if hasattr(focused_widget, "action_cursor_down"):
                focused_widget.action_cursor_down()
            event.prevent_default()
        elif event.character == "k":
            if hasattr(focused_widget, "action_cursor_up"):
                focused_widget.action_cursor_up()
            else:
                self.input.focus()
            event.prevent_default()
        elif event.character == "h":
            try:
                if focused_widget == self.preview_list:
                    self.results_list.focus()
                else:
                    self.input.focus()
            except Exception:
                pass
            event.prevent_default()
        elif event.character == "l":
            try:
                if focused_widget == self.results_list and self.preview_list.display:
                    self.preview_list.focus()
            except Exception:
                pass
            event.prevent_default()
        elif event.character == "U":
            if hasattr(focused_widget, "action_page_up"):
                focused_widget.action_page_up()
            event.prevent_default()
        elif event.character == "D":
            if hasattr(focused_widget, "action_page_down"):
                focused_widget.action_page_down()
            event.prevent_default()
