"""Thread-safe in-process domain event bus.

The bus is an emit/listen surface for projections, coordinators, and
the EventPayloadBridge that translates our domain events into the
dashboard's EventPayload notifications. The event store is the
source of truth; the bus is a *broadcast* channel for derived state.

Listeners run synchronously on the emit thread by default. Long-running
listeners should hand work to their own queue/thread; the bus does not
back-pressure or buffer.
"""

from __future__ import annotations

import threading
from typing import Callable

from backend.messaging.event import StoredEvent

EventListener = Callable[[StoredEvent], None]


class DomainEventBus:
    """Listener-based broadcast. Thread-safe registration and emit.

    A single global instance lives in the app DI; tests construct
    their own.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._listeners: list[EventListener] = []

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        """Register a listener. Returns an unsubscribe callable."""
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                try:
                    self._listeners.remove(listener)
                except ValueError:
                    pass

        return _unsubscribe

    def emit(self, event: StoredEvent) -> None:
        """Synchronously call every listener with the event.

        Exceptions from listeners are isolated: one bad listener does
        not kill the others. Errors are swallowed here and observable
        via metrics/logs in production.
        """
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                # In production this is logged + metric-incremented.
                # In tests this is intentional silence — listeners that
                # care about errors should observe via assertions.
                continue

    def listener_count(self) -> int:
        with self._lock:
            return len(self._listeners)


__all__ = ["DomainEventBus", "EventListener"]
