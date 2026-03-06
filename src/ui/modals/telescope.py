from textual.app import ComposeResult
from textual.widgets import OptionList, Input, Static, Label
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.markup import escape
from textual import work, events

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.ui.modals.track_menu import TrackMenuPopup
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings
from src.config.user_prefs import UserPreferences

class TelescopePrompt(BaseModal[str]):
    BINDINGS = [
        Binding("escape", "dismiss_or_focus_input", "Close / Focus Input"),
        Binding("tab", "focus_next", "Focus Next"),
        Binding("shift+tab", "focus_previous", "Focus Previous"),
    ]

    def __init__(self, initial_query: str = ""):
        super().__init__()
        self.initial_query = initial_query
        self.results_data = []

    def on_mount(self):
        self.network = Container.resolve(SpotifyNetwork)
        self.user_prefs = Container.resolve(UserPreferences)
        
        self.input = self.query_one("#telescope-input", Input)
        self.results_list = self.query_one("#telescope-results", OptionList)
        self.preview_info = self.query_one("#telescope-preview-info", Static)
        self.preview_tracks = self.query_one("#telescope-preview-tracks", OptionList)
        self.preview_tracks.display = False
        
        self.input.focus()
        if self.initial_query:
            self.input.value = self.initial_query
            self.input.cursor_position = len(self.initial_query)
            
        self.search_timer = None
        self.fetch_timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="telescope-wrapper"):
            with Horizontal(id="telescope-header"):
                yield Label("🔍", id="telescope-icon")
                yield Input(placeholder="Search Tracks, Albums & Playlists...", id="telescope-input")
            with Horizontal(id="telescope-body"):
                yield OptionList(id="telescope-results")
                with Vertical(id="telescope-preview"):
                    yield Static(Strings.SELECT_TRACK, id="telescope-preview-info")
                    yield OptionList(id="telescope-preview-tracks")

    def action_dismiss_or_focus_input(self):
        if self.input.has_focus:
            self.dismiss()
        else:
            self.input.focus()

    def action_focus_next(self):
        focusables = [self.input, self.results_list]
        if self.preview_tracks.display:
            focusables.append(self.preview_tracks)
            
        if self.focused in focusables:
            idx = focusables.index(self.focused)
            next_idx = (idx + 1) % len(focusables)
            focusables[next_idx].focus()
        else:
            self.input.focus()

    def action_focus_previous(self):
        focusables = [self.input, self.results_list]
        if self.preview_tracks.display:
            focusables.append(self.preview_tracks)
            
        if self.focused in focusables:
            idx = focusables.index(self.focused)
            next_idx = (idx - 1) % len(focusables)
            focusables[next_idx].focus()
        else:
            self.input.focus()

    def on_input_changed(self, event: Input.Changed):
        query = event.value
        if self.search_timer:
            self.search_timer.stop()
            
        if query:
            self.search_timer = self.set_timer(0.3, lambda: self.perform_search(query))
        else:
            self.results_list.clear_options()
            self.results_data = []
            self.preview_info.update(Strings.SELECT_TRACK)
            self.preview_tracks.display = False

    @work(exclusive=True, thread=True)
    def perform_search(self, query: str):
        try:
            results = self.network.search(query, "track,album,playlist")
            if results is None:
                results = []
            self.app.call_from_thread(self._update_results, results)
        except Exception as e:
            self.app.call_from_thread(self.app.notify, f"Search failed: {e}", severity="error")

    def _update_results(self, results):
        self.results_data = []
        self.results_list.clear_options()
        self.preview_tracks.display = False
        
        if not results:
            self.results_list.add_option(Strings.NO_RESULTS)
            self.preview_info.update(Strings.NO_RESULTS)
            return
            
        for item in results:
            item_type = item.get("_qtype")
            data = item.get("data")
            
            if data is None: # Skip if data is None
                continue

            if item_type == "track":
                artists = ", ".join([a['name'] for a in data.get('artists', []) if a.get('name')])
                clean_name = strip_icons(data.get('name', 'Unknown Track'))
                self.results_data.append({"type": "track", "data": data, "uri": data.get("uri")})
                self.results_list.add_option(f"{Icons.TRACK} {clean_name} - {strip_icons(artists)}")
            elif item_type == "album":
                artists = ", ".join([a['name'] for a in data.get('artists', []) if a.get('name')])
                clean_name = strip_icons(data.get('name', 'Unknown Album'))
                self.results_data.append({"type": "album", "data": data, "uri": data.get("uri")})
                self.results_list.add_option(f"{Icons.ALBUM} {clean_name} - {strip_icons(artists)}")
            elif item_type == "playlist":
                clean_name = strip_icons(data.get('name', 'Unknown Playlist'))
                owner = data.get('owner', {}).get('display_name', 'Unknown')
                self.results_data.append({"type": "playlist", "data": data, "uri": data.get("uri")})
                self.results_list.add_option(f"{Icons.PLAYLIST} {clean_name} - {strip_icons(owner)}")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        # Ignore highlights from the preview tracks list itself
        if event.option_list.id == "telescope-preview-tracks":
            return

        if not self.results_data or event.option_index is None or event.option_index >= len(self.results_data):
            return
            
        item = self.results_data[event.option_index]
        self.preview_tracks.display = False
        
        if self.fetch_timer:
            self.fetch_timer.stop()

        if item["type"] == "track":
            track = item.get("data")
            if not track: return

            artists = ", ".join([strip_icons(a['name']) for a in track.get('artists', []) if a and a.get('name')])
            album_name = strip_icons(track.get('album', {}).get('name', 'Unknown'))
            
            duration_ms = track.get('duration_ms', 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
            
            info = f"[bold #a6e3a1]{Icons.TRACK} {strip_icons(track.get('name', 'Unknown Track'))}[/]\n\n"
            info += f"[#cdd6f4]{Icons.ARTIST} Artist:[/] {artists}\n"
            info += f"[#cdd6f4]{Icons.ALBUM} Album:[/] {album_name}\n"
            info += f"[#cdd6f4]{Icons.DURATION} Duration:[/] {duration_str}\n"
            
            self.preview_info.update(info)

        elif item["type"] == "album":
            album = item.get("data")
            if not album: return

            artists = ", ".join([strip_icons(a['name']) for a in album.get('artists', []) if a and a.get('name')])
            total_tracks = album.get('total_tracks', 0)
            release_date = album.get('release_date', 'Unknown')
            
            info = f"[bold #f9e2af]{Icons.ALBUM} {strip_icons(album.get('name', 'Unknown Album'))}[/]\n\n"
            info += f"[#a6e3a1]{Icons.ARTIST} Artist:[/] {artists}\n"
            info += f"[#cba6f7]📅 Release:[/] {release_date}\n"
            info += f"[#89b4fa]{Icons.TRACK} Tracks:[/] {total_tracks}\n"
            
            self.preview_info.update(info)
            self.preview_tracks.display = True
            self.preview_tracks.clear_options()
            self.preview_tracks.add_option("Loading tracks...")
            album_id = album.get('id')
            if album_id:
                self.fetch_timer = self.set_timer(0.4, lambda: self.fetch_album_tracks(album_id))

        elif item["type"] == "playlist":
            playlist = item.get("data")
            if not playlist: return

            owner = strip_icons(playlist.get('owner', {}).get('display_name', 'Unknown'))
            total_tracks = playlist.get('tracks', {}).get('total', 0)
            desc = strip_icons(playlist.get('description', ''))
            
            info = f"[bold #89b4fa]{Icons.PLAYLIST} {strip_icons(playlist.get('name', 'Unknown Playlist'))}[/]\n\n"
            info += f"[#a6e3a1]{Icons.ARTIST} Owner:[/] {owner}\n"
            info += f"[#cba6f7]{Icons.TRACK} Tracks:[/] {total_tracks}\n"
            if desc:
                info += f"\n[dim italic]{escape(desc)}[/]\n"
            
            self.preview_info.update(info)
            self.preview_tracks.display = True
            self.preview_tracks.clear_options()
            self.preview_tracks.add_option("Loading tracks...")
            playlist_id = playlist.get('id')
            if playlist_id:
                self.fetch_timer = self.set_timer(0.4, lambda: self.fetch_playlist_tracks(playlist_id))

    @work(exclusive=True, thread=True)
    def fetch_album_tracks(self, album_id: str):
        try:
            tracks = self.network.get_album_tracks(album_id)
            self.app.call_from_thread(self._render_preview_tracks, tracks, is_album=True)
        except Exception:
            pass

    @work(exclusive=True, thread=True)
    def fetch_playlist_tracks(self, playlist_id: str):
        try:
            items = self.network.get_playlist_tracks(playlist_id)
            # playlist items are nested
            tracks = [item['track'] for item in items if item.get('track')]
            self.app.call_from_thread(self._render_preview_tracks, tracks, is_album=False)
        except Exception:
            pass

    def _render_preview_tracks(self, tracks, is_album=False):
        self.preview_tracks.clear_options()
        if not tracks:
            self.preview_tracks.add_option("No tracks found.")
            return

        for t in tracks:
            if not t: # Skip if track data is None
                continue
            name = strip_icons(t.get('name', 'Unknown Track'))
            artists = ", ".join([a['name'] for a in t.get('artists', []) if a and a.get('name')])
            self.preview_tracks.add_option(f"{Icons.TRACK} {name} - {strip_icons(artists)}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option_list.id == "telescope-preview-tracks":
            # Just previewing, we don't handle play from preview yet to keep it simple, or we could.
            return
            
        self._handle_selection(event.option_index)

    def _handle_selection(self, index: int):
        if not self.results_data or index is None or index >= len(self.results_data):
            return
            
        item = self.results_data[index]
        
        def generic_action_handler(action: str, uri: str):
            if action:
                from src.hooks.track_actions import play_track, start_track_radio, save_track, remove_saved_track
                if action == "play":
                    if play_track(uri, self.app):
                        self.app.update_now_playing()
                elif action == "radio":
                    start_track_radio(uri, self.app)
                elif action == "save":
                    save_track(uri, self.app)
                elif action == "remove":
                    remove_saved_track(uri, self.app)

        uri = item.get("uri")
        if not uri: return

        if item["type"] == "track":
            track_data = item["data"]
            artists = ", ".join([a['name'] for a in track_data.get('artists', [])])
            display_name = f"{strip_icons(track_data['name'])} by {strip_icons(artists)}"
            self.app.push_screen(TrackMenuPopup(uri, display_name), lambda act: generic_action_handler(act, uri))
            
        elif item["type"] == "album":
            album_data = item["data"]
            self.app.push_screen(TrackMenuPopup(uri, strip_icons(album_data['name'])), lambda act: generic_action_handler(act, uri))

        elif item["type"] == "playlist":
            playlist_data = item["data"]
            self.app.push_screen(TrackMenuPopup(uri, strip_icons(playlist_data['name'])), lambda act: generic_action_handler(act, uri))

    def on_unmount(self):
        try:
            from src.ui.components.status_bar import StatusBar
            self.app.query_one(StatusBar).mode = "NORMAL"
        except Exception:
            pass

    def on_key(self, event: events.Key):
        # If input is focused, typing normal chars should work.
        if self.input.has_focus:
            if event.key == "down":
                self.results_list.focus()
                event.prevent_default()
            return

        # Not in input - OptionList or preview is focused
        focused_widget = self.focused
        if focused_widget is None:
            return

        # VIM Navigation (Only use character checks for j/k/h/l to avoid double arrow handling)
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
            if focused_widget.id == "telescope-preview-tracks":
                self.results_list.focus()
            else:
                self.input.focus()
            event.prevent_default()
        elif event.character == "l":
            if focused_widget.id == "telescope-results" and self.preview_tracks.display:
                self.preview_tracks.focus()
            event.prevent_default()
        
        # Pagination (U/D)
        elif event.character == "U":
            if hasattr(focused_widget, "action_page_up"):
                focused_widget.action_page_up()
            event.prevent_default()
        elif event.character == "D":
            if hasattr(focused_widget, "action_page_down"):
                focused_widget.action_page_down()
            event.prevent_default()
        
        # We REMOVED manual enter, up, down, left, right handling here 
        # to allow the focused widget (OptionList) to handle them natively without double-moving.
