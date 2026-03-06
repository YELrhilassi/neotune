from textual.app import ComposeResult
from textual.widgets import Input, Label
from textual.containers import Horizontal
from textual import events

class TelescopeInput(Input):
    """
    A custom Input widget that supports Vim-like NORMAL and INSERT modes.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = "NORMAL"

    async def _on_key(self, event: events.Key) -> None:
        if self.mode == "NORMAL":
            # Handle Mode Entry
            if event.character == "i":
                self.mode = "INSERT"
                self.post_message(self.ModeChanged("INSERT"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "a":
                self.mode = "INSERT"
                self.cursor_position += 1
                self.post_message(self.ModeChanged("INSERT"))
                event.stop()
                event.prevent_default()
                return

            # Navigation Keys (Navigation within the modal, not the text)
            if event.key == "tab":
                self.post_message(self.Navigate("next"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "shift+tab":
                self.post_message(self.Navigate("prev"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "j" or event.key == "down":
                self.post_message(self.Navigate("down"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "l" or event.key == "right":
                self.post_message(self.Navigate("right"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "H":
                self.post_message(self.Navigate("tab_prev"))
                event.stop()
                event.prevent_default()
                return
            elif event.character == "L":
                self.post_message(self.Navigate("tab_next"))
                event.stop()
                event.prevent_default()
                return
            elif event.key == "escape":
                # Let it bubble to close the modal
                return

            # Strictly block all other printable characters in NORMAL mode
            if event.character and len(event.character) == 1:
                event.stop()
                event.prevent_default()
                return
        else:
            # INSERT mode
            if event.key == "escape":
                self.mode = "NORMAL"
                self.post_message(self.ModeChanged("NORMAL"))
                event.stop()
                event.prevent_default()
                return
        
        # If not handled, let the base class process it (e.g. typing in INSERT mode)
        await super()._on_key(event)

    def on_blur(self, event: events.Blur) -> None:
        """Automatically revert to NORMAL mode when focus is lost."""
        if self.mode != "NORMAL":
            self.mode = "NORMAL"
            self.post_message(self.ModeChanged("NORMAL"))

    class ModeChanged(events.Message):
        def __init__(self, mode: str):
            super().__init__()
            self.mode = mode

    class Navigate(events.Message):
        def __init__(self, direction: str):
            super().__init__()
            self.direction = direction

class TelescopeHeader(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label("🔍", id="telescope-icon")
        yield TelescopeInput(placeholder="Search Spotify...", id="telescope-input")
        yield Label("[dim] [i/a] Insert • [H/L] Tabs • [h/l] Panels • [j/k] Move [/]", id="telescope-hints")
