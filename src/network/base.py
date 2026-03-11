from __future__ import annotations

"""Base class for Spotify API services."""

import time
import uuid
import threading
import json
from typing import Any, Optional, Callable
import spotipy
from spotipy.exceptions import SpotifyException
from src.core.logging_config import get_logger
from src.core.debug_logger import DebugLogger
from src.core.cache import CacheStore

logger = get_logger("spotify_service")


class SpotifyServiceBase:
    """Base class for Spotify services with shared API call logic."""

    _last_call_times: dict[str, float] = {}
    _call_lock = threading.Lock()

    def __init__(self, sp: Optional[spotipy.Spotify] = None):
        self.sp = sp
        self._debug = DebugLogger()
        self._cache = CacheStore()

    def set_spotify_client(self, sp: spotipy.Spotify) -> None:
        """Update the Spotify client instance."""
        self.sp = sp

    def _safe_api_call(
        self,
        func: Callable,
        *args,
        default_return: Any = None,
        track_name: Optional[str] = None,
        cache_ttl: Optional[int] = None,
        min_interval: Optional[float] = 1.0,  # Prevent spamming the same endpoint
        suppress_status_codes: Optional[list[int]] = None,
        **kwargs,
    ) -> Any:
        """Execute API call with error handling, tracking, and optional caching.

        Args:
            func: API function to call
            *args: Positional arguments
            default_return: Value to return on failure
            track_name: Optional name for network tracking
            cache_ttl: Optional TTL in seconds for caching the result
            min_interval: Minimum time between calls to the same endpoint
            suppress_status_codes: HTTP status codes to catch without error logging
            **kwargs: Keyword arguments
        """
        if not self.sp:
            return default_return

        endpoint = track_name or func.__name__

        # Global Rate Limiting / Debouncing
        if min_interval:
            with self._call_lock:
                now = time.time()
                last_call = self._last_call_times.get(endpoint, 0)
                if now - last_call < min_interval:
                    # Silent return, no log Start to avoid spam
                    return default_return
                self._last_call_times[endpoint] = now

        # 1. Check Cache
        if cache_ttl is not None:
            cache_key = f"api:{endpoint}:{args}:{kwargs}"
            cached_val = self._cache.get(cache_key)
            if cached_val is not None:
                self._debug.debug("SpotifyService", f"Cache hit: {endpoint}")
                return cached_val

        # 2. Prepare for Tracking
        request_id = f"req_{str(uuid.uuid4())[:8]}"

        # Capture both positional and keyword arguments for debugging
        tracked_params = {}
        if args:
            tracked_params["args"] = args
        if kwargs:
            tracked_params.update(kwargs)

        self._debug.network_start(request_id, "API", endpoint, tracked_params)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            # 3. Track success
            # Capture full response snippet for debugging
            try:
                # Use a custom serializer for complex objects if needed
                res_str = json.dumps(result, indent=2, default=str)
                size = len(res_str)
                # Keep a reasonably large snippet for 'Details'
                body_snippet = (
                    result
                    if size < 5000
                    else {
                        "info": "Response too large for snippet",
                        "size": size,
                        "preview": str(result)[:500],
                    }
                )
            except:
                size = 0
                body_snippet = str(result)[:1000]

            self._debug.network_end(request_id, status_code=200, size=size, body=body_snippet)
            self._debug.track_performance(endpoint, duration_ms)

            # 4. Save to Cache
            if cache_ttl is not None:
                cache_key = f"api:{endpoint}:{args}:{kwargs}"
                self._cache.set(cache_key, result, ttl=cache_ttl)

            return result
        except SpotifyException as e:
            duration_ms = (time.time() - start_time) * 1000
            status_code = getattr(e, "http_status", None)

            # Check if we should suppress the error log
            should_suppress = suppress_status_codes and status_code in suppress_status_codes

            if not should_suppress:
                error_msg = f"Spotify API error ({endpoint}): {e}"
                logger.warning(error_msg)
                # Direct log to debug service for visibility
                self._debug.error("Network", error_msg)

            self._debug.network_end(request_id, error=str(e), status_code=status_code)
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Unexpected error in API call ({endpoint}): {e}"
            logger.error(error_msg)

            # Direct log to debug service
            self._debug.error("Network", error_msg)

            self._debug.network_end(request_id, error=str(e))
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
