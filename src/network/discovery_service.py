"""Service for discovering new content with robust fallbacks for deprecated endpoints."""

import random
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
            suppress_status_codes=[404, 403],
        )
        if not result:
            return []

        categories = result.get("categories", {}).get("items", [])
        return [c for c in categories if c and c.get("id") and c.get("name")]

    def get_featured_playlists(self, country: Optional[str] = None) -> dict[str, Any]:
        """Fetch featured playlists with search fallback for deprecated endpoints."""
        if not self.sp:
            return {"message": "Featured", "items": []}

        # 1. Attempt official endpoint (affected by Nov 2024 changes)
        result = self._safe_api_call(
            self.sp.featured_playlists,
            country=country,
            limit=20,
            track_name="featured_playlists",
            cache_ttl=600,
            min_interval=60.0,
            suppress_status_codes=[404, 403],
        )

        if result and result.get("playlists"):
            return {
                "message": result.get("message", "Featured"),
                "items": result.get("playlists", {}).get("items", []),
            }

        # 2. Fallback: Search for curated Spotify content
        search_res = self.search("Spotify Picks", types="playlist", limit=15)
        return {
            "message": "Popular Discovery",
            "items": [r["data"] for r in search_res if r.get("_qtype") == "playlist"],
        }

    def search(
        self, query: str, types: str = "track,playlist,album,artist", limit: int = 50
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
        if "artist" in types and result.get("artists"):
            items.extend(
                [{"_qtype": "artist", "data": a} for a in result["artists"].get("items", [])]
            )
        return items

    def get_category_playlists(
        self, category_id: str, country: Optional[str] = None, name_hint: str = ""
    ) -> list[dict[str, Any]]:
        """Fetch playlists for a category with robust fallbacks for deprecated endpoints."""
        if not self.sp:
            return []

        # 1. Try official endpoint (affected by Nov 2024 changes)
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
                suppress_status_codes=[404, 403, 400],
            )
            if res and res.get("playlists", {}).get("items"):
                items = [p for p in res["playlists"]["items"] if p]
                if items:
                    return items

        # 2. Try resolving category ID as a direct playlist ID (common Spotify workaround)
        try:
            res = self._safe_api_call(
                self.sp.playlist, category_id, suppress_status_codes=[404, 403]
            )
            if res:
                return [res]
        except:
            pass

        # 3. Search Fallback (using the category name)
        query = CategoryMappings.QUERY_MAP.get(category_id)
        if not query and name_hint:
            query = f"{name_hint} owner:spotify"

        if query:
            res = self._safe_api_call(
                self.sp.search,
                q=query,
                type="playlist",
                limit=15,
                track_name="cat_search_fallback",
                cache_ttl=1800,
            )
            if res and res.get("playlists"):
                return [p for p in res["playlists"].get("items", []) if p]

        return []

    def get_made_for_you_playlists(self, country: Optional[str] = None) -> list[dict[str, Any]]:
        """Discover 'Made For You' content using search."""
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
                    # Nov 2024 note: Algorithmic playlists might be blocked here too for some users,
                    # but official mixes usually appear in search for the owner.
                    if (
                        pl.get("owner", {}).get("id") == "spotify" or "Mix" in pl.get("name", "")
                    ) and uri not in seen_uris:
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
    ) -> list[dict[str, Any]]:
        """Fetch recommendations with local Related Artists fallback (for Nov 2024 API limits)."""
        if not self.sp:
            return []

        # 1. Attempt official endpoint (might 403/404 for new apps)
        if any([seed_tracks, seed_artists, seed_genres]):
            params = {
                "seed_tracks": seed_tracks[:5] if seed_tracks else None,
                "seed_artists": seed_artists[:5] if seed_artists else None,
                "seed_genres": seed_genres[:5] if seed_genres else None,
                "limit": limit,
                "market": market,
            }
            res = self._safe_api_call(
                self.sp.recommendations,
                track_name="recommendations",
                suppress_status_codes=[404, 403],
                **params,
            )
            if res and res.get("tracks"):
                return res["tracks"]

        # 2. Local Radio Reconstruction (Related Artists -> Top Tracks)
        artist_id = None
        if seed_artists:
            artist_id = seed_artists[0]
        elif seed_tracks:
            track = self._safe_api_call(self.sp.track, seed_tracks[0])
            if track and track.get("artists"):
                artist_id = track["artists"][0].get("id")

        if artist_id:
            # Nov 2024 note: related_artists is also deprecated!
            # We must fallback to SEARCH if related artists fails.
            related = self._safe_api_call(
                self.sp.artist_related_artists, artist_id, suppress_status_codes=[404, 403]
            )

            artists_to_check = []
            if related and related.get("artists"):
                artists_to_check = related["artists"]
            else:
                # Fallback: Search for similar artists or just use the seed artist
                search_res = self.search(f"artist:{artist_id}", types="artist", limit=5)
                artists_to_check = [r["data"] for r in search_res if r.get("_qtype") == "artist"]

            if artists_to_check:
                tracks = []
                random.shuffle(artists_to_check)
                for a in artists_to_check[:8]:
                    top = self._safe_api_call(
                        self.sp.artist_top_tracks, a["id"], country=market or "US"
                    )
                    if top and top.get("tracks"):
                        tracks.extend(top["tracks"][:3])
                    if len(tracks) >= limit:
                        break
                return tracks[:limit]

        # 3. Final Search-based Radio
        search_query = "Recommended"
        if seed_tracks:
            track = self._safe_api_call(self.sp.track, seed_tracks[0])
            if track:
                search_query = f"{track['name']} radio"

        search_res = self.search(search_query, types="track", limit=limit)
        return [r["data"] for r in search_res if r.get("_qtype") == "track"]

    def resolve_special_context(self, uri: str) -> list[str]:
        """Resolve Stations or Algorithmic Playlists into track URIs."""
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
        return []
