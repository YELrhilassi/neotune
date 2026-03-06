from textual.app import ComposeResult
from textual.widgets import Static, OptionList
from textual.containers import Vertical
from textual.markup import escape
from src.core.icons import Icons
from src.core.utils import strip_icons

class TelescopePreview(Vertical):
    def compose(self) -> ComposeResult:
        yield Static(f"[bold #a6adc8]{Icons.SEARCH} Select an item to see details[/]", classes="telescope-empty-state")
        yield Static("", classes="telescope-preview-info")
        yield OptionList(classes="telescope-preview-tracks")

    def update_preview(self, category: str, data: dict):
        empty_state = self.query_one(".telescope-empty-state", Static)
        info_panel = self.query_one(".telescope-preview-info", Static)
        tracks_list = self.query_one(".telescope-preview-tracks", OptionList)
        
        if not data:
            empty_state.display = True
            info_panel.display = False
            tracks_list.display = False
            return

        empty_state.display = False
        info_panel.display = True
        tracks_list.display = False

        if category == "tracks":
            artists = ", ".join([strip_icons(a['name']) for a in data.get('artists', []) if a and a.get('name')])
            album_name = strip_icons(data.get('album', {}).get('name', 'Unknown'))
            duration_ms = data.get('duration_ms', 0)
            duration_str = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
            
            info = f"[bold #a6e3a1]{Icons.TRACK} {strip_icons(data.get('name', 'Unknown'))}[/]\n\n"
            info += f"[#cdd6f4]{Icons.ARTIST} Artist:[/] {artists}\n"
            info += f"[#cdd6f4]{Icons.ALBUM} Album:[/] {album_name}\n"
            info += f"[#cdd6f4]{Icons.DURATION} Duration:[/] {duration_str}\n"
            info_panel.update(info)

        elif category == "albums":
            artists = ", ".join([strip_icons(a['name']) for a in data.get('artists', []) if a and a.get('name')])
            total_tracks = data.get('total_tracks', 0)
            release_date = data.get('release_date', 'Unknown')
            
            info = f"[bold #f9e2af]{Icons.ALBUM} {strip_icons(data.get('name', 'Unknown'))}[/]\n\n"
            info += f"[#a6e3a1]{Icons.ARTIST} Artist:[/] {artists}\n"
            info += f"[#cba6f7]📅 Release:[/] {release_date}\n"
            info += f"[#89b4fa]{Icons.TRACK} Tracks:[/] {total_tracks}\n"
            info_panel.update(info)
            tracks_list.display = True
            tracks_list.clear_options()
            tracks_list.add_option("Loading tracks...")

        elif category == "playlists":
            owner = strip_icons(data.get('owner', {}).get('display_name', 'Unknown'))
            total_tracks = data.get('tracks', {}).get('total', 0)
            desc = strip_icons(data.get('description', ''))
            
            info = f"[bold #89b4fa]{Icons.PLAYLIST} {strip_icons(data.get('name', 'Unknown'))}[/]\n\n"
            info += f"[#a6e3a1]{Icons.ARTIST} Owner:[/] {owner}\n"
            info += f"[#cba6f7]{Icons.TRACK} Tracks:[/] {total_tracks}\n"
            if desc:
                info += f"\n[dim italic]{escape(desc)}[/]\n"
            info_panel.update(info)
            tracks_list.display = True
            tracks_list.clear_options()
            tracks_list.add_option("Loading tracks...")

    def update_tracks(self, tracks: list):
        tracks_list = self.query_one(".telescope-preview-tracks", OptionList)
        tracks_list.clear_options()
        if not tracks:
            tracks_list.add_option("No tracks found.")
            return
        for t in tracks:
            if not t: continue
            name = strip_icons(t.get('name', 'Unknown'))
            artists = ", ".join([a['name'] for a in t.get('artists', []) if a and a.get('name')])
            tracks_list.add_option(f"{Icons.TRACK} {name} - {strip_icons(artists)}")
