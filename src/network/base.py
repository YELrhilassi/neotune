"""Base class for Spotify API services."""

import time
import uuid
from typing import Any, Optional, Dict
import spotipy
from spotipy.exceptions import SpotifyException
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.core.cache import CacheStore

logger = get_logger("spotify_service")


class SpotifyServiceBase:
    """Base class for Spotify services with shared API call logic."""

    def __init__(self, sp: Optional[spotipy.Spotify] = None):
        self.sp = sp
        self._debug = DebugLogger()
        self._cache = CacheStore()

    def set_spotify_client(self, sp: spotipy.Spotify) -> None:
        """Update the Spotify client instance."""
        self.sp = sp

    def _safe_api_call(
        self,
        func: callable,
        *args,
        default_return: Any = None,
        track_name: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """Execute API call with error handling, tracking, and optional caching."""
        if not self.sp:
            return default_return

        endpoint = track_name or func.__name__

        # 1. Check Cache
        if cache_ttl is not None:
            cache_key = f"api:{endpoint}:{args}:{kwargs}"
            cached_val = self._cache.get(cache_key)
            if cached_val is not None:
                self._debug.debug("SpotifyService", f"Cache hit: {endpoint}")
                return cached_val

        # 2. Prepare for Tracking
        request_id = f"req_{str(uuid.uuid4())[:8]}"
        self._debug.network_start(request_id, "API", endpoint, dict(kwargs) if kwargs else None)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            # 3. Track success
            self._debug.network_end(request_id, status_code=200)
            self._debug.track_performance(endpoint, duration_ms)

            # 4. Save to Cache
            if cache_ttl is not None:
                cache_key = f"api:{endpoint}:{args}:{kwargs}"
                self._cache.set(cache_key, result, ttl=cache_ttl)

            return result
        except SpotifyException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"Spotify API error ({endpoint}): {e}")
            self._debug.network_end(
                request_id, error=str(e), status_code=getattr(e, "http_status", None)
            )
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error in API call ({endpoint}): {e}")
            self._debug.network_end(request_id, error=str(e))
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
