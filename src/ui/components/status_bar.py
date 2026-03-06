from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Horizontal
from src.core.di import Container
from src.state.store import Store
from src.core.strings import Strings

class StatusBar(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="status-container"):
            yield Label("", id="status-left")
            yield Label("", id="status-right")

    def on_mount(self):
        self.store = Container.resolve(Store)
        self.update_status()
        self.set_interval(2.0, self.update_status)

    def update_status(self):
        try:
            left_lbl = self.query_one("#status-left", Label)
            right_lbl = self.query_one("#status-right", Label)
        except Exception:
            return

        device_name = self.store.get("preferred_device_name")
        device_id = self.store.get("preferred_device_id")
        
        if device_name:
            device_display = device_name
        elif device_id:
            device_display = f"{device_id[:8]}..."
        else:
            device_display = "No Device"
            
        device_str = f"[#89b4fa]🔊 {device_display}[/]"
        
        auth_status = "[bold #a6e3a1]Connected[/]" if self.store.get("is_authenticated") else "[bold #f38ba8]Disconnected[/]"
        
        left_lbl.update(f"  [dim]Leader: Space[/]  |  {device_str}")
        right_lbl.update(f"{auth_status}  ")
