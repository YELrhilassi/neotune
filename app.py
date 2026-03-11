import sys
import webbrowser
import time
import threading
from src.core.di import Container
from src.state.store import Store
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences
from src.network.spotify_network import SpotifyNetwork
from src.network.auth_service import AuthService
from src.network.playback_service import PlaybackService
from src.network.library_service import LibraryService
from src.network.discovery_service import DiscoveryService
from src.network.local_player import LocalPlayer
from src.network.auth_server import AuthServer
from src.core.command_service import CommandService
from src.core.cache import CacheStore
from src.core.activity_service import ActivityService
from src.ui.terminal_renderer import TerminalRenderer
from src.state.pubsub import PubSub
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, Static
from textual.containers import Vertical, Center


def setup_config():
    """Register essential services."""
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    Container.register(PubSub, PubSub, singleton=True)
    Container.register(Store, Store, singleton=True)
    Container.register(CommandService, CommandService, singleton=True)
    Container.register(CacheStore, CacheStore, singleton=True)
    Container.register(ActivityService, ActivityService, singleton=True)


def setup_spotify():
    """Register Spotify-dependent services with robust initialization."""
    client_config = Container.resolve(ClientConfiguration)
    if not client_config.is_valid():
        return False

    try:
        network = SpotifyNetwork(client_config)
        Container.register(SpotifyNetwork, lambda: network, singleton=True)
        Container.register(AuthService, lambda: network.auth, singleton=True)
        Container.register(PlaybackService, lambda: network.playback, singleton=True)
        Container.register(LibraryService, lambda: network.library, singleton=True)
        Container.register(DiscoveryService, lambda: network.discovery, singleton=True)

        if network.is_authenticated():
            try:
                # Update Network State
                Store().update(is_authenticated=True, api_connected=True)
                player = Container.resolve(LocalPlayer)
            except:
                player = LocalPlayer()
                Container.register(LocalPlayer, lambda: player, singleton=True)
            return True
    except Exception as e:
        print(f"Spotify initialization error: {e}")
    return False


class OnboardingScreen(Screen):
    def __init__(self, auth_url):
        super().__init__()
        self.auth_url = auth_url

    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="setup-mini-card"):
                yield Label("󰓇 Spotify TUI Setup", id="setup-title-minimal")
                yield Static(
                    "To begin, please complete the configuration in your browser.\n"
                    f"Visit: [bold cyan]http://127.0.0.1:8080[/]",
                    id="setup-simple-help",
                )
                yield Button("Open Browser (Desktop)", variant="primary", id="open-btn")
                yield Button("Quit", variant="error", id="quit-btn")
                yield Label("Waiting for configuration...", id="status-lbl")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-btn":
            try:
                webbrowser.open("http://127.0.0.1:8080")
            except Exception:
                self.app.notify("Failed to open browser automatically.", severity="warning")
        elif event.button.id == "quit-btn":
            self.app.exit()


class OnboardingApp(App):
    CSS_PATH = ["styles/main.tcss", "styles/_onboarding.tcss"]
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+q", "quit", "Quit"), ("q", "quit", "Quit")]

    def __init__(self, auth_server):
        super().__init__()
        self.auth_server = auth_server

    def on_mount(self):
        self.push_screen(OnboardingScreen("http://127.0.0.1:8080"))
        self.set_interval(1.0, self.check_server)

    def check_server(self):
        event = self.auth_server.get_event()
        if not event:
            return
        client_config = Container.resolve(ClientConfiguration)
        if event["type"] == "config":
            client_config.client_id = event["client_id"]
            client_config.client_secret = event["client_secret"]
            client_config.redirect_uri = event["redirect_uri"]
            client_config.save()
            network = SpotifyNetwork(client_config)
            Container.register(SpotifyNetwork, lambda: network, singleton=True)
            auth_url = network.get_auth_url()
            self.auth_server.set_auth_url(auth_url)
            try:
                webbrowser.open(auth_url)
            except Exception:
                pass
            self.screen.query_one("#status-lbl", Label).update(
                "Status: [bold yellow]Waiting for Spotify Auth...[/]\n[italic]Check your browser tab to complete login.[/]"
            )
        elif event["type"] == "callback":
            network = Container.resolve(SpotifyNetwork)
            if network.complete_login(event["url"]):
                self.exit(result="auth_complete")


if __name__ == "__main__":
    setup_config()
    client_config = Container.resolve(ClientConfiguration)

    if not client_config.is_valid() or not setup_spotify():
        server = AuthServer(port=8080)
        server.start()
        onboarding = OnboardingApp(server)
        result = onboarding.run()
        if result != "auth_complete":
            sys.exit(0)
        setup_spotify()

    player = Container.resolve(LocalPlayer)
    network = Container.resolve(SpotifyNetwork)
    if player and network:
        prefs = Container.resolve(UserPreferences)
        token = network.get_access_token()
        player.start(audio_config=prefs.audio_config, access_token=token)

    app = TerminalRenderer()
    try:
        app.run()
    except Exception as e:
        print(f"\n[Error] Application crashed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if player:
            try:
                player.stop()
            except KeyboardInterrupt:
                print("\n[Info] Forced exit...")
                try:
                    player.stop(wait=False)
                except:
                    pass
            except Exception:
                pass
