from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Label, Button, Static
from textual.containers import Vertical, Horizontal, Center
from src.core.di import Container
from src.config.client_config import ClientConfiguration

class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        with Center():
            with Vertical(id="setup-mini-card"):
                yield Label("󰓇 Setup", id="setup-title-minimal")
                
                yield Static(
                    "Create an app at [bold]developer.spotify.com[/] and paste your credentials below.",
                    id="setup-simple-help"
                )
                
                yield Label("API Credentials", classes="minimal-section-title")
                yield Input(placeholder="Spotify Client ID", id="client_id", classes="minimal-input")
                yield Input(placeholder="Spotify Client Secret", id="client_secret", password=True, classes="minimal-input")
                yield Input(value="http://127.0.0.1:8080", id="redirect_uri", classes="minimal-input")

                with Horizontal(id="setup-mini-actions"):
                    yield Button("Finish", variant="primary", id="save-btn", classes="small-btn")
                    yield Button("Exit", variant="error", id="quit-btn", classes="small-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            config = Container.resolve(ClientConfiguration)
            config.client_id = self.query_one("#client_id").value.strip()
            config.client_secret = self.query_one("#client_secret").value.strip()
            config.redirect_uri = self.query_one("#redirect_uri").value.strip()
            
            if config.is_valid():
                config.save()
                self.app.exit(result="setup_complete")
            else:
                self.app.notify("Client ID and Secret are required!", severity="error")
        elif event.button.id == "quit-btn":
            self.app.exit()
