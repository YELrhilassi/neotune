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
        # 1. Made For You (Leaf - Exactly as requested, no username)
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
    """Handles the Discovery section with Featured and Browse groups."""

    def build(self):
        metadata = self.store.get("browse_metadata") or {}
        categories = metadata.get("categories", [])

        # Discovery Group (Collapsible)
        disc_root = self.root.add(
            f"{Icons.SEARCH} Discovery",
            expand=True,
            data={"type": "group", "id": "discovery_group"},
        )

        # 1. Featured (Leaf - loads picks into main area)
        disc_root.add_leaf(
            f"{Icons.STAR} Featured",
            data={"type": "featured_hub", "id": "featured_leaf"},
        )

        # 2. Browse All (Group - holds genres)
        br_root = disc_root.add(
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

            # Filter out algorithmic ones from tree as they are in the 'Made For You' leaf hub
            name_lower = cat_name.lower()
            is_algo = any(
                term in name_lower for term in ["made for you", "mix", "discover weekly", "radar"]
            )
            if is_algo or cat_id == "made-for-you" or str(cat_id).startswith("0JQ"):
                continue

            br_root.add(
                strip_icons(cat_name),
                data={"type": "category_root", "id": cat_id},
            )

        if not br_root.children:
            try:
                br_root.remove()
            except:
                pass
