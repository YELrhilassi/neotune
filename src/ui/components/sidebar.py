from textual.widgets import Tree
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.core.strings import Strings

class SidebarPanels(Tree):
    def on_mount(self):
        self.border_title = Strings.LIBRARY_TITLE
        self.root.expand()
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
        
        # Subscribe to updates
        self.store.subscribe("playlists", self.load_data)

    def load_data(self, _=None):
        self.clear()
        
        # We need state to get featured and recently played
        state_playlists = self.store.get("playlists") or []
        state_featured = self.store.get("featured_playlists") or []
        
        # 1. Your Playlists
        pl_node = self.root.add(f"{Icons.PLAYLIST} {Strings.YOUR_PLAYLISTS}", expand=True)
        for pl in state_playlists:
            pl_node.add_leaf(strip_icons(pl['name']), data={"type": "playlist", "id": pl['id']})
            
        # 2. Featured Playlists
        ft_node = self.root.add(f"{Icons.FEATURED} {Strings.FEATURED_PLAYLISTS}", expand=False)
        for pl in state_featured:
            ft_node.add_leaf(strip_icons(pl['name']), data={"type": "playlist", "id": pl['id']})
            
        # 3. Recently Played
        rp_node = self.root.add(f"{Icons.HISTORY} {Strings.HISTORY}", expand=False)
        rp_node.add_leaf(f"{Icons.TRACK} {Strings.SHOW_RECENT}", data={"type": "recent"})

    async def on_tree_node_selected(self, event: Tree.NodeSelected):
        data = event.node.data
        if not data: return
        
        if data.get("type") == "playlist":
            try:
                tracks = self.network.get_playlist_tracks(data['id'])
                self.store.set("current_tracks", tracks)
                self.app.query_one("TrackList").focus()
            except Exception as e:
                self.app.notify(f"Error loading tracks: {e}", severity="error")
                
        elif data.get("type") == "recent":
            recent = self.store.get("recently_played") or []
            self.store.set("current_tracks", recent)
            self.app.query_one("TrackList").focus()
