"""Caching system with optional disk persistence."""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.constants import CacheSettings, Paths
from src.core.logging_config import get_logger

logger = get_logger("cache")


class CacheStore:
    """A Redis-inspired cache with TTL and optional disk persistence.

    Supports both in-memory and disk-based caching with automatic eviction
    of expired entries and size-based limits.
    """

    def __init__(
        self,
        max_size: int = CacheSettings.DEFAULT_MAX_SIZE,
        enable_disk: bool = False,
        disk_path: Optional[Path] = None,
    ) -> None:
        """Initialize cache store.

        Args:
            max_size: Maximum number of items to keep in memory
            enable_disk: Whether to persist cache to disk
            disk_path: Path for disk cache file (defaults to ~/.cache/spotify-tui/cache.json)
        """
        self._store: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.enable_disk = enable_disk
        self.disk_path = disk_path or (Paths.CACHE_DIR / "cache.json")

        if self.enable_disk:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load cache data from disk if available."""
        if not self.disk_path.exists():
            return

        try:
            with open(self.disk_path, "r") as f:
                data = json.load(f)
                # Filter out expired entries
                now = time.time()
                for key, entry in data.items():
                    if entry.get("expires_at", 0) > now:
                        self._store[key] = entry
            logger.debug(f"Loaded {len(self._store)} entries from disk cache")
        except Exception as e:
            logger.warning(f"Failed to load disk cache: {e}")

    def _save_to_disk(self) -> None:
        """Save current cache to disk."""
        if not self.enable_disk:
            return

        try:
            self.disk_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.disk_path, "w") as f:
                json.dump(self._store, f)
            logger.debug("Saved cache to disk")
        except Exception as e:
            logger.warning(f"Failed to save disk cache: {e}")

    def set(
        self,
        key: str,
        value: Any,
        ttl: int = CacheSettings.DEFAULT_TTL_SECONDS,
        persist: bool = True,
    ) -> None:
        """Set a key with time-to-live.

        Args:
            key: Cache key
            value: Value to store (must be JSON serializable if disk enabled)
            ttl: Time-to-live in seconds (default: 24 hours)
            persist: Whether to persist to disk immediately (if disk enabled)
        """
        self._evict_expired()
        self._enforce_size()

        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
        }

        if persist and self.enable_disk:
            self._save_to_disk()

        logger.debug(f"Cache set: {key}")

    def get(self, key: str) -> Any:
        """Get a value by key.

        Args:
            key: Cache key

        Returns:
            Stored value or None if not found/expired
        """
        if key not in self._store:
            return None

        entry = self._store[key]
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def delete(self, key: str, persist: bool = True) -> None:
        """Delete a key from cache.

        Args:
            key: Cache key to delete
            persist: Whether to persist to disk immediately (if disk enabled)
        """
        if key in self._store:
            del self._store[key]
            logger.debug(f"Cache delete: {key}")

        if persist and self.enable_disk:
            self._save_to_disk()

    def clear(self, persist: bool = True) -> None:
        """Clear all cache entries.

        Args:
            persist: Whether to persist to disk immediately (if disk enabled)
        """
        self._store.clear()
        logger.info("Cache cleared")

        if persist and self.enable_disk:
            self._save_to_disk()

    def _evict_expired(self) -> None:
        """Remove all expired entries from cache."""
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._store[k]

        if expired_keys:
            logger.debug(f"Evicted {len(expired_keys)} expired entries")

    def _enforce_size(self) -> None:
        """Enforce maximum cache size by removing oldest entries."""
        if len(self._store) >= self.max_size:
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k]["expires_at"])
            del self._store[oldest_key]
            logger.debug(f"Evicted oldest entry: {oldest_key}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "disk_enabled": self.enable_disk,
            "disk_path": str(self.disk_path) if self.enable_disk else None,
        }
