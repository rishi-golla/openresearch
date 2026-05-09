"""Intake domain events.

The Project aggregate's lifecycle:
  NEW -ProjectCreated-> REGISTERED -PaperFetched-> FETCHED
                                    \\
                                     PaperFetchFailed (stays REGISTERED for retry)

Events are immutable Pydantic models registered by (event_type,
schema_version). The `frozen=True` config + register_event decorator
both come from the foundation in backend.messaging.event.
"""

from __future__ import annotations

from typing import ClassVar

from backend.messaging.event import DomainEvent, register_event
from backend.services.ingestion.intake.sources import PaperSource


@register_event
class ProjectCreated(DomainEvent):
    """A new project has been registered under a deterministic project_id.

    project_id is content-addressed against the source so re-registering
    the same source is idempotent.
    """

    event_type: ClassVar[str] = "project_created"
    schema_version: ClassVar[int] = 1

    project_id: str
    source: PaperSource


@register_event
class PaperFetched(DomainEvent):
    """The paper file has been successfully copied/fetched and is on disk."""

    event_type: ClassVar[str] = "paper_fetched"
    schema_version: ClassVar[int] = 1

    project_id: str
    raw_paper_path: str
    pdf_sha256: str
    pdf_size_bytes: int
    fetched_via: str
    """Adapter name (e.g. 'pdf_path'). Tells future services which fetcher
    handled this paper without re-deriving from the source."""


@register_event
class PaperFetchFailed(DomainEvent):
    """A fetch attempt failed. The aggregate stays in REGISTERED so a
    retry command can re-attempt.

    `cause_kind` is a stable enum-style string for metric grouping;
    `cause_message` is human text. `retryable=True` means the failure
    looks transient (e.g., a missing file that may appear later);
    `False` means the failure is structural (corrupted PDF, unsupported
    source kind).
    """

    event_type: ClassVar[str] = "paper_fetch_failed"
    schema_version: ClassVar[int] = 1

    project_id: str
    cause_kind: str
    cause_message: str
    retryable: bool


__all__ = ["PaperFetchFailed", "PaperFetched", "ProjectCreated"]
