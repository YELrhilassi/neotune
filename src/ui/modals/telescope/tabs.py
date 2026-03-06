from textual.app import ComposeResult
from textual.widgets import Tabs, Tab
from textual.containers import Horizontal

class TelescopeTabs(Horizontal):
    def compose(self) -> ComposeResult:
        yield Tabs(
            Tab("Songs", id="tab-tracks"),
            Tab("Albums", id="tab-albums"),
            Tab("Playlists", id="tab-playlists"),
        )
    
    def update_tabs(self, active_category: str):
        try:
            tabs = self.query_one(Tabs)
            tabs.active = f"tab-{active_category}"
        except Exception:
            pass
