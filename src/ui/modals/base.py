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
        # Allow escape to always dismiss
        if event.key == "escape":
            self.dismiss()
            event.prevent_default()
            return
        
        # We removed the global j/k/h/l translation here to prevent double handling.
        # Subclasses or widgets should handle their own navigation.


