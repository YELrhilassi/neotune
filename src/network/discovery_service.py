"""Service for discovering new content (search, categories, featured)."""

from typing import Any, Optional, List, Dict
import spotipy
from src.core.constants import CategoryMappings
from src.network.base import SpotifyServiceBase


class DiscoveryService(SpotifyServiceBase):
    """Handles Spotify catalog search and discovery features."""

    def get_categories(self, country: Optional[str] = None) -> list[dict[str, Any]]:
        """Fetch available browse categories with validation and 404 suppression."""
        if not self.sp:
            return []

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
        """Fetch featured playlists with 404 suppression and search fallback."""
        if not self.sp:
            return {"message": "Featured", "items": []}

        result = self._safe_api_call(
            self.sp.featured_playlists,
            country=country,
            limit=20,
            track_name="featured_playlists",
            cache_ttl=600,
            min_interval=60.0,
            suppress_status_codes=[404],
        )

        if result and result.get("playlists"):
            return {
                "message": result.get("message", "Featured"),
                "items": result.get("playlists", {}).get("items", []),
            }

        # Fallback: Search for "Featured" or "Popular"
        search_res = self.search("Spotify Popular", types="playlist", limit=10)
        return {
            "message": "Popular Playlists",
            "items": [r["data"] for r in search_res if r.get("_qtype") == "playlist"],
        }

    def search(
        self, query: str, types: str = "track,playlist,album", limit: int = 50
    ) -> list[dict[str, Any]]:
        if not self.sp:
            return []

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
        self, category_id: str, country: Optional[str] = None, name_hint: str = ""
    ) -> list[dict[str, Any]]:
        """Fetch playlists for a category with robust fallbacks and 404 handling."""
        if not self.sp:
            return []

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
                min_interval=5.0,
                suppress_status_codes=[404, 400],
            )
            if res and res.get("playlists", {}).get("items"):
                items = [p for p in res["playlists"]["items"] if p]
                if items:
                    return items

        # 2. Search Fallback (personalized mixes)
        query = CategoryMappings.QUERY_MAP.get(category_id)
        if not query and (category_id.startswith("0JQ") or "mix" in name_hint.lower()):
            from src.core.utils import strip_icons

            clean_name = strip_icons(name_hint)
            if len(clean_name) > 2:
                query = f"{clean_name} owner:spotify"

        if query:
            res = self._safe_api_call(
                self.sp.search,
                q=query,
                type="playlist",
                limit=10,
                track_name="cat_search_fallback",
                cache_ttl=1800,
            )
            if res and res.get("playlists"):
                return [p for p in res["playlists"].get("items", []) if p]

        return []

    def get_made_for_you_playlists(self, country: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Discover 'Made For You' playlists by searching for standard names.
        """
        if not self.sp:
            return []

        search_terms = [
            "Made For You",
            "Daily Mix",
            "Discover Weekly",
            "Release Radar",
            "On Repeat",
        ]
        found_playlists = []
        seen_uris = set()

        for term in search_terms:
            result = self._safe_api_call(
                self.sp.search, q=term, type="playlist", limit=5, track_name="search_mfy"
            )
            if result and result.get("playlists"):
                for pl in result["playlists"].get("items", []):
                    if not pl:
                        continue
                    uri = pl.get("uri")
                    # Owner 'spotify' filter is standard for official mixes
                    if pl.get("owner", {}).get("id") == "spotify" and uri not in seen_uris:
                        found_playlists.append(pl)
                        seen_uris.add(uri)
        return found_playlists

    def get_recommendations(
        self,
        seed_tracks: Optional[list[str]] = None,
        seed_artists: Optional[list[str]] = None,
        seed_genres: Optional[list[str]] = None,
        limit: int = 50,
        market: Optional[str] = None,
        **tunables,
    ) -> list[dict[str, Any]]:
        """Fetch recommendations with local radio fallback."""
        if not self.sp:
            return []

        # 1. Attempt official endpoint
        if any([seed_tracks, seed_artists, seed_genres]):
            params = {
                "seed_tracks": seed_tracks[:5] if seed_tracks else None,
                "seed_artists": seed_artists[:5] if seed_artists else None,
                "seed_genres": seed_genres[:5] if seed_genres else None,
                "limit": limit,
                "market": market,
            }
            for k, v in tunables.items():
                if v is not None:
                    params[k] = v

            res = self._safe_api_call(
                self.sp.recommendations,
                track_name="recommendations",
                suppress_status_codes=[404, 403],
                **params,
            )
            if res and res.get("tracks"):
                return res["tracks"]

        # 2. Local reconstruction (Radio)
        artist_id = None
        if seed_artists:
            artist_id = seed_artists[0]
        elif seed_tracks:
            track = self._safe_api_call(self.sp.track, seed_tracks[0])
            if track and track.get("artists"):
                artist_id = track["artists"][0].get("id")

        if artist_id:
            # Related artists top tracks
            related = self._safe_api_call(self.sp.artist_related_artists, artist_id)
            if related and related.get("artists"):
                import random

                tracks = []
                artists = related["artists"]
                random.shuffle(artists)
                for a in artists[:10]:
                    top = self._safe_api_call(
                        self.sp.artist_top_tracks, a["id"], country=market or "US"
                    )
                    if top and top.get("tracks"):
                        tracks.extend(top["tracks"][:3])
                    if len(tracks) >= limit:
                        break
                return tracks[:limit]

        return []

    def resolve_special_context(self, uri: str) -> list[str]:
        """Resolve Stations or Ghost Playlists."""
        if not uri or not self.sp:
            return []

        if ":station:" in uri:
            parts = uri.split(":")
            seed_id = parts[-1]
            if "track" in parts:
                return [
                    t["uri"]
                    for t in self.get_recommendations(seed_tracks=[seed_id])
                    if t.get("uri")
                ]
            elif "artist" in parts:
                return [
                    t["uri"]
                    for t in self.get_recommendations(seed_artists=[seed_id])
                    if t.get("uri")
                ]

        if ":playlist:" in uri:
            try:
                res = self._safe_api_call(
                    self.sp.playlist_items,
                    uri.split(":")[-1],
                    limit=100,
                    suppress_status_codes=[404],
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
