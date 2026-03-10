from typing import Dict, Any, List, Optional, cast, Set, TYPE_CHECKING
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from textual.binding import Binding
from textual import work, events, on
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.ui.components.content_tree.tree_nodes import (
    LikedSongsBranch,
    PlaylistsBranch,
    FeaturedBranch,
)

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class ContentTree(Tree):
    """
    The primary navigation component, organized into isolated functional branches.
    Uses centralized state management to reactively update its structure.
    """

    # We do NOT override BINDINGS with an empty list.
    # This allows default Enter/Space/Arrows to work.

    def __init__(self, **kwargs):
        super().__init__("Root", **kwargs)
        self.show_root = False
        self.store = Container.resolve(Store)
        self.network = Container.resolve(SpotifyNetwork)
        self._refresh_timer = None
        self._is_refreshing = False

    def on_mount(self):
        self.store.subscribe("playlists", self._reactive_refresh)
        self.store.subscribe("browse_metadata", self._reactive_refresh)
        self.store.subscribe("recently_played", self._reactive_refresh)
        self.store.subscribe("loading_states", self._handle_loading)

        self.refresh_tree()

    def _handle_loading(self, states):
        if states and self.app:
            new_loading = states.get("sidebar", False)
            if self.loading != new_loading:
                self.loading = new_loading

    def _reactive_refresh(self, data):
        if not self.app:
            return
        if self._refresh_timer:
            self._refresh_timer.cancel()

        import threading

        def _deferred():
            if self.app:
                self.app.call_from_thread(self.refresh_tree)

        self._refresh_timer = threading.Timer(1.0, _deferred)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def refresh_tree(self):
        """Rebuilds the tree structure while maintaining UI state."""
        if not self.app or self._is_refreshing:
            return

        self._is_refreshing = True
        try:
            expanded_ids = self._get_expanded_node_ids(self.root)
            had_focus = self.has_focus
            cursor_node_id = (
                self.cursor_node.data.get("id")
                if self.cursor_node and self.cursor_node.data
                else None
            )

            self.clear()
            try:
                LikedSongsBranch(self.root, self.store).build()
                PlaylistsBranch(self.root, self.store).build()
                FeaturedBranch(self.root, self.store).build()
            except Exception as e:
                self.app.log(f"Tree build error: {e}")

            self._restore_expansion(self.root, expanded_ids)
            target_id = cursor_node_id or self.store.get("last_active_node_id")
            if target_id:
                self._handle_last_active(target_id)

            if had_focus:
                self.focus()
        finally:
            self._is_refreshing = False

    def _get_expanded_node_ids(self, node: TreeNode) -> Set[str]:
        expanded = set()
        node_id = node.data.get("id") if node.data else None
        if node.is_expanded and node_id:
            expanded.add(node_id)
        for child in node.children:
            expanded.update(self._get_expanded_node_ids(child))
        return expanded

    def _restore_expansion(self, node: TreeNode, expanded_ids: Set[str]):
        node_id = node.data.get("id") if node.data else None
        if node_id and node_id in expanded_ids:
            node.expand()
        for child in node.children:
            self._restore_expansion(child, expanded_ids)

    def _handle_last_active(self, node_id):
        if not node_id:
            return
        self._select_node_by_id(self.root, node_id)

    def _select_node_by_id(self, node: TreeNode, node_id: str) -> bool:
        if node.data and node.data.get("id") == node_id:
            self.select_node(node)
            return True
        for child in node.children:
            if self._select_node_by_id(child, node_id):
                return True
        return False

    @on(Tree.NodeSelected)
    def handle_selection(self, event: Tree.NodeSelected) -> None:
        """Handles node selection (Enter/Click)."""
        data = event.node.data
        if not data:
            return

        node_type = data.get("type")

        # 1. Folders: Toggle expansion state
        if node_type in ["group", "category_root"]:
            if node_type == "category_root" and not event.node.children:
                # Lazy load category playlists
                self.load_category_playlists(
                    event.node, data.get("id"), str(event.node.label)
                )

            # Standard toggle
            event.node.toggle()
            return

        # 2. Content: Load tracks
        node_id = data.get("id")
        self.store.set("last_active_node_id", node_id, persist=True)

        if node_type == "playlist":
            self.load_playlist_tracks(node_id)
        elif node_type == "liked_songs":
            self.load_liked_songs()

    @work(exclusive=True, thread=True)
    def load_category_playlists(
        self, node: TreeNode, category_id: str, category_name: str = ""
    ):
        """Lazy loader for browse categories."""
        try:

            def _set_loading():
                node.add_leaf("Loading...", data={"type": "loading"})
                node.expand()

            self.app.call_from_thread(_set_loading)

            playlists = self.network.get_playlists_by_category(category_id)

            if not playlists and category_name:
                from src.core.utils import strip_icons

                clean_name = strip_icons(category_name)
                search_res = self.network.search(
                    query=f"{clean_name} owner:spotify", qtype="playlist", limit=20
                )
                playlists = [
                    r["data"] for r in search_res if r.get("_qtype") == "playlist"
                ]

            def _update_ui():
                node.remove_children()
                from src.core.utils import strip_icons

                if not playlists:
                    node.add_leaf("No playlists found", data={"type": "info"})
                else:
                    for pl in playlists:
                        if pl and isinstance(pl, dict):
                            name = strip_icons(pl.get("name", "Unknown Playlist"))
                            node.add_leaf(
                                name, data={"type": "playlist", "id": pl.get("id")}
                            )
                node.expand()

            self.app.call_from_thread(_update_ui)
        except Exception as e:
            if self.app:
                self.app.call_from_thread(
                    self.app.notify, f"Error: {e}", severity="error"
                )
            self.app.call_from_thread(node.remove_children)

    @work(exclusive=True, thread=True)
    def load_playlist_tracks(self, playlist_id: str):
        """Background worker for tracks."""
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            tracks = self.network.get_playlist_tracks(playlist_id)
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)
            self.app.call_from_thread(
                self.store.set,
                "last_active_context",
                f"spotify:playlist:{playlist_id}",
                persist=True,
            )

            def _focus():
                try:
                    self.app.query_one("TrackList").focus()
                except:
                    pass

            self.app.call_from_thread(_focus)
        except Exception as e:
            if self.app:
                self.app.call_from_thread(
                    self.app.notify, f"Error: {e}", severity="error"
                )
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_liked_songs(self):
        """Background worker for liked songs."""
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            tracks = self.network.get_liked_songs()
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "liked_songs", persist=True
            )

            def _focus():
                try:
                    self.app.query_one("TrackList").focus()
                except:
                    pass

            self.app.call_from_thread(_focus)
        except Exception as e:
            if self.app:
                self.app.call_from_thread(
                    self.app.notify, f"Error: {e}", severity="error"
                )
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )
