from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual import events, work

from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.config.user_prefs import UserPreferences
from src.core.command_service import CommandService
from spotipy.oauth2 import SpotifyOauthError

from src.hooks.useEnsureActiveDevice import useEnsureActiveDevice
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer
from src.hooks.useRefreshData import useRefreshData
from src.hooks.useUpdateNowPlaying import useUpdateNowPlaying
from src.hooks.useAutoPlay import useAutoPlay
from src.hooks.useDaemonService import useDaemonService

from src.ui.components.now_playing import NowPlaying
from src.ui.components.sidebar import SidebarPanels
from src.ui.components.track_table import TrackList
from src.ui.components.status_bar import StatusBar
from src.ui.modals.which_key import WhichKeyPopup
from src.ui.themes import THEMES

class TerminalRenderer(App):
    CSS_PATH = [
        "../../styles/_base.tcss",
        "../../styles/_status_bar.tcss",
        "../../styles/_now_playing.tcss",
        "../../styles/_main_view.tcss",
        "../../styles/_modals.tcss",
        "../../styles/_telescope.tcss",
        "../../styles/_onboarding.tcss",
    ]

    BINDINGS = [
        Binding("tab", "focus_next", "Focus Next"),
        Binding("ctrl+l", "show_logs", "Show Logs"),
    ]

    def __init__(self):
        super().__init__()
        self._log_buffer = [] # Store logs for the LogModal
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
        self.local_player = Container.resolve(LocalPlayer)
        self.user_prefs = Container.resolve(UserPreferences)
        self.command_service = Container.resolve(CommandService)
        
        self.leader_mode = False
        self.leader_timer = None

        # Register all available themes
        for theme in THEMES.values():
            self.register_theme(theme)

    def action_show_logs(self):
        from src.ui.modals.log_modal import LogModal
        self.push_screen(LogModal())

    def app_log(self, message: str):
        self._log_buffer.append(message)
        # Also let Textual's internal logger handle it
        self.log(message)

    def notify(self, message: str, *, title: str = "", severity: str = "information", timeout: float = 3.0, **kwargs):
        # Fallback to default toast
        super().notify(message, title=title, severity=severity, timeout=timeout)

    def apply_theme(self, theme_name: str):
        if theme_name in THEMES:
            self.theme = theme_name

    def on_mount(self) -> None:
        self.title = "Spotify TUI"
        
        # Apply theme from user preferences
        self.apply_theme(self.user_prefs.theme)
        
        self.run_startup_sequence()

    @work(exclusive=True)
    async def run_startup_sequence(self):
        await useEnsureActiveDevice(self, silent=False)
        self.refresh_data()
        
        recent = self.store.get("recently_played")
        if recent:
            self.store.set("current_tracks", recent)
        
        await useSwitchToLocalPlayer(self)
        self.set_timer(1.0, lambda: useAutoPlay(self))
        
        self.update_now_playing()
        self.set_interval(5.0, self.update_now_playing)
        self.set_interval(60.0, self.check_authentication)

        # Launch background self-healing daemon service
        await useDaemonService(self)

    def check_authentication(self):
        if not self.network.is_authenticated():
            self.notify("Authentication expired. Attempting to re-authenticate...", severity="warning")
            try:
                self.network.reauthenticate()
                self.notify("Re-authentication successful.", severity="information")
                self.refresh_data()
                self.update_now_playing()
            except Exception as e:
                self.notify(f"Re-authentication failed: {e}. Please restart the application.", severity="error")

    def refresh_data(self):
        useRefreshData(self)

    def on_unmount(self) -> None:
        if self.local_player:
            self.local_player.stop()

    def safe_network_call(self, func, *args, **kwargs):
        if not self.network:
            return None
        try:
            return func(*args, **kwargs)
        except SpotifyOauthError as e:
            self.notify(f"Authentication error: {e}. Attempting re-authentication.", severity="error")
            self.check_authentication()
            return None
        except Exception as e:
            # Handle "No Active Device" by attempting a silent re-activation
            if "No active device" in str(e):
                self.run_background_recovery()
                # Try the call one more time after a short delay
                try:
                    import time
                    time.sleep(1) 
                    return func(*args, **kwargs)
                except Exception:
                    pass
            
            self.notify(f"Spotify API Error: {e}", severity="error")
            return None

    @work(exclusive=True)
    async def run_background_recovery(self):
        await useEnsureActiveDevice(self, silent=True)

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")
        with Horizontal(id="main-container"):
            yield SidebarPanels("Library", id="sidebar")
            yield TrackList(id="track-list")
        yield StatusBar(id="status-bar")

    def update_now_playing(self):
        useUpdateNowPlaying(self) 

    def on_key(self, event: events.Key):
        leader_key = self.user_prefs.leader
        char = event.character
        if event.key == "space": char = "space"
            
        # Ignore raw focus navigation if we are inside a text input
        in_input = self.focused and self.focused.__class__.__name__ == "Input"
        
        nav = self.user_prefs.nav_bindings
        
        # If a modal is active, we don't want to trigger global navigation.
        is_modal_active = len(self.screen_stack) > 1

        if char == nav["left"] and not self.leader_mode and not in_input and not is_modal_active:
            self.action_focus_previous()
            event.prevent_default()
            return
            
        if char == nav["right"] and not self.leader_mode and not in_input and not is_modal_active:
            self.action_focus_next()
            event.prevent_default()
            return
            
        if char == nav["down"] and not self.leader_mode and not in_input and not is_modal_active:
            if hasattr(self.focused, "action_cursor_down"):
                self.focused.action_cursor_down()
            event.prevent_default()
            return
            
        if char == nav["up"] and not self.leader_mode and not in_input and not is_modal_active:
            if hasattr(self.focused, "action_cursor_up"):
                self.focused.action_cursor_up()
            event.prevent_default()
            return
            
        if char == nav.get("page_down") and not self.leader_mode and not in_input and not is_modal_active:
            if hasattr(self.focused, "action_page_down"):
                self.focused.action_page_down()
            event.prevent_default()
            return
            
        if char == nav.get("page_up") and not self.leader_mode and not in_input and not is_modal_active:
            if hasattr(self.focused, "action_page_up"):
                self.focused.action_page_up()
            event.prevent_default()
            return
            
        if self.leader_mode:
            # We are waiting for a leader command
            if event.key == "escape":
                self.cancel_leader()
            elif event.key == "left" and self.is_screen_active("WhichKeyPopup"):
                self.screen.action_previous_page()
            elif event.key == "right" and self.is_screen_active("WhichKeyPopup"):
                self.screen.action_next_page()
            elif char:
                # Get the action for this key
                kb = self.user_prefs.keybindings
                action = kb.get(char, {}).get("action")
                
                # If action is search_prompt, update mode to SEARCH
                if action == "search_prompt":
                    try:
                        self.query_one(StatusBar).mode = "SEARCH"
                    except Exception: pass
                    
                self.handle_leader_command(char)
            else:
                self.cancel_leader() # Cancel on any other unhandled non-character key (like F1)
            event.prevent_default()
            return
            
        if char == leader_key and not in_input:
            self.leader_mode = True
            try:
                self.query_one(StatusBar).mode = "LEADER"
            except Exception: pass
            
            # Optionally show WhichKeyPopup depending on user preferences
            if self.user_prefs.show_which_key:
                self.push_screen(WhichKeyPopup())
                
            event.prevent_default()

    def cancel_leader(self):
        self.leader_mode = False
        try:
            # Revert to SEARCH if search is still active, else NORMAL
            mode = "SEARCH" if self.is_screen_active("TelescopePrompt") else "NORMAL"
            self.query_one(StatusBar).mode = mode
        except Exception: pass
        
        if self.is_screen_active("WhichKeyPopup"):
            self.pop_screen()

    def is_screen_active(self, screen_name):
        return any(type(s).__name__ == screen_name for s in self.screen_stack)

    def handle_leader_command(self, key: str):
        self.cancel_leader()
        if key == " ": key = "space"
            
        kb = self.user_prefs.keybindings
        if key not in kb: return
            
        action = kb[key]["action"]
        self.command_service.execute(action, self)
