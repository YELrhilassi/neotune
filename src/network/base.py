from __future__ import annotations

"""Base class for Spotify API services."""

import time
import uuid
import threading
import json
from typing import Any, Optional, Callable
import spotipy
from spotipy.exceptions import SpotifyException
from src.core.di import Container
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
    _call_lock = threading.Lock()
    _health = ConnectivityTracker()

    def __init__(self, sp: Optional[spotipy.Spotify] = None):
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
                    should_mark_online = True
                    should_mark_offline = False
                else:
                    cls._health.consecutive_failures += 1
                    should_mark_online = False
                    should_mark_offline = (
                        cls._health.consecutive_failures >= cls._health.failure_threshold
                    )

            if success:
                store.set("api_connected", True)
                store.set("is_authenticated", True)
            elif should_mark_offline:
                store.set("api_connected", False)
        except:
            pass

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
        min_interval: Optional[float] = 1.0,
        suppress_status_codes: Optional[list[int]] = None,
        **kwargs,
    ) -> Any:
        if not self.sp:
            return default_return

        endpoint = track_name or func.__name__

        if min_interval:
            with self._call_lock:
                now = time.time()
                last_call = self._last_call_times.get(endpoint, 0)
                if now - last_call < min_interval:
                    return default_return
                self._last_call_times[endpoint] = now

        if cache_ttl is not None:
            cache_key = f"api:{endpoint}:{args}:{kwargs}"
            cached_val = self._cache.get(cache_key)
            if cached_val is not None:
                return cached_val

        request_id = f"req_{str(uuid.uuid4())[:8]}"
        self._debug.network_start(request_id, "API", endpoint, kwargs)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            self._update_connectivity(True)
            self._debug.network_end(request_id, status_code=200, size=0, body=result)
            self._debug.track_performance(endpoint, duration_ms)

            if cache_ttl is not None:
                cache_key = f"api:{endpoint}:{args}:{kwargs}"
                self._cache.set(cache_key, result, ttl=cache_ttl)

            return result
        except SpotifyException as e:
            duration_ms = (time.time() - start_time) * 1000
            status_code = getattr(e, "http_status", None)
            self._update_connectivity(False)

            should_suppress = suppress_status_codes and status_code in suppress_status_codes
            if not should_suppress:
                self._debug.error("Network", f"Spotify API error ({endpoint}): {e}")

            self._debug.network_end(request_id, error=str(e), status_code=status_code)
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._update_connectivity(False)
            self._debug.error("Network", f"Unexpected error in API call ({endpoint}): {e}")
            self._debug.network_end(request_id, error=str(e))
            self._debug.track_performance(endpoint, duration_ms)
            return default_return
