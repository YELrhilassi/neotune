from typing import Dict, Any, List, Optional, Set
from textual.widgets.tree import TreeNode
from src.core.icons import Icons
from src.core.utils import strip_icons
from src.config.user_prefs import UserPreferences
from src.core.di import Container


class BaseBranch:
    """Base class for functional branches in the ContentTree."""

    def __init__(self, root: TreeNode, store: Any):
        self.root = root
        self.store = store

    def build(self):
        pass


class CollectionBranch(BaseBranch):
    """Handles the user's primary collection entries."""

    def build(self):
        # We don't use a root group for these, they stay at the very top
        self.root.add_leaf(
            f"{Icons.SAVE} Liked Songs",
            data={"type": "liked_songs", "id": "liked_songs"},
        )
        self.root.add_leaf(
            f"{Icons.HISTORY} Recently Played",
            data={"type": "recently_played", "id": "recently_played"},
        )


class PlaylistsBranch(BaseBranch):
    """Handles the user's personal playlists under 'Your Playlists'."""

    def build(self):
        playlists = self.store.get("playlists") or []
        if not playlists:
            return

        pl_root = self.root.add(
            f"{Icons.PLAYLIST} Your Playlists",
            expand=True,
            data={"type": "group", "id": "your_playlists_group"},
        )

        seen_names: Dict[str, int] = {}
        for pl in playlists:
            if not pl or not isinstance(pl, dict):
                continue

            name = strip_icons(pl.get("name", "")) or "Untitled Playlist"

            if name in seen_names:
                seen_names[name] += 1
                display_name = f"{name} ({seen_names[name]})"
            else:
                display_name = name
                seen_names[name] = 1

            pl_root.add_leaf(display_name, data={"type": "playlist", "id": pl.get("id")})


class DiscoveryBranch(BaseBranch):
    """Handles the unified Discovery section (Made For You, Featured, Browse)."""

    def build(self):
        metadata = self.store.get("browse_metadata") or {}
        categories = metadata.get("categories", [])
        featured_playlists = metadata.get("featured_playlists", [])
        user_profile = metadata.get("user_profile")
        username = user_profile.get("display_name", "You") if user_profile else "You"

        # 1. Made For You (Personalized Leaf)
        self.root.add_leaf(
            f"{Icons.HEART} Made For {username}",
            data={"type": "made_for_you", "id": "made_for_you"},
        )

        # 2. Featured (Curated Group)
        ft_root = self.root.add(
            f"{Icons.FEATURED} Featured",
            expand=False,
            data={"type": "group", "id": "featured_group"},
        )
        for pl in featured_playlists:
            if pl and isinstance(pl, dict):
                ft_root.add_leaf(
                    strip_icons(pl.get("name", "Playlist")),
                    data={"type": "playlist", "id": pl.get("id")},
                )

        # 3. Browse (Categories Group)
        br_root = self.root.add(
            f"{Icons.SEARCH} Browse All",
            expand=False,
            data={"type": "group", "id": "browse_all_group"},
        )

        for cat in categories:
            if not cat or not isinstance(cat, dict):
                continue
            cat_id = cat.get("id", "")
            cat_name = cat.get("name", "")
            if not cat_id or not cat_name:
                continue

            name_lower = cat_name.lower()
            # 1. Skip categories that are clearly personalized/algorithmic
            # These include common personalized IDs and names
            is_algorithmic = any(
                term in name_lower
                for term in [
                    "made for you",
                    "daily mix",
                    "discover weekly",
                    "release radar",
                    "mix",
                    "dj",
                    "your top",
                    "wrapped",
                ]
            )

            # Regional personalized IDs often start with 0JQ5D
            if is_algorithmic or cat_id == "made-for-you" or cat_id.startswith("0JQ5D"):
                continue

            # 2. Add regular category to Browse All
            br_root.add(
                strip_icons(cat_name),
                data={"type": "category_root", "id": cat_id},
            )

            if is_algorithmic or cat_id == "made-for-you":
                continue

            br_root.add(
                strip_icons(cat_name),
                data={"type": "category_root", "id": cat_id},
            )

        # Cleanup: remove groups only if they are completely empty
        for node in [ft_root, br_root]:
            if not node.children:
                try:
                    node.remove()
                except:
                    pass
