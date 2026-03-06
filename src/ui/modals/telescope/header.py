from textual.app import ComposeResult
from textual.widgets import Input, Label
from textual.containers import Horizontal

class TelescopeHeader(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("🔍", id="telescope-icon")
        yield Input(placeholder="Search Spotify...", id="telescope-input")
        yield Label("[dim] [H/L] Tabs • [h/l] Panels • [j/k] Move [/]", id="telescope-hints")
