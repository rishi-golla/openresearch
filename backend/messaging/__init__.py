"""Messaging primitives: events, commands, envelope, idempotency, bus.

These types form the contract every aggregate, application service, and
coordinator speaks. They are intentionally infrastructure-free: an
event/command instance does not know about SQLite, listeners, or HTTP.
The event store and bus consume these types.
"""

from backend.messaging.bus import DomainEventBus, EventListener
from backend.messaging.command import Command, CommandId
from backend.messaging.envelope import (
    AggregateId,
    CausationId,
    CorrelationId,
    EventEnvelope,
    EventId,
    new_event_id,
    new_correlation_id,
)
from backend.messaging.event import (
    DomainEvent,
    StoredEvent,
    register_event,
    resolve_event_class,
)
from backend.messaging.idempotency import IdempotencyTable

__all__ = [
    "AggregateId",
    "CausationId",
    "Command",
    "CommandId",
    "CorrelationId",
    "DomainEvent",
    "DomainEventBus",
    "EventEnvelope",
    "EventId",
    "EventListener",
    "IdempotencyTable",
    "StoredEvent",
    "new_correlation_id",
    "new_event_id",
    "register_event",
    "resolve_event_class",
]
