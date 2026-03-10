"""Facade for modular Spotify services."""

from typing import Optional, List, Dict, Any
import spotipy
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.network.auth_service import AuthService
from src.network.playback_service import PlaybackService
from src.network.library_service import LibraryService
from src.network.discovery_service import DiscoveryService

logger = get_logger("spotify_network")


class SpotifyNetwork:
    """Facade delegating to specialized Spotify services."""

    def __init__(self, config):
        self.config = config
        self.auth = AuthService(config)
        self.playback = PlaybackService()
        self.library = LibraryService()
        self.discovery = DiscoveryService()

        self.sp: Optional[spotipy.Spotify] = None
        self._sync_client()

    def _sync_client(self) -> None:
        """Ensure all services share the current authenticated client."""
        self.sp = self.auth.get_client()
        if self.sp:
            self.playback.set_spotify_client(self.sp)
            self.library.set_spotify_client(self.sp)
            self.discovery.set_spotify_client(self.sp)

    # --- Auth Delegation ---
    def get_auth_url(self) -> str:
        return self.auth.get_auth_url()

    def complete_login(self, response_url: str) -> bool:
        client = self.auth.complete_login(response_url)
        if client:
            self.sp = client
            self._sync_client()
            return True
        return False

    def is_authenticated(self) -> bool:
        is_auth = self.auth.get_client() is not None
        if is_auth and not self.sp:
            self._sync_client()
        return is_auth

    def reauthenticate(self) -> None:
        self.auth.reauthenticate()
        self.sp = None
        self._sync_client()

    def get_access_token(self) -> Optional[str]:
        return self.auth.get_access_token()

    # --- Playback Delegation ---
    def get_current_playback(self, force: bool = False) -> Optional[Dict[str, Any]]:
        return self.playback.get_current_playback(force=force)

    def get_devices(self) -> Dict[str, Any]:
        return {"devices": self.playback.get_devices()}

    def play_track(self, uri, device_id=None, context_uri=None, offset=None):
        self.playback.play_track(uri, device_id, context_uri, offset)

    def transfer_playback(self, device_id, force_play=True):
        self.playback.transfer(device_id, force_play)

    def toggle_play_pause(self) -> bool:
        playback = self.get_current_playback(force=True)
        if playback and playback.get("is_playing"):
            self.playback.pause()
            return False
        else:
            self.playback.resume()
            return True

    def toggle_shuffle(self) -> bool:
        playback = self.get_current_playback()
        if playback:
            new_state = not playback.get("shuffle_state", False)
            self.playback.toggle_shuffle(new_state)
            return new_state
        return False

    def cycle_repeat(self) -> str:
        states = ["off", "context", "track"]
        playback = self.get_current_playback()
        current = playback.get("repeat_state", "off") if playback else "off"
        next_state = states[(states.index(current) + 1) % 3]
        self.playback.set_repeat(next_state)
        return next_state

    def next_track(self) -> None:
        self.playback.next()

    def prev_track(self) -> None:
        self.playback.previous()

    # --- Library Delegation ---
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        return self.library.get_user_profile()

    def get_liked_songs(self, limit=50) -> List[Dict[str, Any]]:
        return self.library.get_liked_songs(limit)

    def get_playlists(self, limit=50) -> List[Dict[str, Any]]:
        return self.library.get_playlists(limit)

    def get_playlist_tracks(self, pid, limit=50) -> List[Dict[str, Any]]:
        return self.library.get_playlist_tracks(pid, limit)

    def get_album_tracks(self, aid, limit=50) -> List[Dict[str, Any]]:
        return self.library.get_album_tracks(aid, limit)

    def get_recently_played(self, limit=50) -> List[Dict[str, Any]]:
        return self.library.get_recently_played(limit)

    # --- Discovery Delegation ---
    def get_browse_metadata(self) -> Dict[str, Any]:
        # Combines multiple calls for the sidebar
        profile = self.get_user_profile()
        country = profile.get("country") if profile else None

        categories = self.discovery.get_categories(country)
        featured = self.discovery.get_featured_playlists(country)

        return {
            "categories": categories,
            "featured_message": featured["message"],
            "featured_playlists": featured["items"],
            "user_profile": profile,
        }

    def get_playlists_by_category(self, cid, limit=50) -> List[Dict[str, Any]]:
        profile = self.get_user_profile()
        return self.discovery.get_category_playlists(
            cid, profile.get("country") if profile else None
        )

    def search(self, query, qtype="track,playlist,album", limit=50) -> List[Dict[str, Any]]:
        return self.discovery.search(query, qtype, limit)
