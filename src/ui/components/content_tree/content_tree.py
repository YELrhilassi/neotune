from typing import Dict, Any, List, Optional, cast, Set, TYPE_CHECKING
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from textual.binding import Binding
from textual import work, events, on
from src.core.di import Container
from src.state.store import Store
from src.network.spotify_network import SpotifyNetwork
from src.core.utils import strip_icons
from src.ui.components.content_tree.tree_nodes import (
    CollectionBranch,
    MadeForYouBranch,
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

        self._refresh_timer = threading.Timer(1.5, _deferred)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def refresh_tree(self):
        if not self.app or self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            expanded_ids = self._get_expanded_node_ids(self.root)
            had_focus = self.has_focus
            cursor_node_id = None
            if self.cursor_node and self.cursor_node.data:
                cursor_node_id = self.cursor_node.data.get("id")

            self.clear()
            CollectionBranch(self.root, self.store).build()
            MadeForYouBranch(self.root, self.store).build()
            PlaylistsBranch(self.root, self.store).build()
            DiscoveryBranch(self.root, self.store).build()

            self._restore_expansion(self.root, expanded_ids)
            target_id = cursor_node_id or self.store.get("last_active_node_id")
            if target_id:
                self._select_node_by_id(self.root, target_id)
            if had_focus:
                self.focus()
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
        if node_type in ["group", "category_root"]:
            if node_type == "category_root" and not node.children:
                self.load_category_playlists(node, data.get("id"), str(node.label))
            node.toggle()
            return

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
        elif node_type == "featured_hub":
            self.load_featured_hub()

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
                    node_id = str(node.data.get("id", "")) if node.data else ""
                    is_personal = node_id.startswith("0JQ") or "mix" in category_name.lower()
                    if is_personal:
                        node.add_leaf("[dim]Unavailable right now[/]", data={"type": "info"})
                    else:
                        try:
                            node.remove()
                        except:
                            pass
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
        """Loads Lua and Spotify personalized mixes into the main track list area."""
        try:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": True}
            )
            combined = []
            seen_uris = set()

            profile = self.network.library.get_user_profile()
            country = profile.get("country") if profile else None

            # 1. Lua Special Playlists
            from src.config.user_prefs import UserPreferences

            try:
                prefs = Container.resolve(UserPreferences)
                for pl in prefs.special_playlists:
                    if not isinstance(pl, dict):
                        continue
                    uri = pl.get("uri")
                    if uri and uri not in seen_uris:
                        combined.append(
                            {
                                "type": "context",
                                "context_type": "playlist",
                                "uri": uri,
                                "name": pl.get("name", "Special"),
                                "metadata": {"artists": pl.get("description", "User Mix")},
                            }
                        )
                        seen_uris.add(uri)
            except:
                pass

            # 2. Spotify Search Fallback for 'Made For You'
            mfy_playlists = self.network.discovery.get_made_for_you_playlists(country=country)
            for pl in mfy_playlists:
                uri = pl.get("uri")
                if uri and uri not in seen_uris:
                    combined.append(
                        {
                            "type": "context",
                            "context_type": "playlist",
                            "uri": uri,
                            "name": pl.get("name", "Mix"),
                            "metadata": {
                                "artists": f"by {pl.get('owner', {}).get('display_name', 'Spotify')}"
                            },
                        }
                    )
                    seen_uris.add(uri)

            # 3. Personalized Category Extraction
            metadata = self.store.get("browse_metadata") or {}
            categories = metadata.get("categories", [])
            for cat in categories:
                name_lower = cat.get("name", "").lower()
                cat_id = cat.get("id")
                is_algo = any(
                    t in name_lower
                    for t in ["made for you", "daily mix", "discover weekly", "radar", "mix", "dj"]
                )
                if is_algo or str(cat_id).startswith("0JQ5D"):
                    pls = self.network.discovery.get_category_playlists(
                        cat_id, country=country, name_hint=cat.get("name")
                    )
                    for p in pls:
                        uri = p.get("uri")
                        if uri and uri not in seen_uris:
                            combined.append(
                                {
                                    "type": "context",
                                    "context_type": "playlist",
                                    "uri": uri,
                                    "name": p.get("name", "Mix"),
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
            tracks = []
            for pl in items:
                tracks.append(
                    {
                        "type": "context",
                        "context_type": "playlist",
                        "uri": pl.get("uri"),
                        "name": pl.get("name"),
                        "metadata": {
                            "artists": f"by {pl.get('owner', {}).get('display_name', 'Spotify')}"
                        },
                    }
                )
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
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_liked_songs(self):
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
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )

    @work(exclusive=True, thread=True)
    def load_playlist_tracks(self, playlist_id: str):
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
        finally:
            current_l = self.store.get("loading_states") or {}
            self.app.call_from_thread(
                self.store.set, "loading_states", {**current_l, "track_list": False}
            )
