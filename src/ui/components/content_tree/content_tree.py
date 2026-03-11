from typing import Dict, Any, List, Optional, cast, Set, TYPE_CHECKING
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from textual.binding import Binding
from textual import work, events, on
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.ui.components.content_tree.tree_nodes import (
    CollectionBranch,
    PlaylistsBranch,
    DiscoveryBranch,
)

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class ContentTree(Tree):
    """
    The primary navigation component, organized into isolated functional branches.
    Uses centralized state management to reactively update its structure.
    """

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
        self.store.subscribe("special_playlists", self._reactive_refresh)
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
                CollectionBranch(self.root, self.store).build()
                PlaylistsBranch(self.root, self.store).build()
                DiscoveryBranch(self.root, self.store).build()
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
        node = event.node
        data = node.data
        if not data:
            return

        node_type = data.get("type")
        from src.core.debug_logger import DebugLogger

        DebugLogger().debug("Sidebar", f"Selected node: {node_type} ({data.get('id')})")

        # 1. Groups & Categories: Toggle expansion
        if node_type in ["group", "category_root"]:
            if node_type == "category_root" and not node.children:
                # Lazy load category playlists
                self.load_category_playlists(node, data.get("id"), str(node.label))

            if node.is_expanded:
                node.collapse()
            else:
                node.expand()
            return

        # 2. Content: Load tracks/views
        node_id = data.get("id")
        self.store.set("last_active_node_id", node_id, persist=True)

        if node_type == "playlist":
            self.load_playlist_tracks(node_id)
        elif node_type == "liked_songs":
            self.load_liked_songs()
        elif node_type == "recently_played":
            self.load_recently_played()
        elif node_type == "made_for_you":
            self.load_made_for_you()

    @work(exclusive=True, thread=True)
    def load_category_playlists(self, node: TreeNode, category_id: str, category_name: str = ""):
        """Lazy loader for browse categories with automatic filtering of unresponsive items."""
        try:

            def _set_loading():
                node.add_leaf("Loading...", data={"type": "loading"})
                node.expand()

            self.app.call_from_thread(_set_loading)

            # Try to get playlists
            playlists = self.network.get_playlists_by_category(category_id)

            # If browse failed but we have a name, try a generic search as a last resort
            if not playlists and category_name:
                from src.core.utils import strip_icons

                clean_name = strip_icons(category_name)
                # Filter out generic 'Mixes' or ID-looking names for search
                if len(clean_name) > 2 and not clean_name.startswith("0JQ"):
                    search_res = self.network.search(
                        query=f"{clean_name} owner:spotify", qtype="playlist", limit=10
                    )
                    playlists = [r["data"] for r in search_res if r.get("_qtype") == "playlist"]

            def _update_ui():
                if not playlists:
                    # Filter unresponsive: remove node if it fails to load content
                    try:
                        node.remove()
                        if self.has_focus:
                            self.app.notify(
                                f"Filtered unresponsive category: {category_name}",
                                severity="warning",
                            )
                    except:
                        pass
                    return

                node.remove_children()
                from src.core.utils import strip_icons

                for pl in playlists:
                    if pl and isinstance(pl, dict):
                        name = strip_icons(pl.get("name", "Unknown Playlist"))
                        node.add_leaf(name, data={"type": "playlist", "id": pl.get("id")})
                node.expand()

            self.app.call_from_thread(_update_ui)
        except Exception as e:
            if self.app:
                self.app.call_from_thread(
                    self.app.notify, f"Error loading category: {e}", severity="error"
                )
            self.app.call_from_thread(node.remove_children)

    @work(exclusive=True, thread=True)
    def load_made_for_you(self):
        """Background worker for 'Made For You' content."""
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )

            combined = []
            seen_uris = set()

            # 1. Add Special Playlists from Lua Config
            from src.config.user_prefs import UserPreferences

            try:
                prefs = Container.resolve(UserPreferences)
                if prefs and prefs.special_playlists:
                    for pl in prefs.special_playlists:
                        if not pl or not isinstance(pl, dict):
                            continue
                        uri = pl.get("uri")
                        if uri and uri not in seen_uris:
                            combined.append(
                                {
                                    "type": "context",
                                    "context_type": "playlist",
                                    "uri": uri,
                                    "name": pl.get("name", "Special Playlist"),
                                    "metadata": {
                                        "artists": pl.get("description", "User Configured Mix")
                                    },
                                }
                            )
                            seen_uris.add(uri)
            except:
                pass

            # 2. Search for standard 'Made For You' playlists
            mfy_playlists = self.network.discovery.get_made_for_you_playlists()
            for pl in mfy_playlists:
                uri = pl.get("uri")
                if uri and uri not in seen_uris:
                    combined.append(
                        {
                            "type": "context",
                            "context_type": "playlist",
                            "uri": uri,
                            "name": pl.get("name"),
                            "metadata": {
                                "artists": f"by {pl.get('owner', {}).get('display_name', 'Spotify')}"
                            },
                        }
                    )
                    seen_uris.add(uri)

            # 3. Add Algorithmic Categories from Spotify Browse
            metadata = self.store.get("browse_metadata") or {}
            categories = metadata.get("categories", [])
            for cat in categories:
                name_lower = cat.get("name", "").lower()
                cat_id = cat.get("id")
                is_algorithmic = any(
                    term in name_lower
                    for term in [
                        "made for you",
                        "daily mix",
                        "discover weekly",
                        "release radar",
                        "mix",
                        "dj",
                    ]
                )
                if is_algorithmic or cat_id == "made-for-you" or str(cat_id).startswith("0JQ5D"):
                    uri = f"spotify:category:{cat_id}"
                    if uri not in seen_uris:
                        combined.append(
                            {
                                "type": "context",
                                "context_type": "category",
                                "uri": uri,
                                "id": cat_id,
                                "name": cat.get("name"),
                                "metadata": {"artists": "Spotify Algorithmic Content"},
                            }
                        )
                        seen_uris.add(uri)

            self.app.call_from_thread(self.store.set, "current_tracks", combined)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "made_for_you", persist=True
            )

            def _focus():
                try:
                    self.app.query_one("TrackList").focus()
                except:
                    pass

            self.app.call_from_thread(_focus)

        except Exception as e:
            if self.app:
                self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_recently_played(self):
        """Background worker for recently played tracks and contexts."""
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )

            # 1. Fetch from Spotify API (last tracks)
            api_tracks = self.network.get_recently_played()

            # 2. Fetch from local ActivityService (last playlists/albums)
            from src.core.activity_service import ActivityService

            activity_svc = Container.resolve(ActivityService)

            # 3. Combine them
            combined = activity_svc.get_combined_history(api_tracks)

            self.app.call_from_thread(self.store.set, "current_tracks", combined)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "recently_played", persist=True
            )

            def _focus():
                try:
                    self.app.query_one("TrackList").focus()
                except:
                    pass

            self.app.call_from_thread(_focus)
        except Exception as e:
            if self.app:
                self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
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
                self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

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
                self.app.call_from_thread(self.app.notify, f"Error: {e}", severity="error")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )
