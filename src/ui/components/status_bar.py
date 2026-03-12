import threading
import time

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, Static

from src.core.di import Container
from src.core.icons import Icons
from src.state.store import Store


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

        # Subscribe to unified Store keys
        self.store.subscribe("current_playback", lambda val, **kw: self.safe_update())
        self.store.subscribe("api_connected", lambda val, **kw: self.safe_update())
        self.store.subscribe("is_authenticated", lambda val, **kw: self.safe_update())
        self.store.subscribe("preferred_device_name", lambda val, **kw: self.safe_update())
        self.store.subscribe("mode", lambda val, **kw: self.safe_update())
        self.store.subscribe("rate_limit_until", lambda val, **kw: self.safe_update())

        # Set interval for rate limit countdown and auto-retry
        self.set_interval(1.0, self._check_rate_limit_timer)

    def _check_rate_limit_timer(self):
        """Internal timer to handle rate limit countdown and trigger retries."""
        limit_until = self.store.get("rate_limit_until", 0)
        if limit_until > 0:
            now = time.time()
            if now >= limit_until:
                # Rate limit EXPIRED
                self.store.set("rate_limit_until", 0)

                # Trigger targeted retry for whatever data is currently missing
                from src.hooks.useTargetedRetry import useTargetedRetry

                useTargetedRetry(self.app)

            # Force UI update for the countdown
            self.safe_update()

    def safe_update(self):
        """Thread-safe update call."""
        if not self.app:
            return

        if threading.current_thread() is threading.main_thread():
            self.update_status()
        else:
            try:
                self.app.call_from_thread(self.update_status)
            except RuntimeError:
                self.update_status()

    def update_status(self):
        try:
            mode_lbl = self.query_one("#status-mode", Label)
            device_lbl = self.query_one("#status-device", Label)
            quality_lbl = self.query_one("#status-quality", Label)
            connection_lbl = self.query_one("#status-connection", Label)
            mode_sep = self.query_one("#status-mode-sep", Label)
            conn_sep = self.query_one("#status-connection-sep", Label)

            # 1. Update Mode
            current_mode = self.store.get("mode", "NORMAL")
            mode_lbl.update(f" {current_mode} ")
            mode_key = current_mode.lower()

            for m in ["normal", "leader", "search"]:
                if m == mode_key:
                    mode_lbl.add_class(m)
                    mode_sep.add_class(m)
                else:
                    mode_lbl.remove_class(m)
                    mode_sep.remove_class(m)

            # 2. Update Device Info
            device_name = self.store.get("preferred_device_name") or "No Device"
            device_lbl.update(f" {Icons.DEVICE} {device_name} ")

            # 3. Update Quality (from config)
            bitrate = self.user_prefs.audio_config.get("bitrate", "320")

            is_auth = self.store.get("is_authenticated")
            is_connected = self.store.get("api_connected")
            final_connected = bool(is_auth and is_connected)

            if final_connected:
                quality_lbl.update(f" 󰓇 {bitrate}kbps ")
                self.query_one("#status-quality-sep", Label).display = True
                quality_lbl.display = True
            else:
                quality_lbl.display = False
                self.query_one("#status-quality-sep", Label).display = False

            # 4. Update Connection Status
            status_text = "Connected" if final_connected else "Disconnected"
            status_icon = "󰄄" if final_connected else "󰂭"
            connection_lbl.update(f" {status_icon} {status_text} ")

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

            # 5. Rate Limit Warning (Middle)
            middle_lbl = self.query_one("#status-middle", Label)
            limit_until = self.store.get("rate_limit_until", 0)
            if limit_until > 0:
                remaining = int(max(0, limit_until - time.time()))
                if remaining > 0:
                    middle_lbl.update(
                        f" {Icons.INFO} [bold #f38ba8]Rate Limited: Paused for {remaining}s[/] "
                    )
                else:
                    middle_lbl.update("")
            else:
                middle_lbl.update("")

        except Exception:
            pass
