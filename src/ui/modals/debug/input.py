"""Custom input widget for the debug modal with Vim-like modes."""

from textual.widgets import Input
from textual.reactive import reactive
from textual import events, message


class DebugInput(Input):
    """A custom Input widget that supports Vim-like NORMAL and INSERT modes."""

    mode = reactive("NORMAL")

    async def _on_key(self, event: events.Key) -> None:
        if self.mode == "NORMAL":
            if event.character == "i":
                self.mode = "INSERT"
                event.stop()
                event.prevent_default()
                return
            elif event.character == "a":
                self.mode = "INSERT"
                self.cursor_position += 1
                event.stop()
                event.prevent_default()
                return
            elif event.character in ("H", "L"):
                # Bubble H/L to the parent modal for tab switching
                return
            elif event.character == "j" or event.key == "down":
                self.post_message(self.Navigate("down"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "k" or event.key == "up":
                self.post_message(self.Navigate("up"))
                event.stop()
                event.prevent_default()
                return

            if event.character and len(event.character) == 1:
                event.stop()
                event.prevent_default()
                return
        else:
            if event.key == "escape":
                self.mode = "NORMAL"
                event.stop()
                event.prevent_default()
                return

        await super()._on_key(event)

    def watch_mode(self, mode: str) -> None:
        """Apply classes based on mode."""
        self.set_class(mode == "INSERT", "-insert-mode")

    class Navigate(message.Message):
        """Message sent when navigating from input."""

        def __init__(self, direction: str):
            super().__init__()
            self.direction = direction
