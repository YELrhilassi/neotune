from textual.widgets import OptionList
from src.core.icons import Icons
from src.core.utils import strip_icons
from src.core.strings import Strings

class TelescopeResults(OptionList):
    def update_list(self, category: str, data: list):
        self.clear_options()
        if not data:
            self.add_option(Strings.NO_RESULTS)
            return

        for item in data:
            if category == "tracks":
                artists = ", ".join([a['name'] for a in item.get('artists', []) if a.get('name')])
                self.add_option(f"{Icons.TRACK} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(artists)}")
            elif category == "albums":
                artists = ", ".join([a['name'] for a in item.get('artists', []) if a.get('name')])
                self.add_option(f"{Icons.ALBUM} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(artists)}")
            elif category == "playlists":
                owner = item.get('owner', {}).get('display_name', 'Unknown')
                self.add_option(f"{Icons.PLAYLIST} {strip_icons(item.get('name', 'Unknown'))} - {strip_icons(owner)}")
