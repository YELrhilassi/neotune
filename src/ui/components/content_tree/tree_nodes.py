from typing import Dict, Any, List, Optional, Set
from textual.widgets.tree import TreeNode
from src.core.icons import Icons
from src.core.utils import strip_icons


class BaseBranch:
    """Base class for functional branches in the ContentTree."""

    def __init__(self, root: TreeNode, store: Any):
        self.root = root
        self.store = store

    def build(self):
        pass


class LikedSongsBranch(BaseBranch):
    """Handles the 'Liked Songs' entry at the top level."""

    def build(self):
        self.root.add_leaf(
            f"{Icons.SAVE} Liked Songs",
            data={"type": "liked_songs", "id": "liked_songs"},
        )


class PlaylistsBranch(BaseBranch):
    """Handles the user's personal playlists under 'Your Library'."""

    def build(self):
        playlists = self.store.get("playlists") or []
        if not playlists:
            return

        pl_root = self.root.add(
            f"{Icons.PLAYLIST} Your Library",
            expand=True,
            data={"type": "group", "id": "your_playlists_group"},
        )

        seen_names: Dict[str, int] = {}
        for pl in playlists:
            if not pl or not isinstance(pl, dict):
                continue

            name = strip_icons(pl.get("name", "")) or "Untitled Playlist"

            # Handle duplicates by adding a suffix or owner
            if name in seen_names:
                seen_names[name] += 1
                display_name = f"{name} ({seen_names[name]})"
            else:
                display_name = name
                seen_names[name] = 1

            pl_root.add_leaf(display_name, data={"type": "playlist", "id": pl.get("id")})


class RecentlyPlayedBranch(BaseBranch):
    """Handles the 'Recently Played' entry at the top level."""

    def build(self):
        self.root.add_leaf(
            f"{Icons.HISTORY} Recently Played",
            data={"type": "recently_played", "id": "recently_played"},
        )


class FeaturedBranch(BaseBranch):
    """Handles the requested 'Featured' structure with subtrees."""

    def build(self):
        metadata = self.store.get("browse_metadata") or {}
        categories = metadata.get("categories", [])
        featured_playlists = metadata.get("featured_playlists", [])
        featured_msg = metadata.get("featured_message", "Featured")
        user_profile = metadata.get("user_profile")
        username = user_profile.get("display_name", "You") if user_profile else "You"

        # 1. Main Featured Root
        ft_root = self.root.add(
            f"{Icons.FEATURED} {featured_msg}",
            expand=False,
            data={"type": "group", "id": "featured_group"},
        )

        special_mapped: Set[str] = set()

        # 2. Define requested subtrees
        # We'll use these to organize categories dynamically
        sections = [
            (
                "made_for_user",
                f"{Icons.ARTIST} Made For {username}",
                ["personal", username.lower()],
            ),
            ("top_mixes", f"{Icons.TRACK} Your Top Mixes", ["mix", "top mix"]),
            (
                "recommended",
                f"{Icons.RADIO} Recommended Stations",
                ["station", "discover"],
            ),
            ("made_for_you", f"{Icons.HEART} Made For You", ["made for you"]),
        ]

        # Create the subtree nodes
        subtree_nodes = {}
        for key, label, _ in sections:
            subtree_nodes[key] = ft_root.add(label, data={"type": "group", "id": f"subtree_{key}"})

        # 3. Categorize Browse Data into Subtrees
        for cat in categories:
            if not cat or not isinstance(cat, dict):
                continue
            cat_id = cat.get("id", "")
            cat_name = cat.get("name", "")
            if not cat_id or not cat_name:
                continue

            name_lower = cat_name.lower()

            target_key = None
            if "made for you" in name_lower or cat_id == "made-for-you":
                target_key = "made_for_you"
            elif "mix" in name_lower or cat_id == "top-mixes":
                target_key = "top_mixes"
            elif "station" in name_lower or "discover" in name_lower or cat_id == "discover":
                target_key = "recommended"
            # Note: Removed the user_profile based ID matching as it's unreliable and causes 404s

            if target_key:
                subtree_nodes[target_key].add(
                    strip_icons(cat_name),
                    data={"type": "category_root", "id": cat_id},
                )
                special_mapped.add(cat_id)

        # 4. Add Featured Playlists (Editor's Picks)
        # These go directly into the Featured root
        for pl in featured_playlists:
            if not pl or not isinstance(pl, dict):
                continue
            ft_root.add_leaf(
                strip_icons(pl.get("name", "Playlist")),
                data={"type": "playlist", "id": pl.get("id")},
            )

        # 5. Browse All (Remaining Categories)
        remaining_cats = [c for c in categories if c.get("id") not in special_mapped]
        if remaining_cats:
            browse_root = self.root.add(
                f"{Icons.SEARCH} Browse All",
                expand=False,
                data={"type": "group", "id": "browse_all_group"},
            )
            for cat in remaining_cats:
                browse_root.add(
                    strip_icons(cat.get("name", "Category")),
                    data={"type": "category_root", "id": cat.get("id")},
                )

        # 6. Cleanup Empty Subtrees
        for node in list(ft_root.children):
            if not node.children:
                node.remove()
