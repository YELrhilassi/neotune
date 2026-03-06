from textual.app import ComposeResult
from textual.widgets import Label
from textual.containers import Vertical, Grid
from textual import events

from src.ui.modals.base import BaseModal
from src.core.di import Container
from src.config.user_prefs import UserPreferences

class WhichKeyPopup(BaseModal):
    def compose(self) -> ComposeResult:
        with Vertical(id="which-key-dialog"):
            yield Label("[bold #89b4fa]Which Key?[/]", id="which-key-title")
            with Grid(id="which-key-grid"):
                prefs = Container.resolve(UserPreferences)
                keymaps = prefs.keybindings or {}
                for k, val in keymaps.items():
                    yield Label(f"[bold #a6e3a1]{k}[/] [dim]→[/] [#cdd6f4]{val['desc']}[/]")

    def on_key(self, event: events.Key):
        # We don't process keys here anymore. 
        # The main app intercepts keys while leader_mode is true.
        if event.key == "escape":
            self.dismiss()
            return
        super().on_key(event)
