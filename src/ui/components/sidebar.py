from textual.containers import Vertical
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.core.strings import Strings
from src.ui.components.content_tree.content_tree import ContentTree


class SidebarPanels(Vertical):
    def compose(self):
        yield ContentTree(id="content-tree")

    def on_mount(self):
        self.border_title = Strings.LIBRARY_TITLE
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
