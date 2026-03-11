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
            # Left: Mode and Device
            with Horizontal(id="status-left-group"):
                yield Label("", id="status-mode")
                yield Label("", id="status-mode-sep")
                yield Label("", id="status-device")
                yield Label("", id="status-device-sep")

            # Middle: Filler
            yield Label("", id="status-middle")

            # Right: Quality and Connection
            with Horizontal(id="status-right-group"):
                yield Label("", id="status-quality-sep")
                yield Label("", id="status-quality")
                yield Label("", id="status-connection-sep")
                yield Label("", id="status-connection")

    def on_mount(self):
        self.store = Container.resolve(Store)
        from src.config.user_prefs import UserPreferences

        self.user_prefs = Container.resolve(UserPreferences)

        # Subscribe to specific keys that affect status bar
        self.store.subscribe("current_playback", lambda _: self.safe_update())
        self.store.subscribe("api_connected", lambda _: self.safe_update())
        self.store.subscribe("is_authenticated", lambda _: self.safe_update())
        self.store.subscribe("preferred_device_name", lambda _: self.safe_update())
        self.store.subscribe("devices", lambda _: self.safe_update())

        # Also poll occasionally as fallback

        self.set_interval(5.0, self.update_status)
        self.update_status()

    def safe_update(self):
        """Thread-safe update call."""
        if not self.app:
            return

        # Check if we are already in the main thread
        import threading

        if threading.current_thread() is threading.main_thread():
            self.update_status()
        else:
            try:
                self.app.call_from_thread(self.update_status)
            except RuntimeError:
                # Fallback in case main_thread check isn't enough
                self.update_status()

    def watch_mode(self, new_mode: str):
        self.update_status()

    def update_status(self):
        try:
            # Query labels each time to be safe, but use IDs
            mode_lbl = self.query_one("#status-mode", Label)
            device_lbl = self.query_one("#status-device", Label)
            quality_lbl = self.query_one("#status-quality", Label)
            connection_lbl = self.query_one("#status-connection", Label)
            mode_sep = self.query_one("#status-mode-sep", Label)
            conn_sep = self.query_one("#status-connection-sep", Label)

            # 1. Update Mode
            mode_lbl.update(f" {self.mode} ")
            mode_key = self.mode.lower()

            # Reset and apply mode class
            for m in ["normal", "leader", "search"]:
                if m == mode_key:
                    mode_lbl.add_class(m)
                    mode_sep.add_class(m)
                else:
                    mode_lbl.remove_class(m)
                    mode_sep.remove_class(m)

            # 2. Update Device Info
            playback = self.store.get("current_playback")
            device_name = "No Device"
            if playback and playback.get("device"):
                device_name = playback["device"].get("name", "Unknown")
            elif self.store.get("preferred_device_name"):
                device_name = self.store.get("preferred_device_name")

            device_lbl.update(f" {Icons.DEVICE} {device_name} ")

            # 3. Update Quality (from config)
            bitrate = self.user_prefs.audio_config.get("bitrate", "320")
            quality_lbl.update(f" 󰓇 {bitrate}kbps ")

            # 4. Update Connection Status
            is_auth = self.store.get("is_authenticated")
            is_connected = bool(self.store.get("api_connected"))

            final_connected = is_auth and is_connected

            status_text = "Connected" if final_connected else "Disconnected"
            status_icon = "󰄄" if final_connected else "󰂭"
            connection_lbl.update(f" {status_icon} {status_text} ")

            # Apply connection state classes for styling
            if final_connected:
                connection_lbl.add_class("connected")
                conn_sep.add_class("connected")
                connection_lbl.remove_class("disconnected")
                conn_sep.remove_class("disconnected")
            else:
                connection_lbl.add_class("disconnected")
                conn_sep.add_class("disconnected")
                connection_lbl.remove_class("connected")
                conn_sep.remove_class("connected")

        except Exception:
            pass
