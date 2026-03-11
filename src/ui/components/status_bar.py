from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Horizontal
from textual.reactive import reactive
from src.core.di import Container
from src.state.store import Store
from src.core.icons import Icons


from src.state.feature_stores import PlaybackStore, NetworkStore, DeviceStore, ConfigStore, UIStore


class StatusBar(Static):
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

        # Resolve Feature Stores
        self.playback_store = Container.resolve(PlaybackStore)
        self.network_store = Container.resolve(NetworkStore)
        self.device_store = Container.resolve(DeviceStore)
        self.config_store = Container.resolve(ConfigStore)
        self.ui_store = Container.resolve(UIStore)

        # Subscribe to Feature Stores
        self.playback_store.subscribe(lambda _: self.safe_update())
        self.network_store.subscribe(lambda _: self.safe_update())
        self.device_store.subscribe(lambda _: self.safe_update())
        self.config_store.subscribe(lambda _: self.safe_update())
        self.ui_store.subscribe(lambda _: self.safe_update())

        # Mode is still reactive via Textual
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
            ui_state = self.ui_store.get()
            current_mode = ui_state.get("mode", "NORMAL")
            mode_lbl.update(f" {current_mode} ")
            mode_key = current_mode.lower()

            # Reset and apply mode class
            for m in ["normal", "leader", "search"]:
                if m == mode_key:
                    mode_lbl.add_class(m)
                    mode_sep.add_class(m)
                else:
                    mode_lbl.remove_class(m)
                    mode_sep.remove_class(m)

            # 2. Update Device Info
            device_state = self.device_store.get()
            device_name = device_state.get("preferred_name") or "No Device"

            # If nothing is actually playing, playback might show a different device or None
            # But the user wants the selected device.

            device_lbl.update(f" {Icons.DEVICE} {device_name} ")

            # 3. Update Quality (from config)
            config_state = self.config_store.get()
            audio_cfg = config_state.get("audio", {})
            bitrate = audio_cfg.get("bitrate", self.user_prefs.audio_config.get("bitrate", "320"))

            # Only show quality if we are connected to reflect dynamic state
            if final_connected:
                quality_lbl.update(f" 󰓇 {bitrate}kbps ")
                self.query_one("#status-quality-sep", Label).display = True
                quality_lbl.display = True
            else:
                quality_lbl.display = False
                self.query_one("#status-quality-sep", Label).display = False

            # 4. Update Connection Status
            net_state = self.network_store.get()
            is_auth = net_state.get("is_authenticated")
            is_connected = net_state.get("api_connected")

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
