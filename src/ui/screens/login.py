import webbrowser
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Label, Button, Static
from textual.containers import Vertical, Horizontal, Center
from src.core.di import Container
from src.network.spotify_network import SpotifyNetwork

class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        network = Container.resolve(SpotifyNetwork)
        self.auth_url = network.get_auth_url()
        
        with Center():
            with Vertical(id="setup-mini-card"):
                yield Label("󰓇 SPOTIFY AUTHORIZATION", id="setup-title-minimal")

                yield Static(
                    "1. Click the button to authorize in your browser.\n"
                    "2. If it fails, manually copy the link below.\n"
                    "3. Paste the redirected URL (starting with http://...) below.",
                    id="setup-simple-help"
                )
                
                with Horizontal(id="login-mini-actions"):
                    yield Button("Open Link", variant="primary", id="open-browser-btn", classes="small-btn")
                
                yield Label("Manual Link", classes="minimal-section-title")
                yield Input(value=self.auth_url, id="manual-link", classes="minimal-input", read_only=True)

                yield Label("Redirect URL", classes="minimal-section-title")
                yield Input(placeholder="Paste URL here...", id="redirect_url_input", classes="minimal-input")

                with Horizontal(id="setup-mini-actions"):
                    yield Button("Login", variant="success", id="login-btn", classes="small-btn")
                    yield Button("Back", variant="default", id="back-btn", classes="small-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-browser-btn":
            try:
                webbrowser.open(self.auth_url)
            except Exception:
                self.app.notify("Could not open browser. Please copy the link manually.", severity="warning")
        elif event.button.id == "login-btn":
            url = self.query_one("#redirect_url_input").value.strip()
            if not url:
                self.app.notify("Paste the URL!", severity="error")
                return
                
            network = Container.resolve(SpotifyNetwork)
            try:
                if network.complete_login(url):
                    self.app.exit(result="login_complete")
                else:
                    self.app.notify("Invalid URL.", severity="error")
            except Exception as e:
                self.app.notify(f"Error: {e}", severity="error")
        elif event.button.id == "back-btn":
            self.app.exit(result="back_to_setup")
