from textual.app import ComposeResult
from textual.widgets import Label, Button
from textual.containers import Vertical, Horizontal
from src.ui.modals.base import BaseModal
from textual import events

class ConfirmationModal(BaseModal[bool]):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirmation-dialog"):
            yield Label(self.message, id="confirmation-message")
            with Horizontal(id="confirmation-buttons"):
                yield Button("Yes", variant="primary", id="confirm-yes", classes="small-btn")
                yield Button("No", variant="error", id="confirm-no", classes="small-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key == "h":
            self.query_one("#confirm-yes").focus()
        elif event.key == "l":
            self.query_one("#confirm-no").focus()
        elif event.key in ("j", "k"):
            event.prevent_default()
        else:
            super().on_key(event)
