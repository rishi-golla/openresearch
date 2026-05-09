"""Parser Protocol + ParseError.

Implementations live in `pymupdf_parser.py` (this slice). Future
parsers (Nougat, GROBID) plug into the same Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from backend.services.ingestion.parser.model import Figure, Reference, Section


class ParseError(Exception):
    """Parser-side failure with a stable cause_kind for metric grouping."""

    def __init__(self, message: str, *, cause_kind: str, retryable: bool) -> None:
        super().__init__(message)
        self.cause_kind = cause_kind
        self.retryable = retryable


@dataclass(frozen=True)
class ParseResult:
    """Output of `Parser.parse()`. Sections are emitted in (depth, char_offset)
    order so SectionChunker downstream can produce deterministic ChunkIds."""

    sections: Sequence[Section]
    references: Sequence[Reference]
    figures: Sequence[Figure]
    full_text: str


class Parser(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...

    def parse(self, *, project_id: str, paper_path: Path) -> ParseResult:
        """Parse the PDF at `paper_path` and return structured output.

        Raises ParseError on failure; callers catch and translate to
        ParsingFailed events."""


__all__ = ["ParseError", "Parser", "ParseResult"]
