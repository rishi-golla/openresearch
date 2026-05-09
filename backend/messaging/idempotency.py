"""Bounded command-idempotency table.

Spec §4.6 / §8.2: every command application service consults this
table before performing IO. A duplicate command_id returns the
previously recorded result event ids without re-executing.

Bounded retention prevents unbounded growth: rows expire after
`default_retention`. A periodic cleanup job purges expired rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from backend.messaging.command import CommandId
from backend.messaging.envelope import AggregateId, EventId
from backend.persistence.database import Database


_DDL = """
CREATE TABLE IF NOT EXISTS event_store_command_idempotency (
    aggregate_id TEXT NOT NULL,
    command_id TEXT NOT NULL,
    result_event_ids_json TEXT NOT NULL,
    handled_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (aggregate_id, command_id)
);
CREATE INDEX IF NOT EXISTS idx_event_store_idempotency_expires
    ON event_store_command_idempotency(expires_at);
"""


class IdempotencyTable:
    """Stores `(aggregate_id, command_id) -> [event_id, ...]` with bounded retention."""

    def __init__(
        self,
        db: Database,
        default_retention: timedelta = timedelta(days=30),
    ) -> None:
        self._db = db
        self._retention = default_retention
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._db.connection.executescript(_DDL)
        self._db.connection.commit()

    def lookup(
        self,
        aggregate_id: AggregateId,
        command_id: CommandId,
    ) -> tuple[EventId, ...] | None:
        """Return previously recorded result event ids for this command, or None."""
        row = self._db.connection.execute(
            """
            SELECT result_event_ids_json, expires_at
            FROM event_store_command_idempotency
            WHERE aggregate_id = ? AND command_id = ?
            """,
            (aggregate_id, command_id),
        ).fetchone()
        if row is None:
            return None
        # Lazily ignore expired rows (cleanup job removes them durably).
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            return None
        ids = json.loads(row["result_event_ids_json"])
        return tuple(EventId(s) for s in ids)

    def record(
        self,
        aggregate_id: AggregateId,
        command_id: CommandId,
        result_event_ids: Iterable[EventId],
    ) -> None:
        """Record a command's result event ids. Caller is responsible for
        executing this in the same transaction as the corresponding event
        store append (see EventStore.append usage)."""
        now = datetime.now(timezone.utc)
        expires = now + self._retention
        self._db.connection.execute(
            """
            INSERT OR REPLACE INTO event_store_command_idempotency
                (aggregate_id, command_id, result_event_ids_json, handled_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                aggregate_id,
                command_id,
                json.dumps(list(result_event_ids)),
                now.isoformat(),
                expires.isoformat(),
            ),
        )
        # No commit here — commit is the caller's responsibility so this
        # write joins their atomic block.

    def purge_expired(self) -> int:
        """Delete expired rows. Returns the count purged."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cur = self._db.connection.execute(
            "DELETE FROM event_store_command_idempotency WHERE expires_at < ?",
            (now_iso,),
        )
        self._db.connection.commit()
        return cur.rowcount or 0


__all__ = ["IdempotencyTable"]
