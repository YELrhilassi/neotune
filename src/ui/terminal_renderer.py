from typing import Dict, Any, List, Optional, cast, Literal, Set, TYPE_CHECKING
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual import events, work, on

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

from src.ui.components.now_playing import NowPlaying
from src.ui.components.sidebar import SidebarPanels
from src.ui.components.track_table import TrackList
from src.ui.components.status_bar import StatusBar
from src.ui.modals.which_key import WhichKeyPopup
from src.ui.themes import THEMES

if TYPE_CHECKING:
    from textual.screen import Screen
    from textual.widget import Widget

# Define SeverityLevel type alias
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
        "../../styles/_onboarding.tcss",
    ]

    # ONLY core system bindings. NO Space binding here.
    BINDINGS = [
        Binding("tab", "focus_next", "Focus Next"),
        Binding("ctrl+l", "show_logs", "Show Logs"),
        Binding("ctrl+q", "quit", "Quit App"),
        Binding("ctrl+c", "quit", "Quit App"),
    ]

    def __init__(self):
        super().__init__()
        self._log_buffer: List[str] = []
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
        self.local_player = Container.resolve(LocalPlayer)
        self.user_prefs = Container.resolve(UserPreferences)
        self.command_service = Container.resolve(CommandService)

        self.leader_mode = False
        self.leader_timer = None

        for theme in THEMES.values():
            self.register_theme(theme)

    def action_show_logs(self) -> None:
        from src.ui.modals.log_modal import LogModal

        self.push_screen(LogModal())

    def action_play_pause(self) -> None:
        """Executed via leader key mapping or global Space handler."""
        self.command_service.execute("play_pause", self)

    def app_log(self, message: str) -> None:
        self._log_buffer.append(message)
        self.log(message)

    def notify(
        self,
        message: str,
        *,
        title: str = "",
        severity: SeverityLevel = "information",
        timeout: Optional[float] = 3.0,
        **kwargs,
    ) -> None:
        super().notify(message, title=title, severity=severity, timeout=timeout)

    def apply_theme(self, theme_name: str) -> None:
        if hasattr(self.user_prefs, "theme_vars") and self.user_prefs.theme_vars:
            from textual.theme import Theme

            v = self.user_prefs.theme_vars
            fallback = THEMES.get(theme_name, THEMES["catppuccin"])
            custom_theme = Theme(
                name="custom",
                primary=v.get("primary") or fallback.primary,
                accent=v.get("accent") or fallback.accent,
                background=v.get("background") or fallback.background,
                surface=v.get("surface") or fallback.surface,
                panel=v.get("panel") or fallback.panel,
                success=v.get("success") or fallback.success,
                warning=v.get("warning") or fallback.warning,
                error=v.get("error") or fallback.error,
            )
            self.register_theme(custom_theme)
            self.theme = "custom"
        elif theme_name in THEMES:
            self.theme = theme_name

    def on_mount(self) -> None:
        self.title = "Spotify TUI"
        self.apply_theme(self.user_prefs.theme)

        # Ensure 'space' is NOT bound to anything globally by default
        try:
            self._bindings.unbind("space")
        except:
            pass

        self.store.set("nav_bindings", dict(self.user_prefs.nav_bindings))
        self.run_startup_sequence()

    @work(exclusive=True, thread=True)
    def run_startup_sequence(self) -> None:
        useEnsureActiveDevice(self, silent=False)
        self.call_from_thread(self.refresh_data)

        recent = self.store.get("recently_played")
        if recent:
            self.call_from_thread(self.store.set, "current_tracks", recent)

        useSwitchToLocalPlayer(self)
        self.call_from_thread(self.set_timer, 1.0, lambda: useAutoPlay(self))
        self.call_from_thread(self.update_now_playing)
        self.call_from_thread(self.set_interval, 5.0, self.update_now_playing)
        self.call_from_thread(self.set_interval, 60.0, self.check_authentication)

    def check_authentication(self) -> None:
        if not self.network.is_authenticated():
            self.notify(
                "Authentication expired. Re-authenticating...", severity="warning"
            )
            try:
                self.network.reauthenticate()
                self.notify("Re-authentication successful.", severity="information")
                self.refresh_data()
                self.update_now_playing()
            except Exception as e:
                self.notify(f"Re-authentication failed: {e}", severity="error")

    def log_fd_count(self, context: str = "") -> None:
        try:
            import psutil, os

            process = psutil.Process(os.getpid())
            fds = process.num_fds()
            self.app_log(f"[FD Monitor] {context} - FDs: {fds}")
        except Exception:
            pass

    def refresh_data(self) -> None:
        useRefreshData(self)

    async def action_quit(self) -> None:
        self.log_fd_count("action_quit")
        if self.local_player:
            try:
                self.local_player.stop()
            except Exception:
                pass
        self.exit()

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

    @work(thread=True)
    def update_now_playing(self) -> None:
        useUpdateNowPlaying(self)

    def cancel_leader(self) -> None:
        self.leader_mode = False
        try:
            mode = "SEARCH" if self.is_screen_active("TelescopePrompt") else "NORMAL"
            self.query_one(StatusBar).mode = mode
        except Exception:
            pass
        if self.is_screen_active("WhichKeyPopup"):
            self.pop_screen()

    def is_screen_active(self, screen_name: str) -> bool:
        return any(type(s).__name__ == screen_name for s in self.screen_stack)

    def handle_leader_command(self, key_char: str) -> None:
        self.cancel_leader()
        # Map back special key names
        lookup = "space" if key_char == " " else key_char
        kb = self.user_prefs.keybindings
        if lookup in kb:
            action = kb[lookup]["action"]
            self.command_service.execute(action, self)

    def on_key(self, event: events.Key) -> None:
        leader_key = self.user_prefs.leader
        key = event.key
        char = event.character or ""

        # Identification of Leader Key
        is_leader = (char == leader_key) or (key == leader_key)
        if leader_key == "space" and key == "space":
            is_leader = True

        in_input = self.focused and self.focused.__class__.__name__ == "Input"
        is_modal_active = len(self.screen_stack) > 1

        # 1. Leader Mode Handling
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

        # 2. Enter Leader Mode
        if is_leader and not in_input:
            self.leader_mode = True
            try:
                self.query_one(StatusBar).mode = "LEADER"
            except:
                pass
            if self.user_prefs.show_which_key:
                self.push_screen(WhichKeyPopup())
            event.prevent_default()
            event.stop()
            return

        # 3. Global Navigation (Respecting Lua config)
        if not in_input and not is_modal_active:
            nav = self.user_prefs.nav_bindings

            # Switch panels (Left/Right)
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

            # Component-level navigation (Up/Down/Page)
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

        # 4. Bubble everything else
        # Enter will bubble to components.
        # Space (if NOT leader) will bubble and could trigger play_pause if bound.
        # But we don't bind it in BINDINGS now.
        if key == "space" and not is_leader and not in_input:
            # Manually trigger play_pause for space if it's the "spatial key"
            self.action_play_pause()
            event.stop()
            return
