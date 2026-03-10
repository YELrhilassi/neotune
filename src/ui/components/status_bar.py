from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Horizontal
from textual.reactive import reactive
from src.core.di import Container
from src.state.store import Store
from src.core.icons import Icons

class StatusBar(Static):
    mode = reactive("NORMAL")

    def compose(self) -> ComposeResult:
        with Horizontal(id="status-container"):
            yield Label("", id="status-mode")
            yield Label("", id="status-mode-sep")
            yield Label("", id="status-left")
            yield Label("", id="status-left-sep")
            yield Label("", id="status-middle")
            yield Label("", id="status-right-sep")
            yield Label("", id="status-right")

    def on_mount(self):
        self.store = Container.resolve(Store)
        self.update_status()
        self.set_interval(2.0, self.update_status)

    def watch_mode(self, new_mode: str):
        self.update_status()

    def update_status(self):
        try:
            mode_lbl = self.query_one("#status-mode", Label)
            left_lbl = self.query_one("#status-left", Label)
            right_lbl = self.query_one("#status-right", Label)
            
            # Update Mode
            mode_lbl.update(f" {self.mode} ")
            mode_lbl.set_class(self.mode.lower(), True)
            self.query_one("#status-mode-sep", Label).set_class(self.mode.lower(), True)

            # Update Device Info
            device_name = self.store.get("preferred_device_name") or "No Device"
            left_lbl.update(f" {Icons.DEVICE} {device_name} ")

            # Update Connection Status
            auth_status = "Connected" if self.store.get("is_authenticated") else "Disconnected"
            auth_icon = "󰄄" if self.store.get("is_authenticated") else "󰂭"
            right_lbl.update(f" {auth_icon} {auth_status} ")

        except Exception:
            pass
