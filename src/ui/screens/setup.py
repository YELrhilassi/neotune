from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Label, Button, Static, Header, Footer
from textual.containers import Vertical, Horizontal, Center, Container as TextualContainer
from src.core.di import Container
from src.config.client_config import ClientConfiguration

class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="setup-card"):
                yield Label("󰓇 Spotify TUI Setup", id="setup-title")
                
                with Horizontal(id="setup-split"):
                    with Vertical(id="setup-info"):
                        yield Label("Instructions", classes="section-title")
                        yield Static(
                            "1. Visit [bold #89b4fa]developer.spotify.com[/]\n"
                            "2. Create a [italic]New App[/].\n"
                            "3. Copy [bold]Client ID[/] & [bold]Secret[/].\n"
                            "4. Set Redirect URI to:\n   [italic #a6e3a1]http://127.0.0.1:8080[/]\n\n"
                            "[dim]spotifyd requires your account credentials for DRM playback.[/dim]",
                            id="setup-help"
                        )
                    
                    with Vertical(id="setup-inputs"):
                        yield Label("API Credentials", classes="section-title")
                        with Vertical(classes="input-group"):
                            yield Input(placeholder="Client ID", id="client_id")
                            yield Input(placeholder="Client Secret", id="client_secret", password=True)
                            yield Input(value="http://127.0.0.1:8080", id="redirect_uri")
                        
                        yield Label("Spotify Account (Local Player)", classes="section-title")
                        with Vertical(classes="input-group"):
                            yield Input(placeholder="Username", id="username")
                            yield Input(placeholder="Password", id="password", password=True)

                with Horizontal(id="setup-footer"):
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
