from textual.app import ComposeResult
from textual.widgets import Label
from textual.containers import Horizontal

class TelescopeTabs(Horizontal):
    def compose(self) -> ComposeResult:
        yield Label(" Songs ", id="tab-tracks", classes="tab active")
        yield Label(" Albums ", id="tab-albums", classes="tab")
        yield Label(" Playlists ", id="tab-playlists", classes="tab")
    
    def update_tabs(self, active_category: str):
        for cat in ["tracks", "albums", "playlists"]:
            tab = self.query_one(f"#tab-{cat}", Label)
            tab.set_class(cat == active_category, "active")
