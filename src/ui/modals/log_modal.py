from typing import cast, TYPE_CHECKING
from textual.app import ComposeResult
from textual.widgets import RichLog
from src.ui.modals.base import BaseModal

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class LogModal(BaseModal):
    def compose(self) -> ComposeResult:
        yield RichLog(id="app-logs", highlight=True, markup=True)

    def on_mount(self) -> None:
        log_widget = self.query_one(RichLog)

        # 1. Show librespot player logs if they exist
        try:
            from src.core.di import Container
            from src.network.local_player import LocalPlayer
            import os

            player = Container.resolve(LocalPlayer)
            log_path = os.path.join(player.cache_dir, "librespot.log")
            if os.path.exists(log_path):
                log_widget.write("[bold #89b4fa]=== Player Logs (librespot.log) ===[/]")
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-50:]:  # Show last 50 lines
                        log_widget.write(f"[#6c7086]{line.strip()}[/]")
                log_widget.write("\n[bold #cba6f7]=== Application Logs ===[/]")
        except Exception:
            pass

        # 2. Show internal app logs
        from src.ui.terminal_renderer import TerminalRenderer

        if isinstance(self.app, TerminalRenderer):
            app = cast(TerminalRenderer, self.app)
            for line in app._log_buffer:
                log_widget.write(line)

    def write(self, content):
        self.query_one(RichLog).write(content)
