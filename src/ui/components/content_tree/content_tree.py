from typing import Dict, Any, List, Optional, cast, Set, TYPE_CHECKING
import threading
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from textual.binding import Binding
from textual import work, events, on
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.core.utils import strip_icons
from src.core.icons import Icons
from src.ui.components.content_tree.tree_nodes import (
    CollectionBranch,
    PlaylistsBranch,
    DiscoveryBranch,
)

if TYPE_CHECKING:
    from src.ui.terminal_renderer import TerminalRenderer


class ContentTree(Tree):
    """
    Primary navigation component using a tree structure.
    """

    def __init__(self, **kwargs):
        super().__init__("Root", **kwargs)
        self.show_root = False
        self.store = Store()  # Singleton
        self.network = Container.resolve(SpotifyNetwork)
        self._refresh_timer = None
        self._is_refreshing = False
        self._last_build_data = {}

    def on_mount(self):
        # Subscribe to Store keys for navigation updates
        self.store.subscribe("playlists", lambda val, **kw: self._reactive_refresh())
        self.store.subscribe("browse_metadata", lambda val, **kw: self._reactive_refresh())
        self.store.subscribe("special_playlists", lambda val, **kw: self._reactive_refresh())
        self.store.subscribe("loading_states", lambda val, **kw: self._handle_loading(val))
        self.refresh_tree()

    def _handle_loading(self, states):
        if states and self.app:
            new_loading = states.get("sidebar", False)
            if self.loading != new_loading:
                if threading.current_thread() is threading.main_thread():
                    self.loading = new_loading
                else:
                    self.app.call_from_thread(setattr, self, "loading", new_loading)

    def _reactive_refresh(self):
        if not self.app:
            return

        # Check if data changed to avoid flicker
        new_data = {
            "playlists": self.store.get("playlists"),
            "browse_metadata": self.store.get("browse_metadata"),
            "special_playlists": self.store.get("special_playlists"),
        }
        if new_data == self._last_build_data:
            return
        self._last_build_data = new_data

        if self._refresh_timer:
            self._refresh_timer.cancel()

        def _deferred():
            try:
                if threading.current_thread() is threading.main_thread():
                    self.refresh_tree()
                else:
                    self.app.call_from_thread(self.refresh_tree)
            except:
                pass

        self._refresh_timer = threading.Timer(1.0, _deferred)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def refresh_tree(self):
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
            CollectionBranch(self.root, self.store).build()
            PlaylistsBranch(self.root, self.store).build()
            DiscoveryBranch(self.root, self.store).build()

            self._restore_expansion(self.root, expanded_ids)
            target_id = cursor_node_id or self.store.get("last_active_node_id")
            if target_id:
                self._select_node_by_id(self.root, target_id)
            if had_focus:
                self.focus()
        except Exception as e:
            from src.core.debug_logger import DebugLogger

            DebugLogger().error("ContentTree", f"Tree build error: {e}")
        finally:
            self._is_refreshing = False

    def _get_expanded_node_ids(self, node: TreeNode) -> Set[str]:
        expanded = set()
        if node.is_expanded and node.data:
            node_id = node.data.get("id")
            if node_id:
                expanded.add(node_id)
        for child in node.children:
            expanded.update(self._get_expanded_node_ids(child))
        return expanded

    def _restore_expansion(self, node: TreeNode, expanded_ids: Set[str]):
        if node.data:
            node_id = node.data.get("id")
            if node_id in expanded_ids:
                node.expand()
        for child in node.children:
            self._restore_expansion(child, expanded_ids)

    def _select_node_by_id(self, node: TreeNode, node_id: str) -> bool:
        data = node.data
        if data and data.get("id") == node_id:
            self.select_node(node)
            return True
        for child in node.children:
            if self._select_node_by_id(child, node_id):
                return True
        return False

    @on(Tree.NodeSelected)
    def handle_selection(self, event: Tree.NodeSelected) -> None:
        node = event.node
        data = node.data
        if not data:
            return

        node_type = data.get("type")
        if node_type in ["group", "category_root"]:
            if node_type == "category_root" and not node.children:
                self.load_category_playlists(node, data.get("id"), str(node.label))
            return

        node_id = data.get("id")
        self.store.set("last_active_node_id", node_id, persist=True)

        if node_type == "playlist":
            self.load_playlist_tracks(node_id)
        elif node_type == "spotify_user_leaf":
            self.load_spotify_user_playlists_to_table(node_id)
        elif node_type == "liked_songs":
            self.load_liked_songs()
        elif node_type == "recently_played":
            self.load_recently_played()
        elif node_type == "made_for_you":
            self.load_made_for_you()
        elif node_type == "featured_hub":
            self.load_featured_hub()

    @work(exclusive=True, thread=True)
    def load_spotify_user_playlists_to_table(self, user_id: str):
        """
        Loads all playlists for a user (like 'spotify') and displays them in the main table.
        """
        import time
        import re
        import datetime

        def _render(pl_list):
            current_year = datetime.datetime.now().year

            def get_sort_key(pl):
                name = pl.get("name", "").lower()
                match = re.search(r"\b(19|20)\d{2}\b", name)
                year = int(match.group()) if match else None
                if "top" in name:
                    if year == current_year:
                        return (1, name)
                    if year is None:
                        return (2, name)
                    return (4, name)
                return (3, name)

            sorted_pls = sorted(pl_list, key=get_sort_key)
            tracks = [
                {
                    "type": "context",
                    "context_type": "playlist",
                    "uri": pl.get("uri"),
                    "name": pl.get("name"),
                    "metadata": {"artists": ""},
                }
                for pl in sorted_pls
                if pl and isinstance(pl, dict)
            ]
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)

        try:
            # 1. Update UI loading state
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )

            # 2. Check Persistent Cache (Source of Truth)
            cache_key = (
                "prefetch:spotify_playlists"
                if user_id == "spotify"
                else f"prefetch:all_user_playlists_{user_id}"
            )
            from src.core.cache import CacheStore

            cache = CacheStore(enable_disk=True)
            cached_obj = cache.get(cache_key)

            if cached_obj and isinstance(cached_obj, dict) and cached_obj.get("data"):
                _render(cached_obj["data"])
                # Return immediately if cache is fresh enough
                if time.time() - cached_obj.get("time", 0) < 86400:
                    return

            # 3. Fetch from API
            all_playlists = []
            offset = 0
            while True:
                if getattr(self.app, "_exit", False) or not self.app.is_running:
                    break

                result = self.network.discovery.get_user_playlists(user_id, limit=50, offset=offset)
                items = result.get("items", [])
                if not items:
                    break

                all_playlists.extend(items)
                _render(all_playlists)  # Incremental update

                if offset + 50 >= result.get("total", 0):
                    break
                offset += 50
                time.sleep(1.0)  # Gentle

            # 4. Save to Cache
            if all_playlists:
                cache.set(cache_key, {"time": time.time(), "data": all_playlists}, ttl=86400)

        except Exception as e:
            from src.core.debug_logger import DebugLogger

            DebugLogger().error("ContentTree", f"Failed to load Spotify user playlists: {e}")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )
            self.app.call_from_thread(
                self.store.set, "last_active_context", "spotify_playlists", persist=True
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())

    @work(exclusive=True, thread=True)
    def load_category_playlists(self, node: TreeNode, category_id: str, category_name: str = ""):
        try:
            self.app.call_from_thread(lambda: node.add_leaf("Loading...", data={"type": "loading"}))
            self.app.call_from_thread(node.expand)
            playlists = self.network.discovery.get_category_playlists(
                category_id, name_hint=category_name
            )

            def _update_ui():
                node.remove_children()
                if not playlists:
                    node.add_leaf("[dim]No playlists found[/]", data={"type": "info"})
                    return
                for pl in playlists:
                    if pl and isinstance(pl, dict):
                        node.add_leaf(
                            strip_icons(pl.get("name", "Playlist")),
                            data={"type": "playlist", "id": pl.get("id")},
                        )
                node.expand()

            self.app.call_from_thread(_update_ui)
        except:
            self.app.call_from_thread(node.remove_children)

    @work(exclusive=True, thread=True)
    def load_made_for_you(self):
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            combined = []
            seen_uris = set()
            for sp in self.store.get("special_playlists") or []:
                uri = sp.get("uri")
                if uri and uri not in seen_uris:
                    combined.append(
                        {
                            "type": "context",
                            "context_type": "playlist",
                            "uri": uri,
                            "name": sp.get("name"),
                            "metadata": {"artists": sp.get("description", "Lua Config")},
                        }
                    )
                    seen_uris.add(uri)
            mfy_playlists = self.network.discovery.get_made_for_you_playlists()
            for pl in mfy_playlists:
                if not pl:
                    continue
                uri = pl.get("uri")
                if uri and uri not in seen_uris:
                    combined.append(
                        {
                            "type": "context",
                            "context_type": "playlist",
                            "uri": uri,
                            "name": pl.get("name"),
                            "metadata": {"artists": "Spotify Mix"},
                        }
                    )
                    seen_uris.add(uri)
            self.app.call_from_thread(self.store.set, "current_tracks", combined)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "made_for_you", persist=True
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_featured_hub(self):
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            featured = self.network.discovery.get_featured_playlists()
            items = featured.get("items", [])
            tracks = [
                {
                    "type": "context",
                    "context_type": "playlist",
                    "uri": pl.get("uri"),
                    "name": pl.get("name"),
                    "metadata": {"artists": "Spotify Pick"},
                }
                for pl in items
                if pl
            ]
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "featured_hub", persist=True
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_recently_played(self):
        from src.core.debug_logger import DebugLogger

        debug = DebugLogger()
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            api_tracks = self.network.library.get_recently_played()
            from src.core.activity_service import ActivityService

            activity_svc = Container.resolve(ActivityService)
            combined = activity_svc.get_combined_history(api_tracks)
            self.app.call_from_thread(self.store.set, "current_tracks", combined)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "recently_played", persist=True
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())
        except Exception as e:
            debug.error("ContentTree", f"Failed to load recently played: {e}")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_liked_songs(self):
        from src.core.debug_logger import DebugLogger

        debug = DebugLogger()
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            tracks = self.network.library.get_liked_songs()
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)
            self.app.call_from_thread(
                self.store.set, "last_active_context", "liked_songs", persist=True
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())
        except Exception as e:
            debug.error("ContentTree", f"Failed to load liked songs: {e}")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_playlist_tracks(self, playlist_id: str):
        from src.core.debug_logger import DebugLogger

        debug = DebugLogger()
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            tracks = self.network.library.get_playlist_tracks(playlist_id)
            self.app.call_from_thread(self.store.set, "current_tracks", tracks)
            self.app.call_from_thread(
                self.store.set,
                "last_active_context",
                f"spotify:playlist:{playlist_id}",
                persist=True,
            )
            self.app.call_from_thread(lambda: self.app.query_one("TrackList").focus())
        except Exception as e:
            debug.error("ContentTree", f"Failed to load playlist: {e}")
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )
