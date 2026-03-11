from typing import Any, Callable, Dict, Generic, TypeVar, Optional
from src.state.pubsub import PubSub

T = TypeVar("T")


class BaseStore(Generic[T]):
    """Base class for feature-specific reactive stores."""

    def __init__(self, topic: str, initial_state: T):
        self._topic = topic
        self._state = initial_state
        self._pubsub = PubSub()

    @property
    def state(self) -> T:
        return self._state

    def get(self) -> T:
        return self._state

    def set(self, new_state: T) -> None:
        """Update the entire state and publish."""
        if self._state != new_state:
            self._state = new_state
            self.notify()

    def update(self, **kwargs) -> None:
        """Update specific fields of the state (if state is a dict)."""
        if not isinstance(self._state, dict):
            raise TypeError("update() can only be used if state is a dictionary")

        changed = False
        for k, v in kwargs.items():
            # For complex objects like lists or dicts, we always assume changed or do deep comparison
            # to be safe for reactivity.
            if isinstance(v, (list, dict)):
                self._state[k] = v
                changed = True
            elif self._state.get(k) != v:
                self._state[k] = v
                changed = True

        if changed:
            self.notify()

    def subscribe(self, callback: Callable[[T], None]) -> None:
        """Subscribe to state changes. Executes callback immediately with current state."""
        self._pubsub.subscribe(self._topic, callback)
        callback(self._state)

    def notify(self) -> None:
        """Force a notification to all subscribers."""
        self._pubsub.publish(self._topic, self._state)
