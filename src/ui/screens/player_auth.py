import webbrowser
import threading
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, Button, Static, Footer, TextArea
from textual.containers import Vertical, Horizontal, Center
from src.core.di import Container
from src.network.local_player import LocalPlayer
from src.hooks.useCopyToClipboard import useCopyToClipboard

class PlayerAuthScreen(Screen):
    """Screen for authenticating the spotifyd background daemon."""
    
    def compose(self) -> ComposeResult:
        self.player = Container.resolve(LocalPlayer)
        self.auth_process = self.player.get_auth_process()
        self.auth_url = ""
        
        # Thread to read the URL from the process output
        threading.Thread(target=self._capture_url, daemon=True).start()

        with Vertical(id="setup-mini-card"):
            yield Label("󰓇 PLAYER AUTHORIZATION", id="setup-title-minimal")
            
            yield Static(
                "The background player needs authorization.\n"
                "Once the link is ready, copy or open it.",
                id="setup-simple-help"
            )

            with Horizontal(id="login-mini-actions"):
                yield Button("Open Link", variant="primary", id="open-player-browser-btn", classes="small-btn", disabled=True)
                yield Button("Copy Link", variant="default", id="copy-player-link-btn", classes="small-btn", disabled=True)

            yield Label("Authorization Link", classes="minimal-section-title")
            yield TextArea("", id="player-manual-link", classes="minimal-text-area", read_only=True)

            yield Label("Status: Waiting for daemon...", id="auth-status-lbl", classes="minimal-section-title")

            with Horizontal(id="setup-mini-actions"):
                yield Button("Cancel", variant="error", id="cancel-btn", classes="small-btn")
        yield Footer()

    def _capture_url(self):
        """Reads spotifyd output to find the authorization URL."""
        for line in iter(self.auth_process.stdout.readline, ''):
            if "Browse to:" in line:
                self.auth_url = line.split("Browse to:")[1].strip()
                self.app.call_from_thread(self._enable_buttons)
            
        # If the process finishes, it means auth is complete
        returncode = self.auth_process.wait()
        if returncode == 0:
            self.app.call_from_thread(self.app.exit, "player_auth_complete")

    def _enable_buttons(self):
        self.query_one("#open-player-browser-btn").disabled = False
        self.query_one("#copy-player-link-btn").disabled = False
        self.query_one("#player-manual-link").text = self.auth_url
        self.query_one("#auth-status-lbl").update("Status: [bold #a6e3a1]Link Ready[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-player-browser-btn":
            if self.auth_url:
                try:
                    if not webbrowser.open(self.auth_url):
                         self.app.notify("System could not open browser.", severity="warning")
                except Exception:
                    self.app.notify("Display error: Use 'Copy Link' instead.", severity="warning")
        elif event.button.id == "copy-player-link-btn":
            if self.auth_url and useCopyToClipboard(self.auth_url):
                self.app.notify("Link copied to clipboard!")
        elif event.button.id == "cancel-btn":
            self.auth_process.terminate()
            self.app.exit(result="player_auth_cancelled")
