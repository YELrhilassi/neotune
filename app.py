import sys
import webbrowser
import time
from src.core.di import Container
from src.state.store import Store
from src.config.client_config import ClientConfiguration
from src.config.user_prefs import UserPreferences
from src.network.spotify_network import SpotifyNetwork
from src.network.local_player import LocalPlayer
from src.network.auth_server import AuthServer
from src.core.command_service import CommandService
from src.core.cache import CacheStore
from src.ui.terminal_renderer import TerminalRenderer
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, Static
from textual.containers import Vertical, Center


def setup_config():
    """Register essential services that don't depend on Spotify Auth."""
    Container.register(ClientConfiguration, ClientConfiguration, singleton=True)
    Container.register(UserPreferences, UserPreferences, singleton=True)
    Container.register(Store, Store, singleton=True)
    Container.register(CommandService, CommandService, singleton=True)
    Container.register(CacheStore, CacheStore, singleton=True)


def setup_spotify():
    """Register Spotify-dependent services once config is valid."""
    client_config = Container.resolve(ClientConfiguration)
    if not client_config.is_valid():
        return False

    network = SpotifyNetwork(client_config)
    Container.register(SpotifyNetwork, lambda: network, singleton=True)

    if network.is_authenticated():
        player = LocalPlayer()
        Container.register(LocalPlayer, lambda: player, singleton=True)
        return True
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
                self.app.notify(
                    "Failed to open browser automatically.", severity="warning"
                )
        elif event.button.id == "quit-btn":
            self.app.exit()


class OnboardingApp(App):
    CSS_PATH = ["styles/main.tcss", "styles/_onboarding.tcss"]
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, auth_server):
        super().__init__()
        self.auth_server = auth_server
        self.config_done = False

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

            # Now trigger Spotify Login
            network = SpotifyNetwork(client_config)
            Container.register(SpotifyNetwork, lambda: network, singleton=True)
            auth_url = network.get_auth_url()

            # Pass the URL back to the server so the browser can see it
            self.auth_server.set_auth_url(auth_url)

            # Try to open browser, but don't worry if it fails
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

    # Check if we need to do the onboarding
    if not client_config.is_valid() or not setup_spotify():
        server = AuthServer(port=8080)
        server.start()

        onboarding = OnboardingApp(server)
        result = onboarding.run()

        if result != "auth_complete":
            sys.exit(0)

        setup_spotify()

    # Start Local Player (librespot)
    player = Container.resolve(LocalPlayer)
    network = Container.resolve(SpotifyNetwork)
    if player and network:
        # Since we use librespot direct now, it's easier
        prefs = Container.resolve(UserPreferences)
        token = network.get_access_token()
        player.start(audio_config=prefs.audio_config, access_token=token)

    # Launch main TUI
    app = TerminalRenderer()
    try:
        app.run()
    finally:
        if player:
            player.stop()
