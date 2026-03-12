from __future__ import annotations

"""Base class for Spotify API services."""

import time
import uuid
import threading
import json
from typing import Any, Optional, Callable, cast
import spotipy
from spotipy.exceptions import SpotifyException

from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.core.cache import CacheStore

logger = get_logger("spotify_service")


class ConnectivityTracker:
    """Shared state for connection health monitoring."""

    consecutive_failures = 0
    failure_threshold = 3
    lock = threading.Lock()


class SpotifyServiceBase:
    """Base class for Spotify services with shared API call logic."""

    _last_call_times: dict[str, float] = {}
    _rate_limit_until: float = 0
    _call_lock = threading.Lock()
    _health = ConnectivityTracker()

    def __init__(self, sp: spotipy.Spotify | None = None):
        self.sp = sp
        self._debug = DebugLogger()
        self._cache = CacheStore()

    @classmethod
    def _update_connectivity(cls, success: bool):
        """Update global connectivity state with dampening."""
        try:
            from src.state.store import Store

            store = Store()  # Singleton

            with cls._health.lock:
                if success:
                    cls._health.consecutive_failures = 0
                    should_mark_offline = False
                else:
                    cls._health.consecutive_failures += 1
                    should_mark_offline = (
                        cls._health.consecutive_failures >= cls._health.failure_threshold
                    )

            if success:
                store.set("api_connected", True)
                store.set("is_authenticated", True)
            elif should_mark_offline:
                store.set("api_connected", False)
        except Exception:
            pass

    def set_spotify_client(self, sp: spotipy.Spotify) -> None:
        """Update the Spotify client instance."""
        self.sp = sp

    @classmethod
    def is_rate_limited(cls) -> bool:
        """Check if we are currently in a rate limit cooldown period."""
        return time.time() < cls._rate_limit_until

    def _safe_api_call(
        self,
        func: Callable,
        *args,
        default_return: Any = None,
        track_name: str | None = None,
        cache_ttl: int | None = None,
        min_interval: float | None = 1.0,
        suppress_status_codes: list[int] | None = None,
        **kwargs,
    ) -> Any:
        if not self.sp:
            return default_return

        endpoint = track_name or func.__name__
        cache_key = ""

        if cache_ttl is not None:
            # Create a safe key from args and kwargs
            args_str = str(args)
            kwargs_str = str(sorted(kwargs.items()))
            cache_key = f"api:{endpoint}:{args_str}:{kwargs_str}"
            cached_val = self._cache.get(cache_key)
            if cached_val is not None:
                return cached_val

        # Check Global Rate Limit
        if time.time() < SpotifyServiceBase._rate_limit_until:
            return default_return

        if min_interval:
            with self._call_lock:
                now = time.time()
                last_call = self._last_call_times.get(endpoint, 0)
                if now - last_call < min_interval:
                    return default_return
                self._last_call_times[endpoint] = now

        request_id = f"req_{uuid.uuid4().hex[:8]}"
        self._debug.network_start(request_id, "API", endpoint, kwargs)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)

            # Cache the new result
            if cache_ttl is not None and cache_key:
                self._cache.set(cache_key, result, ttl=cache_ttl)

            self._debug.network_end(request_id, status_code=200, body=result)
            return result
        except spotipy.SpotifyException as se:
            status = se.http_status

            if status == 429:
                # Extract Retry-After or default to 5s
                retry_after = int(se.headers.get("Retry-After", 5))
                SpotifyServiceBase._rate_limit_until = time.time() + retry_after
                self._debug.error(
                    "Network", f"RATE LIMIT EXCEEDED (429): {se}. Retry after {retry_after}s"
                )
                self._update_connectivity(False)
                return default_return

            if status in [404, 403]:
                # Don't cache 404s/403s if they are expected occasionally
                if suppress_status_codes and status in suppress_status_codes:
                    pass  # Don't log spam
                else:
                    self._debug.error("Network", f"Spotify API error ({endpoint}): {se}")
                return default_return

            self._debug.error("Network", f"Spotify API error ({endpoint}): {se}")
            self._update_connectivity(False)
            self._debug.network_end(request_id, status_code=status, error=str(se))
            return default_return
        except Exception as e:
            self._update_connectivity(False)
            self._debug.error("Network", f"Unexpected error in API call ({endpoint}): {e}")
            self._debug.network_end(request_id, error=str(e))
            return default_return
