"""A small, thread-safe, in-process publish/subscribe event bus.

Design goals (per the runtime architecture doc):

- The audio callback thread must never block. ``publish`` therefore only
  ever appends to per-topic subscriber lists under a short-held lock and
  invokes callbacks synchronously *on the calling thread* — it performs no
  I/O and no unbounded work itself. Subscribers that need to hop onto the
  Qt UI thread are responsible for doing so (see ``QtBridge`` below), so the
  bus itself stays UI-framework-agnostic and unit-testable without Qt.
- Subscribing/unsubscribing is safe to call from any thread at any time,
  including from inside a callback that is itself being invoked.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable, DefaultDict, List

from pianotutor.services.event_types import Topic

logger = logging.getLogger(__name__)

Subscriber = Callable[[Any], None]


class EventBus:
    """Synchronous, thread-safe publish/subscribe bus keyed by ``Topic``."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: DefaultDict[Topic, List[Subscriber]] = defaultdict(list)

    def subscribe(self, topic: Topic, callback: Subscriber) -> Callable[[], None]:
        """Register ``callback`` for ``topic``.

        Returns an ``unsubscribe`` callable for convenient cleanup, e.g.::

            unsub = bus.subscribe(Topic.NOTE_DETECTED, on_note)
            ...
            unsub()
        """
        with self._lock:
            self._subscribers[topic].append(callback)

        def _unsubscribe() -> None:
            self.unsubscribe(topic, callback)

        return _unsubscribe

    def unsubscribe(self, topic: Topic, callback: Subscriber) -> None:
        with self._lock:
            subs = self._subscribers.get(topic)
            if not subs:
                return
            try:
                subs.remove(callback)
            except ValueError:
                pass

    def publish(self, topic: Topic, payload: Any = None) -> None:
        """Invoke all subscribers for ``topic`` with ``payload``.

        Subscriber lists are copied under the lock, then invoked outside of
        it, so a subscriber can safely subscribe/unsubscribe from within its
        own callback without deadlocking.
        """
        with self._lock:
            subs = list(self._subscribers.get(topic, ()))

        for callback in subs:
            try:
                callback(payload)
            except Exception:  # noqa: BLE001 - one bad subscriber must not break others
                logger.exception("Unhandled exception in subscriber for topic %s", topic)

    def clear(self, topic: Topic | None = None) -> None:
        """Remove all subscribers, optionally scoped to a single topic."""
        with self._lock:
            if topic is None:
                self._subscribers.clear()
            else:
                self._subscribers.pop(topic, None)
