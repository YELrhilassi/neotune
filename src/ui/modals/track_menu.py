from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.containers import Middle
from src.ui.modals.base import BaseModal

class TrackMenuPopup(BaseModal[str]):
    def __init__(self, item_uri: str, item_name: str):
        super().__init__()
        self.item_uri = item_uri
        self.item_name = item_name
        
        is_track = ":track:" in item_uri
        is_playlist = ":playlist:" in item_uri
        is_album = ":album:" in item_uri
        is_artist = ":artist:" in item_uri
        
        play_label = "Play Track" if is_track else ("Play Playlist" if is_playlist else ("Play Album" if is_album else ("Play Artist" if is_artist else "Play")))
        
        self.actions = [
            (play_label, "play"),
        ]
        
        if is_track:
            self.actions.extend([
                ("Start Track Radio", "radio"),
                ("Save to Liked Songs", "save"),
                ("Remove from Liked Songs", "remove")
            ])

    def compose(self) -> ComposeResult:
        with Middle(id="track-menu-dialog"):
            yield Label(f"Options: {self.item_name}", id="track-menu-title")
            options = [action[0] for action in self.actions]
            yield OptionList(*options, id="track-menu-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        action_id = self.actions[event.option_index][1]
        self.dismiss(action_id)
