from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual import events

from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.config.user_prefs import UserPreferences
from src.core.command_service import CommandService
from spotipy.oauth2 import SpotifyOauthError # Import SpotifyOauthError

from src.ui.components.now_playing import NowPlaying
from src.ui.components.sidebar import SidebarPanels
from src.ui.components.track_table import TrackList
from src.ui.components.status_bar import StatusBar
from src.ui.modals.which_key import WhichKeyPopup
from src.ui.components.notification import CustomNotification

class TerminalRenderer(App):
    CSS_PATH = "../../styles/main.tcss"

    BINDINGS = [
        Binding("tab", "focus_next", "Focus Next"),
    ]

    def __init__(self):
        super().__init__()
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
        self.local_player = Container.resolve(LocalPlayer)
        self.user_prefs = Container.resolve(UserPreferences)
        self.command_service = Container.resolve(CommandService)
        
        self.leader_mode = False
        self.leader_timer = None

    def notify(self, message: str, severity: str = "information", timeout: float = 3.0):
        # We are replacing the default notify with our custom widget
        notification = CustomNotification(message, severity=severity)
        self.mount(notification)
        notification.styles.display = "block"
        notification.add_class("show")
        
    def on_mount(self) -> None:
        self.title = "Spotify TUI"
        
        # Proactively check for an active device on startup
        self.set_timer(0.1, self.ensure_active_device)
        
        self.refresh_data()
        
        # Auto-load the recently played tracks as the default view
        recent = self.store.get("recently_played")
        if recent:
            self.store.set("current_tracks", recent)
        
        # Resume previous device / Auto switch
        self.set_timer(1.0, self.switch_to_local_player)
        
        self.update_now_playing()
        self.set_interval(5.0, self.update_now_playing)
        self.set_interval(60.0, self.check_authentication) # Proactive auth check

    def ensure_active_device(self):
        try:
            playback = self.network.get_current_playback()
            if not playback or not playback.get('device'):
                self.notify("No active device found. Activating TUI player...", severity="information")
                self.switch_to_local_player(force=True)
        except Exception:
            # This can fail if auth is expired, which `check_authentication` will handle.
            pass

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
        try:
            self.store.set("playlists", self.network.get_playlists())
            self.store.set("featured_playlists", self.network.get_featured_playlists())
            self.store.set("recently_played", self.network.get_recently_played())
        except SpotifyOauthError as e:
            self.notify(f"Authentication error during data refresh: {e}. Attempting re-authentication.", severity="error")
            self.check_authentication()
        except Exception as e:
            self.notify(f"Spotify API Error: {e}", severity="error")

    def switch_to_local_player(self, force=False):
        try:
            devices_data = self.network.get_devices()
            if not devices_data or not devices_data.get('devices'):
                return
            
            # If not forcing, only switch if there's no active device.
            is_active = any(d.get('is_active') for d in devices_data['devices'])
            if not force and is_active:
                return
                
            for device in devices_data['devices']:
                if device['name'] == "Spotify TUI Player":
                    self.store.set("preferred_device_id", device['id'])
                    self.store.set("preferred_device_name", device['name'])
                    self.network.transfer_playback(device['id'], force_play=False)
                    self.notify(f"Auto-switched to local output: {device['name']}")
                    return # Found our preferred device

            # If TUI player not found, activate the first available one
            if force and devices_data['devices']:
                first_device = devices_data['devices'][0]
                self.store.set("preferred_device_id", first_device['id'])
                self.store.set("preferred_device_name", first_device['name'])
                self.network.transfer_playback(first_device['id'], force_play=False)
                self.notify(f"Activated first available device: {first_device['name']}")

        except Exception:
            pass

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
            self.notify(f"Spotify API Error: {e}", severity="error")
            return None

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")
        with Horizontal(id="main-container"):
            yield SidebarPanels("Library", id="sidebar")
            yield TrackList(id="track-list")
        yield StatusBar(id="status-bar")

    def update_now_playing(self):
        try:
            playback = self.network.get_current_playback()
            self.store.set("current_playback", playback)
        except SpotifyOauthError as e:
            self.notify(f"Authentication error during playback update: {e}. Attempting re-authentication.", severity="error")
            self.check_authentication()
        except Exception:
            pass 

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
                self.handle_leader_command(char)
            else:
                self.cancel_leader() # Cancel on any other unhandled non-character key (like F1)
            event.prevent_default()
            return
            
        if char == leader_key and not in_input:
            self.leader_mode = True
            
            # Optionally show WhichKeyPopup depending on user preferences
            if self.user_prefs.show_which_key:
                self.push_screen(WhichKeyPopup())
                
            event.prevent_default()

    def cancel_leader(self):
        self.leader_mode = False
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
