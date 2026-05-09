"""Tests for backend.messaging.bus."""

from __future__ import annotations

import threading
from typing import ClassVar

from backend.messaging.bus import DomainEventBus
from backend.messaging.envelope import AggregateId, make_envelope
from backend.messaging.event import (
    DomainEvent,
    StoredEvent,
    _clear_registry_for_tests,
    register_event,
)


def _stored_event() -> StoredEvent:
    @register_event
    class Toy(DomainEvent):
        event_type: ClassVar[str] = "toy_emitted"
        schema_version: ClassVar[int] = 1

    env = make_envelope(source="test")
    return StoredEvent(
        global_position=1,
        aggregate_id=AggregateId("agg_x"),
        aggregate_type="toy",
        aggregate_version=1,
        event_type="toy_emitted",
        schema_version=1,
        payload={},
        envelope=env,
        occurred_at=env.occurred_at,
    )


def setup_function() -> None:
    _clear_registry_for_tests()


def teardown_function() -> None:
    _clear_registry_for_tests()


def test_emit_calls_each_listener_once():
    bus = DomainEventBus()
    received: list[StoredEvent] = []

    bus.subscribe(received.append)
    bus.emit(_stored_event())

    assert len(received) == 1
    assert received[0].event_type == "toy_emitted"


def test_unsubscribe_stops_delivery():
    bus = DomainEventBus()
    received: list[StoredEvent] = []
    unsub = bus.subscribe(received.append)
    unsub()

    bus.emit(_stored_event())
    assert received == []


def test_listener_exception_does_not_block_others():
    bus = DomainEventBus()
    received_b: list[StoredEvent] = []

    def crashing(_e: StoredEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(crashing)
    bus.subscribe(received_b.append)
    bus.emit(_stored_event())

    assert len(received_b) == 1


def test_subscribe_is_thread_safe():
    bus = DomainEventBus()
    received: list[StoredEvent] = []
    lock = threading.Lock()

    def safe_append(e: StoredEvent) -> None:
        with lock:
            received.append(e)

    threads = [threading.Thread(target=lambda: bus.subscribe(safe_append)) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert bus.listener_count() == 20
    bus.emit(_stored_event())
    assert len(received) == 20
