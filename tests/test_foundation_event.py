"""Tests for backend.messaging.event."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import ValidationError

from backend.messaging.envelope import AggregateId, make_envelope
from backend.messaging.event import (
    DomainEvent,
    EventTypeAlreadyRegistered,
    StoredEvent,
    _clear_registry_for_tests,
    register_event,
    registered_event_types,
    resolve_event_class,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    _clear_registry_for_tests()
    yield
    _clear_registry_for_tests()


def test_register_event_records_class_under_event_type():
    @register_event
    class TestThingHappened(DomainEvent):
        event_type: ClassVar[str] = "test_thing_happened"
        schema_version: ClassVar[int] = 1
        thing_id: str

    assert resolve_event_class("test_thing_happened") is TestThingHappened
    assert "test_thing_happened" in registered_event_types()


def test_register_event_rejects_blank_event_type():
    class Bad(DomainEvent):
        event_type: ClassVar[str] = ""

    with pytest.raises(ValueError):
        register_event(Bad)


def test_register_event_rejects_collision_with_different_class():
    @register_event
    class A(DomainEvent):
        event_type: ClassVar[str] = "collide"
        schema_version: ClassVar[int] = 1

    class B(DomainEvent):
        event_type: ClassVar[str] = "collide"
        schema_version: ClassVar[int] = 1

    with pytest.raises(EventTypeAlreadyRegistered):
        register_event(B)


def test_register_event_is_idempotent_for_same_class():
    @register_event
    class Same(DomainEvent):
        event_type: ClassVar[str] = "same"
        schema_version: ClassVar[int] = 1

    # Re-registering the same class is a no-op.
    register_event(Same)
    assert resolve_event_class("same") is Same


def test_resolve_unknown_event_type_raises_keyerror():
    with pytest.raises(KeyError):
        resolve_event_class("nonexistent")


def test_domain_event_is_frozen():
    @register_event
    class Frozen(DomainEvent):
        event_type: ClassVar[str] = "frozen_event"
        schema_version: ClassVar[int] = 1
        x: int

    e = Frozen(x=1)
    with pytest.raises(ValidationError):
        e.x = 2  # type: ignore[misc]


def test_stored_event_into_validates_payload():
    @register_event
    class Demo(DomainEvent):
        event_type: ClassVar[str] = "demo_event"
        schema_version: ClassVar[int] = 1
        n: int

    env = make_envelope(source="test")
    stored = StoredEvent(
        global_position=1,
        aggregate_id=AggregateId("agg_1"),
        aggregate_type="demo",
        aggregate_version=1,
        event_type="demo_event",
        schema_version=1,
        payload={"n": 42},
        envelope=env,
        occurred_at=env.occurred_at,
    )
    typed = stored.into(Demo)
    assert isinstance(typed, Demo)
    assert typed.n == 42


def test_stored_event_into_rejects_wrong_class():
    @register_event
    class A(DomainEvent):
        event_type: ClassVar[str] = "type_a"
        schema_version: ClassVar[int] = 1

    @register_event
    class B(DomainEvent):
        event_type: ClassVar[str] = "type_b"
        schema_version: ClassVar[int] = 1

    env = make_envelope(source="test")
    stored = StoredEvent(
        global_position=1,
        aggregate_id=AggregateId("agg_1"),
        aggregate_type="x",
        aggregate_version=1,
        event_type="type_a",
        schema_version=1,
        payload={},
        envelope=env,
        occurred_at=env.occurred_at,
    )
    with pytest.raises(ValueError, match="Cannot deserialize"):
        stored.into(B)
