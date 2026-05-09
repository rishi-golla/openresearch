"""Domain event base class + the registry that maps event_type -> Pydantic class.

Subclasses set a class-level `event_type` and `schema_version`. The
registry is populated by `@register_event` so the event store can
look up the correct Pydantic class to validate any payload it loads
back from disk (catching a hand-rolled-dict backdoor — spec §5.6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from backend.messaging.envelope import (
    AggregateId,
    EventEnvelope,
    EventId,
)


class DomainEvent(BaseModel):
    """Base class for every domain event in our system.

    Subclasses MUST set:
      - event_type: ClassVar[str]   - e.g. "project_created"
      - schema_version: ClassVar[int] - 1 on first introduction; bump
        when payload shape changes (paired with an upcaster registration)

    Subclasses MUST be frozen (model_config frozen=True). Domain events
    are immutable facts.
    """

    model_config = ConfigDict(frozen=True)

    # Subclasses override.
    event_type: ClassVar[str] = ""
    schema_version: ClassVar[int] = 1


class StoredEvent(BaseModel):
    """An event as it exists in the event store: payload + envelope + position info.

    Yielded by EventStore.load() / load_global() / Subscription.
    """

    model_config = ConfigDict(frozen=True)

    global_position: int
    aggregate_id: AggregateId
    aggregate_type: str
    aggregate_version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    """Validated against the registered DomainEvent subclass on load."""
    envelope: EventEnvelope
    occurred_at: datetime

    def into(self, cls: type[DomainEvent]) -> DomainEvent:
        """Return the payload deserialized into a typed DomainEvent.

        Re-validates via Pydantic — empty-citation backdoors etc. raise here.
        """
        if cls.event_type != self.event_type:
            raise ValueError(
                f"Cannot deserialize event_type={self.event_type!r} into "
                f"{cls.__name__} (event_type={cls.event_type!r})"
            )
        return cls.model_validate(self.payload)


# --- Registry --------------------------------------------------------------


_REGISTRY: dict[str, type[DomainEvent]] = {}


class EventTypeAlreadyRegistered(Exception):
    """Raised when two classes claim the same `event_type`."""


def register_event(cls: type[DomainEvent]) -> type[DomainEvent]:
    """Decorator: register a DomainEvent subclass by its event_type.

    Used by the event store to look up validators on load. Idempotent
    when the same class is re-registered (helpful in test reloads);
    raises if a *different* class claims an existing type.

    Example:
        @register_event
        class ProjectCreated(DomainEvent):
            event_type: ClassVar[str] = "project_created"
            schema_version: ClassVar[int] = 1
            project_id: str
            source: dict
    """
    if not cls.event_type:
        raise ValueError(
            f"{cls.__name__} must set a non-empty `event_type` class attribute"
        )
    existing = _REGISTRY.get(cls.event_type)
    if existing is not None and existing is not cls:
        raise EventTypeAlreadyRegistered(
            f"event_type={cls.event_type!r} already registered to "
            f"{existing.__module__}.{existing.__name__}; cannot reassign to "
            f"{cls.__module__}.{cls.__name__}"
        )
    _REGISTRY[cls.event_type] = cls
    return cls


def resolve_event_class(event_type: str) -> type[DomainEvent]:
    """Look up the registered DomainEvent subclass for an event_type.

    Raises KeyError if unknown — indicating an event in the store that
    no Python class can decode (an upcaster gap or a renamed type).
    """
    try:
        return _REGISTRY[event_type]
    except KeyError as exc:
        raise KeyError(
            f"No DomainEvent class registered for event_type={event_type!r}. "
            f"Either register it or add an upcaster/rename rule."
        ) from exc


def registered_event_types() -> list[str]:
    """Sorted list of currently-registered event types (for diagnostics)."""
    return sorted(_REGISTRY.keys())


def _clear_registry_for_tests() -> None:
    """Test-only helper to reset the registry between test cases."""
    _REGISTRY.clear()


__all__ = [
    "DomainEvent",
    "EventTypeAlreadyRegistered",
    "StoredEvent",
    "register_event",
    "registered_event_types",
    "resolve_event_class",
]
