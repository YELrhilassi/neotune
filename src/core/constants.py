"""Application-wide constants for Spotify TUI."""

from pathlib import Path
from enum import Enum


class ThemeNames(str, Enum):
    """Available theme names."""

    CATPPUCCIN = "catppuccin"
    NORD = "nord"
    DRACULA = "dracula"
    TOKYO_NIGHT = "tokyo-night"
    DEFAULT = "default"


class AudioBackend(str, Enum):
    """Supported audio backends."""

    PULSEAUDIO = "pulseaudio"
    ALSA = "alsa"
    RODIO = "rodio"
    PIPE = "pipe"


class AudioBitrate(str, Enum):
    """Available audio bitrates."""

    LOW = "96"
    MEDIUM = "160"
    HIGH = "320"


class NavigationKeys:
    """Default navigation key bindings."""

    UP = "k"
    DOWN = "j"
    LEFT = "h"
    RIGHT = "l"
    PAGE_UP = "U"
    PAGE_DOWN = "D"


class PlayerSettings:
    """Player-related constants."""

    DEVICE_NAME = "Spotify TUI Player"
    DEFAULT_BITRATE = AudioBitrate.HIGH
    DEFAULT_BACKEND = AudioBackend.PULSEAUDIO
    DEFAULT_DEVICE = "default"
    INITIAL_VOLUME = "100"
    DEVICE_TYPE = "computer"


class ServerSettings:
    """Server configuration constants."""

    DEFAULT_PORT = 8080
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_REDIRECT_URI = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


class Paths:
    """Application paths."""

    CONFIG_DIR = Path.home() / ".config" / "spotify-tui"
    CACHE_DIR = Path.home() / ".cache" / "spotify_tui_librespot"
    STATE_FILE = CONFIG_DIR / "state.json"
    CLIENT_CONFIG_FILE = CONFIG_DIR / "client.yml"
    LIBRESPOT_LOG_FILE = CACHE_DIR / "librespot.log"
    LIBRESPOT_CACHE_DIR = CACHE_DIR
    LUA_CONFIG_DIR = Path("lua").absolute()


class CacheSettings:
    """Cache configuration."""

    DEFAULT_MAX_SIZE = 100
    DEFAULT_TTL_SECONDS = 86400  # 24 hours


class KeyringKeys:
    """Keyring service names."""

    SERVICE_NAME = "spotify_tui"
    CLIENT_ID_KEY = "client_id"
    CLIENT_SECRET_KEY = "client_secret"


class SpotifyScopes:
    """OAuth scopes required by the application."""

    SCOPES = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "playlist-read-private",
        "user-read-currently-playing",
        "user-library-read",
        "user-read-recently-played",
    ]


class ErrorMessages:
    """User-facing error messages."""

    AUTH_FAILED = "Authentication failed. Please check your credentials."
    NO_ACTIVE_DEVICE = "No active device found."
    NETWORK_ERROR = "Network error occurred. Please try again."
    PLAYBACK_ERROR = "Playback control failed."


class CategoryMappings:
    """Spotify category ID to search query mappings for fallback."""

    QUERY_MAP = {
        "made-for-you": "Mix owner:spotify",
        "top_mixes": "Top Mix owner:spotify",
        "discover": "Discover owner:spotify",
        "0JQ5DAqbMKFHOzu9Kzcc9M": "Mix owner:spotify",
        "0JQ5DAt0tbjZptfcdMSKl3": "Mix owner:spotify",
    }
