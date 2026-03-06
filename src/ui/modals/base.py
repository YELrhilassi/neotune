from textual.screen import ModalScreen
from textual.binding import Binding
from textual import events
from typing import TypeVar
from src.core.di import Container
from src.config.user_prefs import UserPreferences

ResultType = TypeVar("ResultType")

class BaseModal(ModalScreen[ResultType]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close")
    ]
    
    def on_key(self, event: events.Key):
        prefs = Container.resolve(UserPreferences)
        nav = prefs.nav_bindings
        char = event.character
        
        in_input = self.focused and self.focused.__class__.__name__ == "Input"
        
        if not in_input and char:
            if char == nav.get("down"):
                if hasattr(self.focused, "action_cursor_down"):
                    self.focused.action_cursor_down()
                event.prevent_default()
                return
            elif char == nav.get("up"):
                if hasattr(self.focused, "action_cursor_up"):
                    self.focused.action_cursor_up()
                event.prevent_default()
                return
            elif char == nav.get("page_down"):
                if hasattr(self.focused, "action_page_down"):
                    self.focused.action_page_down()
                event.prevent_default()
                return
            elif char == nav.get("page_up"):
                if hasattr(self.focused, "action_page_up"):
                    self.focused.action_page_up()
                event.prevent_default()
                return

