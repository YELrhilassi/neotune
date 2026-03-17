import threading
from typing import Any

from src.state.store import Store


class VirtualQueueManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VirtualQueueManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.store = Store()
        # Ensure 'skipped_uris' is part of the persistent keys in Store if possible, or handle it manually here
        # For our purposes, we can just use the store which handles state persistence.

        # Load skipped_uris from store or init empty set
        loaded_skips = self.store.get("skipped_uris", [])
        self.skipped_uris: set[str] = set(loaded_skips)

        self._initialized = True

    def mark_skipped(self, uri: str):
        """Add a track URI to the skipped list and persist it."""
        if not uri:
            return
        self.skipped_uris.add(uri)
        self._save()

    def unmark_skipped(self, uri: str):
        """Remove a track URI from the skipped list and persist it."""
        if uri in self.skipped_uris:
            self.skipped_uris.remove(uri)
            self._save()

    def is_skipped(self, uri: str) -> bool:
        """Check if a track is marked to be skipped."""
        return uri in self.skipped_uris

    def _save(self):
        """Save the skipped URIs to the persistent store."""
        self.store.set("skipped_uris", list(self.skipped_uris), persist=True)

    def filter_queue(self, queue_data: dict[str, Any]) -> dict[str, Any]:
        """Filter out skipped tracks from the real queue."""
        if not queue_data:
            return {}

        filtered_queue = []
        for track in queue_data.get("queue", []):
            if track and track.get("uri") not in self.skipped_uris:
                filtered_queue.append(track)

        return {
            "currently_playing": queue_data.get("currently_playing"),
            "queue": filtered_queue
        }
