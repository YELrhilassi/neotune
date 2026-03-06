import uuid
from textual.widgets import DataTable
from src.core.di import Container
from src.state.store import Store
from src.ui.modals.track_menu import TrackMenuPopup
from src.hooks.track_actions import play_track, start_track_radio, save_track, remove_saved_track
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings

class TrackList(DataTable):
    def on_mount(self):
        self.border_title = Strings.TRACKS_TITLE
        self.add_columns(f"{Icons.TRACK} Track", f"{Icons.ARTIST} Artist", f"{Icons.ALBUM} Album", f"{Icons.DURATION} Duration")
        self.cursor_type = "row"
        self.store = Container.resolve(Store)
        self.store.subscribe("current_tracks", self.load_tracks)

    def load_tracks(self, tracks: list):
        self.clear()
        if not tracks:
            return
            
        self.track_data_map = {}

        for item in tracks:
            track = item.get('track', item) 
            if not track or 'name' not in track: continue
            
            artists = ", ".join([strip_icons(a['name']) for a in track['artists']])
            duration_ms = track.get('duration_ms', 0)
            duration_min = duration_ms // 60000
            duration_sec = (duration_ms % 60000) // 1000
            duration_str = f"{duration_min}:{duration_sec:02d}"
            
            # Use UUID to prevent DuplicateKey error if same track appears multiple times in history
            unique_key = f"{track['uri']}_{uuid.uuid4().hex[:8]}"
            self.track_data_map[unique_key] = track
            
            self.add_row(
                strip_icons(track['name']), artists, strip_icons(track.get('album', {}).get('name', 'Unknown')), duration_str,
                key=unique_key
            )

    async def on_data_table_row_selected(self, event: DataTable.RowSelected):
        key = event.row_key.value
        track_data = self.track_data_map.get(key)
        if not track_data: return
        
        artists = ", ".join([a['name'] for a in track_data.get('artists', [])])
        display_name = f"{track_data['name']} by {artists}"
        
        def on_action_selected(action: str):
            if action == "play":
                if play_track(track_data['uri'], self.app):
                    self.app.update_now_playing()
            elif action == "radio":
                start_track_radio(track_data['uri'], self.app)
            elif action == "save":
                save_track(track_data['uri'], self.app)
            elif action == "remove":
                remove_saved_track(track_data['uri'], self.app)
                
        self.app.push_screen(TrackMenuPopup(track_data['uri'], display_name), on_action_selected)
