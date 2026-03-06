from textual.app import ComposeResult
from textual.widgets import OptionList, Input
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive
from textual import work, events

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.core.strings import Strings
from src.ui.modals.track_menu import TrackMenuPopup
from src.core.utils import strip_icons

# Components
from src.ui.modals.telescope.header import TelescopeHeader
from src.ui.modals.telescope.tabs import TelescopeTabs
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

    active_category = reactive("tracks")
    input_mode = reactive("NORMAL")

    def __init__(self, initial_query: str = ""):
        super().__init__()
        self.initial_query = initial_query
        self.results_data = {"tracks": [], "albums": [], "playlists": []}
        self.preview_data = []

    def on_mount(self):
        self.header = self.query_one(TelescopeHeader)
        self.tabs = self.query_one(TelescopeTabs)
        self.results_list = self.query_one(TelescopeResults)
        self.preview = self.query_one(TelescopePreview)
        self.input = self.header.query_one(Input)
        
        # Start in results list or header but in NORMAL mode
        self.input.focus()
        if self.initial_query:
            self.input.value = self.initial_query
            self.input.cursor_position = len(self.initial_query)
            
        self.search_timer = None
        self.fetch_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="telescope-wrapper"):
            yield TelescopeHeader(id="telescope-header")
            yield TelescopeTabs(id="telescope-tabs")
            with Horizontal(id="telescope-body"):
                yield TelescopeResults(id="telescope-results")
                yield TelescopePreview(id="telescope-preview")

    def action_handle_escape(self):
        if self.input_mode == "INSERT":
            self.input_mode = "NORMAL"
        else:
            self.dismiss()

    def action_focus_next(self):
        if self.input.has_focus:
            self.results_list.focus()
        else:
            self.input.focus()

    def action_focus_previous(self):
        if self.input.has_focus:
            if self.preview.query_one("#telescope-preview-tracks").display:
                self.preview.query_one("#telescope-preview-tracks").focus()
            else:
                self.results_list.focus()
        else:
            self.input.focus()

    def action_next_category(self):
        cats = ["tracks", "albums", "playlists"]
        idx = cats.index(self.active_category)
        self.active_category = cats[(idx + 1) % 3]

    def action_prev_category(self):
        cats = ["tracks", "albums", "playlists"]
        idx = cats.index(self.active_category)
        self.active_category = cats[(idx - 1) % 3]

    def watch_active_category(self, new_cat: str):
        if hasattr(self, "tabs"):
            self.tabs.update_tabs(new_cat)
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

    def on_input_changed(self, event: Input.Changed):
        if self.input_mode == "NORMAL" and event.value != self.initial_query:
            # This is a safeguard but usually handled by on_key prevention
            pass

        query = event.value
        if self.search_timer:
            self.search_timer.stop()
        if query:
            self.search_timer = self.set_timer(0.3, lambda: self.perform_search(query))
        else:
            self.results_data = {"tracks": [], "albums": [], "playlists": []}
            self._refresh_results_list()

    @work(exclusive=True, thread=True)
    def perform_search(self, query: str):
        results = useSpotifySearch(query)
        self.app.call_from_thread(self._handle_search_results, results)

    def _handle_search_results(self, results):
        self.results_data = results
        self._refresh_results_list()

    def _refresh_results_list(self):
        data = self.results_data.get(self.active_category, [])
        self.results_list.update_list(self.active_category, data)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        if event.option_list.id == "telescope-preview-tracks":
            return

        current_data = self.results_data.get(self.active_category, [])
        if not current_data or event.option_index is None or event.option_index >= len(current_data):
            return
            
        data = current_data[event.option_index]
        self.preview.update_preview(self.active_category, data)
        
        if self.fetch_timer: self.fetch_timer.stop()
        
        if self.active_category == "albums":
            self.fetch_timer = self.set_timer(0.4, lambda: self.fetch_album_details(data.get('id')))
        elif self.active_category == "playlists":
            self.fetch_timer = self.set_timer(0.4, lambda: self.fetch_playlist_details(data.get('id')))

    @work(exclusive=True, thread=True)
    def fetch_album_details(self, album_id: str):
        if not album_id: return
        tracks = useFetchAlbumTracks(album_id)
        self.app.call_from_thread(self._handle_preview_tracks, tracks)

    @work(exclusive=True, thread=True)
    def fetch_playlist_details(self, playlist_id: str):
        if not playlist_id: return
        tracks = useFetchPlaylistTracks(playlist_id)
        self.app.call_from_thread(self._handle_preview_tracks, tracks)

    def _handle_preview_tracks(self, tracks):
        self.preview_data = tracks
        self.preview.update_tracks(tracks)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option_list.id == "telescope-preview-tracks":
            if not self.preview_data or event.option_index >= len(self.preview_data):
                return
            uri = self.preview_data[event.option_index].get("uri")
            if uri:
                from src.hooks.usePlayTrack import usePlayTrack
                if usePlayTrack(uri, self.app): self.app.update_now_playing()
            return
            
        self._handle_selection(event.option_index)

    def _handle_selection(self, index: int):
        current_data = self.results_data.get(self.active_category, [])
        if not current_data or index >= len(current_data): return
        data = current_data[index]
        uri = data.get("uri")
        if not uri: return

        def generic_action_handler(action: str, uri: str):
            if not action: return
            from src.hooks.usePlayTrack import usePlayTrack
            from src.hooks.useTrackRadio import useTrackRadio
            from src.hooks.useSaveTrack import useSaveTrack
            from src.hooks.useRemoveTrack import useRemoveTrack
            
            if action == "play":
                if usePlayTrack(uri, self.app): self.app.update_now_playing()
            elif action == "radio": useTrackRadio(uri, self.app)
            elif action == "save": useSaveTrack(uri, self.app)
            elif action == "remove": useRemoveTrack(uri, self.app)

        name = data.get("name", "Unknown")
        if self.active_category == "tracks":
            artists = ", ".join([a['name'] for a in data.get('artists', [])])
            display_name = f"{strip_icons(name)} by {strip_icons(artists)}"
        else:
            display_name = strip_icons(name)

        self.app.push_screen(TrackMenuPopup(uri, display_name), lambda act: generic_action_handler(act, uri))

    def on_unmount(self):
        try:
            from src.ui.components.status_bar import StatusBar
            self.app.query_one(StatusBar).mode = "NORMAL"
        except Exception: pass

    def on_key(self, event: events.Key):
        # Mode handling for the Header Input
        if self.input.has_focus:
            if self.input_mode == "NORMAL":
                if event.character == "i":
                    self.input_mode = "INSERT"
                    event.prevent_default()
                    return
                elif event.character == "a":
                    self.input_mode = "INSERT"
                    self.input.cursor_position += 1
                    event.prevent_default()
                    return
                elif event.key == "down":
                    self.results_list.focus()
                    event.prevent_default()
                    return
                # In Normal mode, don't let characters pass to Input
                if event.character and len(event.character) == 1:
                    event.prevent_default()
                    return
            else:
                # INSERT Mode
                if event.key == "escape":
                    self.input_mode = "NORMAL"
                    event.prevent_default()
                    return
                return # Let Input handle keys

        focused_widget = self.focused
        if focused_widget is None: return

        if event.character == "j":
            if hasattr(focused_widget, "action_cursor_down"): focused_widget.action_cursor_down()
            event.prevent_default()
        elif event.character == "k":
            if hasattr(focused_widget, "action_cursor_up"): focused_widget.action_cursor_up()
            else: self.input.focus()
            event.prevent_default()
        elif event.character == "h":
            if focused_widget.id == "telescope-preview-tracks": self.results_list.focus()
            else: self.input.focus()
            event.prevent_default()
        elif event.character == "l":
            if focused_widget.id == "telescope-results" and self.preview.query_one("#telescope-preview-tracks").display:
                self.preview.query_one("#telescope-preview-tracks").focus()
            event.prevent_default()
        elif event.character == "U":
            if hasattr(focused_widget, "action_page_up"): focused_widget.action_page_up()
            event.prevent_default()
        elif event.character == "D":
            if hasattr(focused_widget, "action_page_down"): focused_widget.action_page_down()
            event.prevent_default()
