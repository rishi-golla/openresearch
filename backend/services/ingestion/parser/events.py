"""Parser domain events (#13)."""

from __future__ import annotations

from typing import ClassVar

from backend.messaging.event import DomainEvent, register_event
from backend.services.ingestion.parser.model import Figure, Reference, Section


@register_event
class ParsingStarted(DomainEvent):
    event_type: ClassVar[str] = "parsing_started"
    schema_version: ClassVar[int] = 1
    project_id: str
    parser_name: str
    parser_version: str


@register_event
class SectionExtracted(DomainEvent):
    event_type: ClassVar[str] = "section_extracted"
    schema_version: ClassVar[int] = 1
    project_id: str
    section: Section
    extraction_confidence: float = 1.0


@register_event
class ReferenceExtracted(DomainEvent):
    event_type: ClassVar[str] = "reference_extracted"
    schema_version: ClassVar[int] = 1
    project_id: str
    reference: Reference


@register_event
class FigureExtracted(DomainEvent):
    event_type: ClassVar[str] = "figure_extracted"
    schema_version: ClassVar[int] = 1
    project_id: str
    figure: Figure


@register_event
class ParsingCompleted(DomainEvent):
    event_type: ClassVar[str] = "parsing_completed"
    schema_version: ClassVar[int] = 1
    project_id: str
    section_count: int
    reference_count: int
    figure_count: int
    parser_name: str
    parser_version: str
    full_text_blob_path: str
    full_text_sha256: str


@register_event
class ParsingFailed(DomainEvent):
    event_type: ClassVar[str] = "parsing_failed"
    schema_version: ClassVar[int] = 1
    project_id: str
    parser_name: str
    cause_kind: str
    cause_message: str
    retryable: bool


__all__ = [
    "FigureExtracted",
    "ParsingCompleted",
    "ParsingFailed",
    "ParsingStarted",
    "ReferenceExtracted",
    "SectionExtracted",
]
