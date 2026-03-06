from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Horizontal, Vertical
from src.core.di import Container
from src.state.store import Store
from src.models.types import PlaybackDict
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings

class NowPlaying(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="np-container"):
            with Vertical(id="np-info"):
                yield Label(f"[dim]{Icons.PAUSE} {Strings.PAUSED_OR_NOTHING}[/]", id="np-track-name")
                yield Label("", id="np-artist-name")
            
            with Horizontal(id="np-controls"):
                yield Label("", id="np-shuffle-icon")
                yield Label("", id="np-repeat-icon")

    def on_mount(self):
        self.store = Container.resolve(Store)
        self.store.subscribe("current_playback", self.update_playback)

    def update_playback(self, playback: PlaybackDict | None):
        # Fail gracefully if widgets are not yet mounted during early intervals
        try:
            track_lbl = self.query_one("#np-track-name", Label)
            artist_lbl = self.query_one("#np-artist-name", Label)
            shuffle_lbl = self.query_one("#np-shuffle-icon", Label)
            repeat_lbl = self.query_one("#np-repeat-icon", Label)
        except Exception:
            return

        if playback and playback.get('is_playing') and playback.get('item'):
            item = playback['item']
            artists = strip_icons(", ".join([a['name'] for a in item['artists']]))
            track_name = strip_icons(item['name'])
            
            # Formatting states
            shuffle_icon = Icons.SHUFFLE_ON if playback.get('shuffle_state') else Icons.SHUFFLE_OFF
            repeat_state = playback.get('repeat_state', 'off')
            repeat_icon = Icons.REPEAT_CONTEXT if repeat_state == 'context' else (Icons.REPEAT_TRACK if repeat_state == 'track' else Icons.REPEAT_OFF)
            
            track_lbl.update(f"[bold #a6e3a1]{Icons.PLAY}  {track_name}[/]")
            artist_lbl.update(f"[#cdd6f4]{Icons.ARTIST}  {artists}[/]")
            shuffle_lbl.update(f"[#89b4fa] {shuffle_icon} [/]")
            repeat_lbl.update(f"[#89b4fa] {repeat_icon} [/]")
        else:
            device_name = self.store.get("preferred_device_name") or "No Active Device"
            track_lbl.update(f"[dim]{Icons.PAUSE} {Strings.PAUSED_OR_NOTHING}[/] [bold #89b4fa]({device_name})[/]")
            artist_lbl.update("")
            shuffle_lbl.update("")
            repeat_lbl.update("")
