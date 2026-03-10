"""Service for discovering new content (search, categories, featured)."""

from typing import List, Dict, Any, Optional
from src.core.constants import CategoryMappings
from src.network.base import SpotifyServiceBase


class DiscoveryService(SpotifyServiceBase):
    """Handles Spotify catalog search and discovery features."""

    def get_categories(self, country: Optional[str] = None) -> List[Dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.categories, country=country, limit=50, track_name="categories", cache_ttl=3600
        )
        return result.get("categories", {}).get("items", []) if result else []

    def get_featured_playlists(self, country: Optional[str] = None) -> Dict[str, Any]:
        result = self._safe_api_call(
            self.sp.featured_playlists,
            country=country,
            limit=20,
            track_name="featured_playlists",
            cache_ttl=600,
        )
        return {
            "message": result.get("message", "Featured") if result else "Featured",
            "items": result.get("playlists", {}).get("items", []) if result else [],
        }

    def search(
        self, query: str, types: str = "track,playlist,album", limit: int = 50
    ) -> List[Dict[str, Any]]:
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
    ) -> List[Dict[str, Any]]:
        # multi-stage fallback logic
        for name, params in [
            ("cat_playlists", {"category_id": category_id, "country": country}),
            ("cat_playlists_no_country", {"category_id": category_id}),
        ]:
            res = self._safe_api_call(
                self.sp.category_playlists, **params, track_name=name, cache_ttl=1800
            )
            if res and res.get("playlists", {}).get("items"):
                return [p for p in res["playlists"]["items"] if p]

        # Final search fallback
        query = CategoryMappings.QUERY_MAP.get(category_id, category_id)
        if "owner:spotify" not in query:
            query = f"{query} owner:spotify"
        res = self._safe_api_call(
            self.sp.search,
            q=query,
            type="playlist",
            track_name="cat_search_fallback",
            cache_ttl=1800,
        )
        return res.get("playlists", {}).get("items", []) if res else []
