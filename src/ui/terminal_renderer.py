import time
import threading
from typing import Dict, Any, List, Optional, cast, Literal, Set, TYPE_CHECKING
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual import events, work, on

from src.core.di import Container
from src.state.store import Store
from src.state.pubsub import PubSub
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.config.user_prefs import UserPreferences
from src.core.command_service import CommandService
from src.core.debug_logger import DebugLogger, LogLevel
from spotipy.oauth2 import SpotifyOauthError

from src.hooks.useEnsureActiveDevice import useEnsureActiveDevice
from src.hooks.useSwitchToLocalPlayer import useSwitchToLocalPlayer
from src.hooks.useRefreshData import useRefreshData
from src.hooks.useUpdateNowPlaying import useUpdateNowPlaying
from src.hooks.useAutoPlay import useAutoPlay

from src.ui.components.now_playing import NowPlaying
from src.ui.components.sidebar import SidebarPanels
from src.ui.components.track_table import TrackList
from src.ui.components.status_bar import StatusBar
from src.ui.modals.which_key import WhichKeyPopup
from src.ui.themes import THEMES

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.widget import Widget

SeverityLevel = Literal["information", "warning", "error"]


class TerminalRenderer(App):
    CSS_PATH = [
        "../../styles/main.tcss",
        "../../styles/_base.tcss",
        "../../styles/_status_bar.tcss",
        "../../styles/_now_playing.tcss",
        "../../styles/_main_view.tcss",
        "../../styles/_modals.tcss",
        "../../styles/_telescope.tcss",
        "../../styles/_fuzzy.tcss",
        "../../styles/_onboarding.tcss",
    ]

    BINDINGS = [
        Binding("tab", "focus_next", "Focus Next"),
        Binding("ctrl+l", "show_logs", "Show Logs"),
        Binding("ctrl+q", "quit", "Quit App"),
        Binding("ctrl+c", "quit", "Quit App"),
    ]

    def __init__(self):
        super().__init__()
        self.user_prefs = Container.resolve(UserPreferences)
        self.store = Store()  # Singleton
        self.network = Container.resolve(SpotifyNetwork)
        self.local_player = Container.resolve(LocalPlayer)
        self.command_service = Container.resolve(CommandService)

        self.leader_mode = False
        self._is_running = True
        self.debug_logger = DebugLogger()
        self.leader_timer = None

        for theme in THEMES.values():
            self.register_theme(theme)

    def on_mount(self) -> None:
        self.title = "NeoTune"
        self.apply_theme(self.user_prefs.theme)

        # Sync persistent bindings and Lua config
        self.store.set("nav_bindings", dict(self.user_prefs.nav_bindings))
        self.store.set("special_playlists", list(self.user_prefs.special_playlists))

        self.run_startup_sequence()
        self.run_heartbeat_loop()

    @work(exclusive=True, thread=True)
    def run_startup_sequence(self) -> None:
        useEnsureActiveDevice(self, silent=True)
        self.refresh_data()
        recent = self.store.get("recently_played")
        if recent:
            self.call_from_thread(self.store.set, "current_tracks", recent)
        useSwitchToLocalPlayer(self)
        self.call_from_thread(self.set_timer, 2.0, lambda: useAutoPlay(self))
        self.call_from_thread(self.update_now_playing)

    @work(name="heartbeat", exclusive=True, thread=True)
    def run_heartbeat_loop(self) -> None:
        while self._is_running:
            now = time.time()
            try:
                # Player Health Check
                if self.local_player and not self.local_player.is_running():
                    if self.network and self.network.is_authenticated():
                        token = self.network.get_access_token()
                        self.local_player.start(
                            audio_config=self.user_prefs.audio_config, access_token=token
                        )

                playback = self.store.get("current_playback")
                is_playing = bool(playback and playback.get("is_playing"))

                if is_playing and playback:
                    progress_ms = playback.get("progress_ms", 0)
                    duration_ms = playback.get("item", {}).get("duration_ms", 0)
                    remaining_ms = duration_ms - progress_ms
                    interval = 2.0 if remaining_ms < 10000 else 10.0
                else:
                    interval = 15.0

                if (
                    not hasattr(self, "_last_playback_poll")
                    or now - self._last_playback_poll >= interval
                ):
                    useUpdateNowPlaying(self)
                    self._last_playback_poll = now

                if not hasattr(self, "_last_auth_check") or now - self._last_auth_check > 600:
                    self.call_from_thread(self.check_authentication)
                    self._last_auth_check = now

                if not hasattr(self, "_last_device_sync") or now - self._last_device_sync > 60:
                    try:
                        network = Container.resolve(SpotifyNetwork)
                        devices_data = network.get_devices()
                        self.store.set("devices", devices_data.get("devices", []))
                        self._last_device_sync = now
                    except:
                        pass

                time.sleep(1.0)
            except Exception:
                time.sleep(5.0)

    def check_authentication(self) -> None:
        if not self.network.is_authenticated():
            self.notify("Authentication expired. Re-authenticating...", severity="warning")
            try:
                self.network.reauthenticate()
                self.refresh_data()
                self.update_now_playing()
            except Exception as e:
                self.notify(f"Re-authentication failed: {e}", severity="error")

    def refresh_data(self) -> None:
        useRefreshData(self)

    async def action_quit(self) -> None:
        self._is_running = False
        if self.local_player:
            try:
                self.local_player.stop()
            except:
                pass
        self.exit()

    def is_screen_active(self, screen_name: str) -> bool:
        return any(type(s).__name__ == screen_name for s in self.screen_stack)

    def safe_push_screen(self, screen, callback=None):
        """Enforce single-instance of same modal type."""
        screen_type = type(screen).__name__
        for s in self.screen_stack:
            if type(s).__name__ == screen_type:
                return None
        return self.push_screen(screen, callback)

    def safe_network_call(self, func, *args, **kwargs) -> Any:
        if not self.network:
            return None
        try:
            return func(*args, **kwargs)
        except SpotifyOauthError:
            self.check_authentication()
            return None
        except Exception as e:
            self.notify(f"Spotify API Error: {e}", severity="error")
            return None

    def compose(self) -> ComposeResult:
        yield NowPlaying(id="now-playing")
        with Horizontal(id="main-container"):
            yield SidebarPanels(id="sidebar")
            yield TrackList(id="track-list")
        yield StatusBar(id="status-bar")

    @work(exclusive=True, thread=True)
    def update_now_playing(self, force: bool = False) -> None:
        useUpdateNowPlaying(self, force=force)

    def cancel_leader(self) -> None:
        self.leader_mode = False
        try:
            mode = "SEARCH" if self.is_screen_active("TelescopePrompt") else "NORMAL"
            self.store.set("mode", mode)
        except:
            pass
        if self.is_screen_active("WhichKeyPopup"):
            self.pop_screen()

    def handle_leader_command(self, key_char: str) -> None:
        self.cancel_leader()
        lookup = "space" if key_char == " " else key_char
        kb = self.user_prefs.keybindings
        if lookup in kb:
            action = kb[lookup]["action"]
            self.command_service.execute(action, self)

    def on_key(self, event: events.Key) -> None:
        leader_key = self.user_prefs.leader
        key = event.key
        char = event.character or ""
        is_leader = (char == leader_key) or (key == leader_key)
        if leader_key == "space" and key == "space":
            is_leader = True
        in_input = self.focused and self.focused.__class__.__name__ == "Input"
        is_modal_active = len(self.screen_stack) > 1

        if self.leader_mode:
            if key == "escape":
                self.cancel_leader()
            elif char:
                self.handle_leader_command(char)
            else:
                self.cancel_leader()
            event.prevent_default()
            event.stop()
            return

        if is_leader and not in_input:
            self.leader_mode = True
            try:
                self.store.set("mode", "LEADER")
            except:
                pass
            if self.user_prefs.show_which_key:
                self.safe_push_screen(WhichKeyPopup())
            event.prevent_default()
            event.stop()
            return

        if not in_input and not is_modal_active:
            nav = self.user_prefs.nav_bindings
            if char == nav.get("left"):
                try:
                    self.query_one("#content-tree").focus()
                except:
                    pass
                event.stop()
                return
            elif char == nav.get("right"):
                try:
                    self.query_one("TrackList").focus()
                except:
                    pass
                event.stop()
                return
            f = self.focused
            if f:
                method_map = {
                    nav.get("up"): "action_cursor_up",
                    nav.get("down"): "action_cursor_down",
                    nav.get("page_up"): "action_page_up",
                    nav.get("page_down"): "action_page_down",
                }
                action_name = method_map.get(char)
                if action_name and hasattr(f, action_name):
                    getattr(f, action_name)()
                    event.stop()
                    return

        if key == "space" and not is_leader and not in_input:
            self.action_play_pause()
            event.stop()
            return

    def apply_theme(self, theme_name: str) -> None:
        if hasattr(self.user_prefs, "theme_vars") and self.user_prefs.theme_vars:
            from textual.theme import Theme

            v = self.user_prefs.theme_vars
            fb = THEMES.get(theme_name, THEMES["catppuccin"])
            self.register_theme(
                Theme(
                    name="custom",
                    primary=v.get("primary") or fb.primary,
                    accent=v.get("accent") or fb.accent,
                    background=v.get("background") or fb.background,
                    surface=v.get("surface") or fb.surface,
                    panel=v.get("panel") or fb.panel,
                    success=v.get("success") or fb.success,
                    warning=v.get("warning") or fb.warning,
                    error=v.get("error") or fb.error,
                )
            )
            self.theme = "custom"
        elif theme_name in THEMES:
            self.theme = theme_name

    def on_unmount(self) -> None:
        self._is_running = False
        self._exit = True

    def action_play_pause(self) -> None:
        self.command_service.execute("play_pause", self)

    def action_show_logs(self) -> None:
        from src.ui.modals.log_modal import LogModal

        self.safe_push_screen(LogModal())

    def copy_to_clipboard(self, text: str) -> None:
        from src.core.utils import copy_to_clipboard

        if copy_to_clipboard(text):
            self.notify("Copied to clipboard")
        else:
            self.notify("Failed to copy to clipboard", severity="error")
