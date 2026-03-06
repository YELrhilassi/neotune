from textual.app import ComposeResult
from textual.widgets import OptionList, Input, Static
from textual.containers import Horizontal, Vertical
from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork
from src.ui.modals.track_menu import TrackMenuPopup
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings
from src.config.user_prefs import UserPreferences
from src.core.command_service import CommandService
from textual import work

class TelescopePrompt(BaseModal[str]):
    def on_mount(self):
        self.network = Container.resolve(SpotifyNetwork)
        self.user_prefs = Container.resolve(UserPreferences)
        self.command_service = Container.resolve(CommandService)
        self.query_one("#telescope-input").focus()
        self.search_timer = None
        self.results_data = []

    def compose(self) -> ComposeResult:
        with Vertical(id="telescope-container"):
            yield Input(placeholder="Search Spotify or type ':' for commands...", id="telescope-input")
            with Horizontal(id="telescope-body"):
                yield OptionList(id="telescope-results")
                yield Static(Strings.SELECT_TRACK, id="telescope-info")

    def on_input_changed(self, event: Input.Changed):
        query = event.value
        if self.search_timer:
            self.search_timer.stop()
            
        if query:
            commands = self.user_prefs.commands
            matched_cmds = [cmd for cmd in commands if cmd.startswith(query.lstrip(":"))]
            
            # If explicit command syntax, or matched command without explicit if user wants
            if query.startswith(":") or (matched_cmds and not query.startswith(" ")):
                self.show_commands(query)
            else:
                self.search_timer = self.set_timer(0.3, lambda: self.trigger_search(query))
        else:
            self.query_one("#telescope-results", OptionList).clear_options()
            self.results_data = []
            self.query_one("#telescope-info", Static).update(Strings.SELECT_TRACK)

    def show_commands(self, query):
        clean_query = query.lstrip(":")
        commands = self.user_prefs.commands
        
        list_widget = self.query_one("#telescope-results", OptionList)
        list_widget.clear_options()
        self.results_data = []
        
        if clean_query:
            matched = [k for k in commands if k.startswith(clean_query)]
        else:
            matched = list(commands.keys())
            
        for m in matched:
            cmd = commands[m]
            self.results_data.append({"type": "command", "action": cmd["action"], "alias": m, "desc": cmd["desc"]})
            list_widget.add_option(f"> {m} - {cmd['desc']}")
            
        self.query_one("#telescope-info", Static).update("[bold #f38ba8]Command Mode[/]\n\nSelect a command to execute.")

    def trigger_search(self, query):
        self.perform_search(query)

    @work(exclusive=True, thread=True)
    def perform_search(self, query: str):
        try:
            results = self.network.search(query, "track")
            self.app.call_from_thread(self._update_results, results)
        except Exception as e:
            self.app.call_from_thread(self.app.notify, f"Search failed: {e}", severity="error")

    def _update_results(self, results):
        self.results_data = []
        list_widget = self.query_one("#telescope-results", OptionList)
        list_widget.clear_options()
        
        if not results:
            list_widget.add_option(Strings.NO_RESULTS)
            self.query_one("#telescope-info", Static).update(Strings.NO_RESULTS)
            return
            
        for track in results:
            artists = ", ".join([a['name'] for a in track['artists']])
            clean_name = strip_icons(track['name'])
            self.results_data.append({"type": "track", "data": track})
            list_widget.add_option(f"{Icons.TRACK} {clean_name} - {strip_icons(artists)}")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted):
        if not self.results_data or event.option_index is None or event.option_index >= len(self.results_data):
            return
            
        item = self.results_data[event.option_index]
        if item["type"] == "track":
            track = item["data"]
            artists = ", ".join([strip_icons(a['name']) for a in track.get('artists', [])])
            album = strip_icons(track.get('album', {}).get('name', 'Unknown'))
            
            duration_ms = track.get('duration_ms', 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
            
            info = f"[bold #a6e3a1]{Icons.TRACK} {strip_icons(track['name'])}[/]\n\n"
            info += f"[#cdd6f4]{Icons.ARTIST} Artist:[/] {artists}\n"
            info += f"[#cdd6f4]{Icons.ALBUM} Album:[/] {album}\n"
            info += f"[#cdd6f4]{Icons.DURATION} Duration:[/] {duration_str}\n"
            
            self.query_one("#telescope-info", Static).update(info)
        elif item["type"] == "command":
            info = f"[bold #f38ba8]Command:[/] {item['alias']}\n\n"
            info += f"[#cdd6f4]Action:[/] {item['action']}\n"
            info += f"[#cdd6f4]Description:[/] {item['desc']}\n"
            self.query_one("#telescope-info", Static).update(info)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if not self.results_data: return
        item = self.results_data[event.option_index]
        
        if item["type"] == "command":
            self.dismiss()
            self.command_service.execute(item["action"], self.app)
        elif item["type"] == "track":
            track_data = item["data"]
            artists = ", ".join([a['name'] for a in track_data.get('artists', [])])
            display_name = f"{strip_icons(track_data['name'])} by {strip_icons(artists)}"
            
            def on_action_selected(action: str):
                if action:
                    from src.hooks.track_actions import play_track, start_track_radio, save_track, remove_saved_track
                    if action == "play":
                        if play_track(track_data['uri'], self.app):
                            self.app.update_now_playing()
                    elif action == "radio":
                        start_track_radio(track_data['uri'], self.app)
                    elif action == "save":
                        save_track(track_data['uri'], self.app)
                    elif action == "remove":
                        remove_saved_track(track_data['uri'], self.app)
                    
            self.app.push_screen(TrackMenuPopup(track_data['uri'], display_name), on_action_selected)
