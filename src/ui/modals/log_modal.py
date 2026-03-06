from textual.app import ComposeResult
from textual.widgets import RichLog
from src.ui.modals.base import BaseModal

class LogModal(BaseModal):
    def compose(self) -> ComposeResult:
        yield RichLog(id="app-logs", highlight=True, markup=True)

    def on_mount(self) -> None:
        log_widget = self.query_one(RichLog)
        # Pull logs from the app's log buffer if possible, 
        # but for now we will just show what has been logged during this session
        for line in self.app._log_buffer:
            log_widget.write(line)

    def write(self, content):
        self.query_one(RichLog).write(content)
