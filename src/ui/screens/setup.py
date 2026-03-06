from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Label, Button, Static, Header, Footer
from textual.containers import Vertical, Horizontal, Center
from src.core.di import Container
from src.config.client_config import ClientConfiguration

class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="setup-form"):
                yield Label("Spotify TUI Configuration", id="setup-title")
                yield Static(
                    "Welcome! Let's get you connected to Spotify.\n\n"
                    "1. [bold]Create App:[/] Visit [blue]developer.spotify.com/dashboard[/]\n"
                    "2. [bold]Credentials:[/] Paste your [italic]Client ID[/] and [italic]Secret[/] below.\n"
                    "3. [bold]Redirect URI:[/] Ensure [italic]http://127.0.0.1:8080[/] is whitelisted in your app settings.\n"
                    "4. [bold]spotifyd:[/] Provide your username/password for high-quality playback daemon support.",
                    id="setup-help"
                )
                
                with Vertical(classes="input-group"):
                    yield Label("Spotify API Client ID")
                    yield Input(placeholder="Paste ID...", id="client_id")
                    
                    yield Label("Spotify API Client Secret")
                    yield Input(placeholder="Paste Secret...", id="client_secret", password=True)
                    
                    yield Label("Redirect URI")
                    yield Input(value="http://127.0.0.1:8080", id="redirect_uri")
                
                with Vertical(classes="input-group"):
                    yield Label("Spotify Username (for spotifyd)")
                    yield Input(placeholder="Username...", id="username")
                    
                    yield Label("Spotify Password (for spotifyd)")
                    yield Input(placeholder="Password...", id="password", password=True)
                
                with Horizontal(id="setup-buttons"):
                    yield Button("Complete Setup", variant="primary", id="save-btn")
                    yield Button("Quit", variant="error", id="quit-btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            config = Container.resolve(ClientConfiguration)
            config.client_id = self.query_one("#client_id").value.strip()
            config.client_secret = self.query_one("#client_secret").value.strip()
            config.redirect_uri = self.query_one("#redirect_uri").value.strip()
            config.username = self.query_one("#username").value.strip()
            config.password = self.query_one("#password").value.strip()
            
            if config.is_valid():
                config.save()
                self.app.exit(result="setup_complete")
            else:
                self.app.notify("Client ID and Secret are required!", severity="error")
        elif event.button.id == "quit-btn":
            self.app.exit()
