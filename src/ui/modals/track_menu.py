from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.containers import Middle
from src.ui.modals.base import BaseModal

class TrackMenuPopup(BaseModal[str]):
    def __init__(self, track_uri: str, track_name: str):
        super().__init__()
        self.track_uri = track_uri
        self.track_name = track_name
        self.actions = [
            ("Play Track", "play"),
            ("Start Track Radio", "radio"),
            ("Save to Liked Songs", "save"),
            ("Remove from Liked Songs", "remove")
        ]

    def compose(self) -> ComposeResult:
        with Middle(id="track-menu-dialog"):
            yield Label(f"Options: {self.track_name}", id="track-menu-title")
            options = [action[0] for action in self.actions]
            yield OptionList(*options, id="track-menu-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        action_id = self.actions[event.option_index][1]
        self.dismiss(action_id)
