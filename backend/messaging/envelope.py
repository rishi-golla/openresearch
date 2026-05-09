"""Event envelope and ID newtypes.

The envelope carries the metadata every stored event needs:
- A unique event_id for idempotent appends.
- A correlation_id pinned to a single user-facing request, propagated
  through every event the request causes.
- A causation_id pointing at the parent event in the chain (or None
  for the root command).
- The wall-clock time the event occurred (UTC).
- The producing module ("ingestion.intake.service", "context.workspace.service").
- A schema_version so upcasters can migrate older events forward.

Newtype IDs are typed strings — `mypy --strict` distinguishes a
ProjectId from a TaskId at compile time even though both are strings
at runtime.
"""

from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from typing import NewType

from pydantic import BaseModel, ConfigDict, Field

EventId = NewType("EventId", str)
CorrelationId = NewType("CorrelationId", str)
CausationId = NewType("CausationId", str)
AggregateId = NewType("AggregateId", str)


# --- ID generation ---------------------------------------------------------
#
# We use Crockford-base32 ULIDs for monotonic, lexicographically sortable
# IDs without an external dependency. Implemented inline to avoid pulling
# in `ulid-py` until later phases.

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """Produce a 26-character Crockford-base32 ULID.

    First 10 chars: 48-bit timestamp (ms since epoch).
    Last 16 chars: 80 random bits.
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    ts_chars = []
    for _ in range(10):
        ts_chars.append(_CROCKFORD[ts_ms & 0x1F])
        ts_ms >>= 5
    ts_str = "".join(reversed(ts_chars))

    rnd = int.from_bytes(secrets.token_bytes(10), "big")
    rnd_chars = []
    for _ in range(16):
        rnd_chars.append(_CROCKFORD[rnd & 0x1F])
        rnd >>= 5
    rnd_str = "".join(reversed(rnd_chars))

    return ts_str + rnd_str


def new_event_id() -> EventId:
    return EventId(f"evt_{_ulid()}")


def new_correlation_id() -> CorrelationId:
    return CorrelationId(f"cor_{_ulid()}")


def new_causation_id(from_event: EventId) -> CausationId:
    """Causation IDs are event IDs of the parent event in the chain."""
    return CausationId(from_event)


# --- Envelope --------------------------------------------------------------


class EventEnvelope(BaseModel):
    """Metadata that wraps every domain event in storage.

    The envelope and the payload are stored separately in the event store:
    payload_json holds the domain event, metadata_json holds a serialized
    EventEnvelope. This keeps payload schemas pure.
    """

    model_config = ConfigDict(frozen=True)

    event_id: EventId
    correlation_id: CorrelationId
    causation_id: CausationId | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    """Producing module path, e.g. 'ingestion.intake.service'."""
    schema_version: int = 1


def make_envelope(
    *,
    source: str,
    correlation_id: CorrelationId | None = None,
    causation_id: CausationId | None = None,
    schema_version: int = 1,
) -> EventEnvelope:
    """Convenience constructor: fills in event_id and occurred_at."""
    return EventEnvelope(
        event_id=new_event_id(),
        correlation_id=correlation_id or new_correlation_id(),
        causation_id=causation_id,
        source=source,
        schema_version=schema_version,
        occurred_at=datetime.now(timezone.utc),
    )


__all__ = [
    "AggregateId",
    "CausationId",
    "CorrelationId",
    "EventEnvelope",
    "EventId",
    "make_envelope",
    "new_causation_id",
    "new_correlation_id",
    "new_event_id",
]
