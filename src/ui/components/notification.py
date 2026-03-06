from textual.widgets import Static
from textual.app import ComposeResult
from textual import work

class CustomNotification(Static):
    def __init__(self, message: str, severity: str = "information"):
        super().__init__(message, classes=f"notification {severity}")
        self.message = message
        self.severity = severity

    def on_mount(self):
        self.set_timer(3.0, self.dismiss)

    @work(exclusive=True)
    async def dismiss(self):
        await self.remove()
