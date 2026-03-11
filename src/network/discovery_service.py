"""Service for discovering new content (search, categories, featured)."""

from typing import Any, Optional, List, Dict
import spotipy
from src.core.constants import CategoryMappings
from src.network.base import SpotifyServiceBase


class DiscoveryService(SpotifyServiceBase):
    """Handles Spotify catalog search and discovery features."""

    def get_categories(self, country: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch available browse categories with validation and 404 suppression."""
        result = self._safe_api_call(
            self.sp.categories,
            country=country,
            limit=50,
            track_name="categories",
            cache_ttl=3600,
            min_interval=300.0,
            suppress_status_codes=[404],
        )
        if not result:
            return []

        categories = result.get("categories", {}).get("items", [])
        return [c for c in categories if c and c.get("id") and c.get("name")]

    def get_featured_playlists(self, country: Optional[str] = None) -> dict[str, Any]:
        """Fetch featured playlists with 404 suppression."""
        result = self._safe_api_call(
            self.sp.featured_playlists,
            country=country,
            limit=20,
            track_name="featured_playlists",
            cache_ttl=600,
            min_interval=60.0,
            suppress_status_codes=[404],
        )
        return {
            "message": result.get("message", "Featured") if result else "Featured",
            "items": result.get("playlists", {}).get("items", []) if result else [],
        }

    def search(
        self, query: str, types: str = "track,playlist,album", limit: int = 50
    ) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.search, q=query, type=types, limit=limit, track_name="search", cache_ttl=60
        )
        if not result:
            return []

        items = []
        if "track" in types and result.get("tracks"):
            items.extend(
                [{"_qtype": "track", "data": t} for t in result["tracks"].get("items", [])]
            )
        if "album" in types and result.get("albums"):
            items.extend(
                [{"_qtype": "album", "data": a} for a in result["albums"].get("items", [])]
            )
        if "playlist" in types and result.get("playlists"):
            items.extend(
                [{"_qtype": "playlist", "data": p} for p in result["playlists"].get("items", [])]
            )
        return items

    def get_category_playlists(
        self, category_id: str, country: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch playlists for a category with robust fallbacks and 404 handling."""
        # 1. Try official category_playlists endpoint
        for name, params in [
            ("cat_playlists", {"category_id": category_id, "country": country}),
            ("cat_playlists_no_country", {"category_id": category_id}),
        ]:
            res = self._safe_api_call(
                self.sp.category_playlists,
                **params,
                track_name=name,
                cache_ttl=1800,
                min_interval=10.0,
                suppress_status_codes=[404],
            )
            if res and res.get("playlists", {}).get("items"):
                items = [p for p in res["playlists"]["items"] if p]
                if items:
                    return items

        # 2. Search fallback
        query = CategoryMappings.QUERY_MAP.get(category_id)
        if query:
            res = self._safe_api_call(
                self.sp.search,
                q=query,
                type="playlist",
                track_name="cat_search_fallback",
                cache_ttl=1800,
            )
            return res.get("playlists", {}).get("items", []) if res else []

        return []

    def get_recommendations(
        self, seed_tracks: list[str] = None, seed_artists: list[str] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch recommendations based on seeds (reconstructs 'Radio')."""
        # Ensure we have at least one seed
        if not seed_tracks and not seed_artists:
            return []

        result = self._safe_api_call(
            self.sp.recommendations,
            seed_tracks=seed_tracks,
            seed_artists=seed_artists,
            limit=limit,
            track_name="recommendations",
            cache_ttl=300,
        )
        return result.get("tracks", []) if result else []

    def resolve_special_context(self, uri: str) -> list[str]:
        """Try to resolve a non-standard URI into a list of playable track URIs."""
        if not uri or not self.sp:
            return []

        # 1. Handle Stations (Radio)
        if ":station:" in uri:
            parts = uri.split(":")
            # Logic: station:track:ID or station:artist:ID
            seed_id = parts[-1]
            if "track" in parts:
                tracks = self.get_recommendations(seed_tracks=[seed_id])
            elif "artist" in parts:
                tracks = self.get_recommendations(seed_artists=[seed_id])
            else:
                return []
            return [t["uri"] for t in tracks if t.get("uri")]

        # 2. Handle "Ghost" Playlists (Daily Mixes, Discover Weekly)
        if ":playlist:" in uri:
            playlist_id = uri.split(":")[-1]
            # Attempt A: Fetch items directly (sometimes metadata 404s but items work)
            try:
                res = self._safe_api_call(
                    self.sp.playlist_items,
                    playlist_id,
                    limit=100,
                    track_name="resolve_ghost_items",
                    suppress_status_codes=[404, 403],
                )
                if res and res.get("items"):
                    return [
                        i["track"]["uri"]
                        for i in res["items"]
                        if i.get("track") and i["track"].get("uri")
                    ]
            except:
                pass

            # Attempt B: Contextual Search Fallback (using Activity History)
            from src.core.activity_service import ActivityService
            from src.core.di import Container as DIContainer

            try:
                activity = DIContainer.resolve(ActivityService)
                history = activity.get_recent_contexts()
                match = next((item for item in history if item["uri"] == uri), None)
                if match and match.get("name") and ":" not in match["name"]:
                    # We have a real name from a previous successful session!
                    search_res = self.search(
                        f"{match['name']} owner:spotify", types="playlist", limit=1
                    )
                    if search_res and search_res[0].get("_qtype") == "playlist":
                        new_id = search_res[0]["data"].get("id")
                        res = self._safe_api_call(
                            self.sp.playlist_items, new_id, limit=50, suppress_status_codes=[404]
                        )
                        if res and res.get("items"):
                            return [
                                i["track"]["uri"]
                                for i in res["items"]
                                if i.get("track") and i["track"].get("uri")
                            ]
            except:
                pass

        return []
