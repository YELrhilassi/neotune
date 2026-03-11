from typing import Any, Callable, Dict, List, Set, Optional
import threading


class PubSub:
    """A thread-safe, centralized PubSub system (Singleton)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(PubSub, cls).__new__(cls)
                cls._instance._subscribers = {}
                cls._instance._global_subscribers = set()
            return cls._instance

    def __init__(self):
        # Initialized via __new__ if singleton, but for safety:
        if not hasattr(self, "_subscribers"):
            self._subscribers = {}
            self._global_subscribers = set()
            self._lock = threading.Lock()

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = set()
            self._subscribers[topic].add(callback)

    def subscribe_all(self, callback: Callable[[str, Any], None]) -> None:
        with self._lock:
            self._global_subscribers.add(callback)

    def unsubscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic].discard(callback)

    def publish(self, topic: str, data: Any) -> None:
        with self._lock:
            subs = list(self._subscribers.get(topic, []))
            globals = list(self._global_subscribers)

        for callback in subs:
            try:
                callback(data)
            except:
                pass

        for callback in globals:
            try:
                callback(topic, data)
            except:
                pass
