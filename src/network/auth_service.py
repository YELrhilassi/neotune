"""Authentication service for Spotify OAuth."""

from typing import Optional, Any
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from src.core.logging_config import get_logger
from src.core.constants import SpotifyScopes
from src.core.debug_logger import DebugLogger

logger = get_logger("auth_service")


class AuthService:
    """Manages Spotify authentication lifecycle."""

    def __init__(self, config):
        self.config = config
        self._auth_manager: Optional[SpotifyOAuth] = None
        self._debug = DebugLogger()
        self._setup_auth()

    def _setup_auth(self) -> None:
        if not self.config.is_valid():
            return

        self._auth_manager = SpotifyOAuth(
            requests_timeout=5,
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=self.config.redirect_uri,
            scope=",".join(SpotifyScopes.SCOPES),
            open_browser=False,
        )

    def get_auth_url(self) -> str:
        if not self._auth_manager:
            self._setup_auth()
        return self._auth_manager.get_authorize_url() if self._auth_manager else ""

    def complete_login(self, response_url: str) -> Optional[spotipy.Spotify]:
        if not self._auth_manager:
            self._setup_auth()
        if not self._auth_manager:
            return None

        try:
            code = self._auth_manager.parse_response_code(response_url)
            token = self._auth_manager.get_access_token(code, as_dict=False)
            if token:
                self._debug.info("AuthService", "Login successful")

                try:
                    from src.state.store import Store

                    store = Store()
                    store.update(is_authenticated=True, api_connected=True)
                except:
                    pass

                return spotipy.Spotify(
                    auth_manager=self._auth_manager, requests_timeout=10, retries=0
                )
        except Exception as e:
            msg = f"Login failed: {e}"
            logger.error(msg)
            self._debug.error("AuthService", msg)
        return None

    def get_client(self) -> Optional[spotipy.Spotify]:
        """Get an authenticated spotipy client."""
        if not self._auth_manager:
            self._setup_auth()
        if not self._auth_manager:
            return None

        token_info = self._auth_manager.get_cached_token()
        if not token_info:
            return None

        if self._auth_manager.is_token_expired(token_info):
            try:
                self._auth_manager.refresh_access_token(token_info["refresh_token"])
            except Exception as e:
                msg = f"Token refresh failed: {e}"
                logger.error(msg)
                self._debug.error("AuthService", msg)
                return None

        return spotipy.Spotify(auth_manager=self._auth_manager, requests_timeout=10, retries=0)

    def reauthenticate(self) -> None:
        self._auth_manager = None
        self._setup_auth()
        self._debug.info("AuthService", "Re-authentication initiated")

    def get_access_token(self) -> Optional[str]:
        if not self._auth_manager:
            return None

        token_info = self._auth_manager.get_cached_token()
        if token_info:
            if self._auth_manager.is_token_expired(token_info):
                try:
                    token_info = self._auth_manager.refresh_access_token(
                        token_info["refresh_token"]
                    )
                except Exception as e:
                    self._debug.error("AuthService", f"Failed to refresh token: {e}")
                    return None
            return token_info.get("access_token")

        return None
