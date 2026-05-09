"""ParsedPaperAggregate — pure state machine (no IO)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from backend.messaging.event import DomainEvent
from backend.services.ingestion.parser.events import (
    FigureExtracted,
    ParsingCompleted,
    ParsingFailed,
    ParsingStarted,
    ReferenceExtracted,
    SectionExtracted,
)


class ParsedPaperState(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class InvalidParseTransition(Exception):
    def __init__(self, state: ParsedPaperState, attempted: str) -> None:
        super().__init__(
            f"Invalid command {attempted!r} for ParsedPaperAggregate in "
            f"state {state.value!r}"
        )
        self.state = state
        self.attempted = attempted


@dataclass
class ParsedPaperAggregate:
    project_id: str = ""
    state: ParsedPaperState = ParsedPaperState.PENDING
    parser_name: str = ""
    parser_version: str = ""
    section_count: int = 0
    reference_count: int = 0
    figure_count: int = 0
    version: int = 0

    @classmethod
    def empty(cls, project_id: str) -> "ParsedPaperAggregate":
        return cls(project_id=project_id, state=ParsedPaperState.PENDING, version=0)

    def handle_start(
        self, parser_name: str, parser_version: str
    ) -> Sequence[DomainEvent]:
        if self.state is ParsedPaperState.PARSING:
            raise InvalidParseTransition(self.state, "start")
        if self.state is ParsedPaperState.PARSED:
            raise InvalidParseTransition(self.state, "start")
        # PENDING or FAILED -> can start (retry from FAILED)
        return [
            ParsingStarted(
                project_id=self.project_id,
                parser_name=parser_name,
                parser_version=parser_version,
            )
        ]

    def apply(self, event: DomainEvent) -> None:
        if isinstance(event, ParsingStarted):
            self.state = ParsedPaperState.PARSING
            self.parser_name = event.parser_name
            self.parser_version = event.parser_version
        elif isinstance(event, SectionExtracted):
            self.section_count += 1
        elif isinstance(event, ReferenceExtracted):
            self.reference_count += 1
        elif isinstance(event, FigureExtracted):
            self.figure_count += 1
        elif isinstance(event, ParsingCompleted):
            self.state = ParsedPaperState.PARSED
        elif isinstance(event, ParsingFailed):
            self.state = ParsedPaperState.FAILED
        else:
            raise TypeError(
                f"ParsedPaperAggregate cannot apply event of type "
                f"{type(event).__name__}"
            )
        self.version += 1

    def apply_all(self, events: Sequence[DomainEvent]) -> None:
        for ev in events:
            self.apply(ev)


__all__ = [
    "InvalidParseTransition",
    "ParsedPaperAggregate",
    "ParsedPaperState",
]
