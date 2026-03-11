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
    """Handles the user's primary collection entries (Made For You, Liked, Recent)."""

    def build(self):
        # 1. Made For You (Leaf - At the very top)
        self.root.add_leaf(
            f"{Icons.HEART} Made For You",
            data={"type": "made_for_you", "id": "made_for_you_leaf"},
        )

        # 2. Liked Songs (Leaf)
        self.root.add_leaf(
            f"{Icons.SAVE} Liked Songs",
            data={"type": "liked_songs", "id": "liked_songs_leaf"},
        )

        # 3. Recently Played (Leaf)
        self.root.add_leaf(
            f"{Icons.HISTORY} Recently Played",
            data={"type": "recently_played", "id": "recently_played_leaf"},
        )


class PlaylistsBranch(BaseBranch):
    """Handles the user's personal playlists group."""

    def build(self):
        playlists = self.store.get("playlists") or []

        pl_root = self.root.add(
            f"{Icons.PLAYLIST} Your Playlists",
            expand=True,
            data={"type": "group", "id": "your_playlists_group"},
        )

        if not playlists:
            return

        seen_names: Dict[str, int] = {}
        for pl in playlists:
            if not isinstance(pl, dict):
                continue
            name = strip_icons(pl.get("name", "")) or "Untitled"
            if name in seen_names:
                seen_names[name] += 1
                display_name = f"{name} ({seen_names[name]})"
            else:
                display_name = name
                seen_names[name] = 1

            pl_root.add_leaf(display_name, data={"type": "playlist", "id": pl.get("id")})


class DiscoveryBranch(BaseBranch):
    """Handles the unified Discovery section."""

    def build(self):
        metadata = self.store.get("browse_metadata") or {}
        categories = metadata.get("categories", [])

        # Discovery Group
        disc_root = self.root.add(
            f"{Icons.SEARCH} Discovery",
            expand=True,
            data={"type": "group", "id": "discovery_group"},
        )

        # 1. Featured (Leaf)
        disc_root.add_leaf(
            f"{Icons.FEATURED} Featured",
            data={"type": "featured_hub", "id": "featured_leaf"},
        )

        # 2. Categories (Group)
        cat_root = disc_root.add(
            f"{Icons.TELESCOPE} Browse All",
            expand=False,
            data={"type": "group", "id": "browse_all_group"},
        )

        for cat in categories:
            if not isinstance(cat, dict):
                continue
            cat_id = cat.get("id")
            cat_name = cat.get("name")
            if not cat_id or not cat_name:
                continue

            name_lower = cat_name.lower()
            # Sort into 'Personalized' if algorithmic, but user wants 'Browse All' as a group
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

            # Filter algorithmic from 'Browse All' as they go to 'Made For You' leaf
            if is_algorithmic or cat_id == "made-for-you" or str(cat_id).startswith("0JQ5D"):
                continue

            cat_root.add(
                strip_icons(cat_name),
                data={"type": "category_root", "id": cat_id},
            )

        if not cat_root.children:
            try:
                cat_root.remove()
            except:
                pass
