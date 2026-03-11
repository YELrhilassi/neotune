import sys
from typing import Any, Callable

# Type ignore for pypubsub
try:
    from pubsub import pub  # type: ignore
except ImportError:
    pass


class PubSub:
    """Wrapper around pypubsub for thread-safe event distribution."""

    @staticmethod
    def subscribe(topic: Any, callback: Callable) -> None:
        """
        Subscribe to a topic.
        Note: callback MUST accept keyword arguments matching published data.
        """
        try:
            pub.subscribe(callback, topic)  # type: ignore
        except NameError:
            pass

    @staticmethod
    def unsubscribe(topic: str, callback: Callable) -> None:
        try:
            pub.unsubscribe(callback, topic)  # type: ignore
        except NameError:
            pass

    @staticmethod
    def publish(topic: str, **kwargs) -> None:
        """Publish data to a topic using keyword arguments."""
        try:
            pub.sendMessage(topic, **kwargs)  # type: ignore
        except NameError:
            pass

    @staticmethod
    def subscribe_all(callback: Callable) -> None:
        """Subscribe to all messages. Callback receives (topic, **kwargs)."""
        try:
            pub.subscribe(callback, pub.ALL_TOPICS)  # type: ignore
        except NameError:
            pass
