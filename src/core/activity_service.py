"""Service for tracking and managing user activity locally."""

import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from src.core.cache import CacheStore
from src.core.constants import Paths


class ActivityService:
    """Manages local history of played contexts (playlists, albums)."""

    _instance: Optional["ActivityService"] = None

    def __new__(cls) -> "ActivityService":
        if cls._instance is None:
            cls._instance = super(ActivityService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._initialized = True
        self._cache = CacheStore(enable_disk=True, disk_path=Paths.CACHE_DIR / "activity.json")
        self._history_key = "recent_contexts"
        self._max_history = 50

    def record_context_play(
        self, context_uri: str, name: str, context_type: str, metadata: Optional[dict] = None
    ):
        """Record that a context (playlist/album) was played with optional metadata."""
        if not context_uri:
            return

        history = self.get_recent_contexts()

        # Check if we already have this context with a proper name
        existing = next((item for item in history if item["uri"] == context_uri), None)

        if existing:
            # If the new name is just a placeholder and we have a real name, keep the real one
            if ":" in name and ":" not in existing["name"]:
                name = existing["name"]

            # If we don't have metadata yet but we just got some, update it
            if not existing.get("metadata") and metadata:
                existing["metadata"] = metadata

            history = [item for item in history if item["uri"] != context_uri]

        # Add to top
        history.insert(
            0,
            {
                "uri": context_uri,
                "name": name,
                "type": context_type,
                "timestamp": time.time(),
                "metadata": metadata or (existing.get("metadata") if existing else {}),
            },
        )

        # Trim
        history = history[: self._max_history]
        self._cache.set(self._history_key, history)

    def get_recent_contexts(self) -> list[dict[str, Any]]:
        """Get the list of recently played contexts."""
        return self._cache.get(self._history_key) or []

    def get_combined_history(self, api_tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Combine API track history with local context history, sorted by time."""
        local_contexts = self.get_recent_contexts()

        combined = []

        # 1. Add local contexts
        for ctx in local_contexts:
            combined.append(
                {
                    "type": "context",
                    "context_type": ctx["type"],
                    "uri": ctx["uri"],
                    "name": ctx["name"],
                    "timestamp": ctx.get("timestamp", 0),
                    "metadata": ctx.get("metadata", {}),
                }
            )

        # 2. Add API tracks and parse timestamps
        from datetime import datetime

        for item in api_tracks:
            track = item.get("track")
            if track:
                played_at = item.get("played_at", "")
                ts = 0
                try:
                    # Spotify format: 2023-10-25T12:34:56.789Z
                    dt = datetime.strptime(
                        played_at.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z"
                    )
                    ts = dt.timestamp()
                except:
                    try:
                        dt = datetime.strptime(
                            played_at.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z"
                        )
                        ts = dt.timestamp()
                    except:
                        pass

                combined.append(
                    {"type": "track", "data": track, "played_at": played_at, "timestamp": ts}
                )

        # 3. Sort by timestamp descending
        combined.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        return combined
