from textual.app import ComposeResult
from textual.widgets import OptionList, Static
from textual.containers import Vertical
from src.core.icons import Icons
from src.core.utils import strip_icons
from src.core.strings import Strings

class TelescopeResults(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("", classes="telescope-empty-state")
        yield OptionList(classes="telescope-results-list")

    def show_loading(self):
        lst = self.query_one(".telescope-results-list", OptionList)
        empty = self.query_one(".telescope-empty-state", Static)
        empty.display = False
        lst.display = True
        lst.loading = True

    def update_list(self, category: str, data: list):
        lst = self.query_one(".telescope-results-list", OptionList)
        empty = self.query_one(".telescope-empty-state", Static)
        lst.clear_options()
        
        if not data:
            lst.display = False
            empty.display = True
            empty.update(f"[bold #a6adc8]{Icons.SEARCH} Search for {category}...[/]")
            return

        lst.display = True
        empty.display = False
        
        for item in data:
            if category == "tracks":
                artists = ", ".join([a['name'] for a in item.get('artists', []) if a.get('name')])
                lst.add_option(f"{Icons.TRACK} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(artists)}")
            elif category == "albums":
                artists = ", ".join([a['name'] for a in item.get('artists', []) if a.get('name')])
                lst.add_option(f"{Icons.ALBUM} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(artists)}")
            elif category == "playlists":
                owner = item.get('owner', {}).get('display_name', 'Unknown')
                lst.add_option(f"{Icons.PLAYLIST} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(owner)}")
