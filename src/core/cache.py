import time
from typing import Any, Dict

class CacheStore:
    """A Redis-inspired in-memory cache with TTL and maximum item limits."""
    
    def __init__(self, max_size: int = 100):
        self._store: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size

    def set(self, key: str, value: Any, ttl: int = 86400):
        """Set a key with a time-to-live in seconds (default 24h)."""
        self._evict_expired()
        self._enforce_size()
        
        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }

    def get(self, key: str) -> Any:
        """Get a value by key. Returns None if not found or expired."""
        if key not in self._store:
            return None
            
        entry = self._store[key]
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None
            
        return entry["value"]

    def delete(self, key: str):
        if key in self._store:
            del self._store[key]

    def clear(self):
        self._store.clear()

    def _evict_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._store[k]

    def _enforce_size(self):
        if len(self._store) >= self.max_size:
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k]["expires_at"])
            del self._store[oldest_key]
