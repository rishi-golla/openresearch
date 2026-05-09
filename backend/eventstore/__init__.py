"""Event store: append-only canonical record of every domain fact.

The store is the source of truth. Aggregates are loaded by replaying
their event stream; projections are derived by replaying the global
stream. Subscriptions allow long-lived consumers (coordinators,
projections, the dashboard bridge) to react in near-real-time.

This package defines Protocols only; concrete implementations
(SqliteEventStore, future Postgres / EventStoreDB) live in sibling
modules.
"""

from backend.eventstore.interface import (
    AppendError,
    AppendResult,
    ConcurrencyError,
    DuplicateEventError,
    EventStore,
    StoreCapabilities,
    Subscription,
    SubscriptionClosedError,
)

__all__ = [
    "AppendError",
    "AppendResult",
    "ConcurrencyError",
    "DuplicateEventError",
    "EventStore",
    "StoreCapabilities",
    "Subscription",
    "SubscriptionClosedError",
]
