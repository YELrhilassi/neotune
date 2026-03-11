from pubsub import pub
from typing import Any, Callable


class PubSub:
    """Wrapper around pypubsub for thread-safe event distribution."""

    @staticmethod
    def subscribe(topic: str, callback: Callable) -> None:
        """
        Subscribe to a topic.
        Note: callback MUST accept keyword arguments matching published data.
        """
        pub.subscribe(callback, topic)

    @staticmethod
    def unsubscribe(topic: str, callback: Callable) -> None:
        pub.unsubscribe(callback, topic)

    @staticmethod
    def publish(topic: str, **kwargs) -> None:
        """Publish data to a topic using keyword arguments."""
        pub.sendMessage(topic, **kwargs)

    @staticmethod
    def subscribe_all(callback: Callable) -> None:
        """Subscribe to all messages. Callback receives (topic, **kwargs)."""
        # pypubsub doesn't have a direct 'subscribe_all' in the same way,
        # but we can use a listener on a base topic or pub.ALL_TOPICS
        pub.subscribe(callback, pub.ALL_TOPICS)
