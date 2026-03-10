"""Service for managing user library data (playlists, saved tracks)."""

from typing import Any, Optional
from src.network.base import SpotifyServiceBase


class LibraryService(SpotifyServiceBase):
    """Handles fetching and managing user-specific Spotify data."""

    def get_user_profile(self) -> Optional[dict[str, Any]]:
        return self._safe_api_call(self.sp.current_user, track_name="current_user", cache_ttl=3600)

    def get_liked_songs(self, limit: int = 50) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.current_user_saved_tracks,
            limit=limit,
            default_return={},
            track_name="liked_songs",
            cache_ttl=60,
        )
        return result.get("items", []) if result else []

    def get_playlists(self, limit: int = 50) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.current_user_playlists,
            limit=limit,
            default_return={},
            track_name="user_playlists",
            cache_ttl=300,
        )
        return result.get("items", []) if result else []

    def get_playlist_tracks(self, playlist_id: str, limit: int = 50) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.playlist_items,
            playlist_id,
            limit=limit,
            default_return={},
            track_name="playlist_items",
            cache_ttl=60,
        )
        return result.get("items", []) if result else []

    def get_album_tracks(self, album_id: str, limit: int = 50) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.album_tracks,
            album_id,
            limit=limit,
            default_return={},
            track_name="album_tracks",
            cache_ttl=3600,
        )
        return result.get("items", []) if result else []

    def get_recently_played(self, limit: int = 50) -> list[dict[str, Any]]:
        result = self._safe_api_call(
            self.sp.current_user_recently_played,
            limit=limit,
            default_return={},
            track_name="recently_played",
            cache_ttl=60,
        )
        return result.get("items", []) if result else []
