"""IntakeFetcher Protocol — the IO boundary for intake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.services.ingestion.intake.sources import PaperSource


class IntakeFetchError(Exception):
    """Base class for fetcher failures.

    Subclasses or callers attach `cause_kind` (a stable string) and
    `retryable` (bool). The IntakeAppService translates these into
    PaperFetchFailed events without raising further.
    """

    def __init__(self, message: str, *, cause_kind: str, retryable: bool) -> None:
        super().__init__(message)
        self.cause_kind = cause_kind
        self.retryable = retryable


@dataclass(frozen=True)
class FetchResult:
    """What every fetcher produces."""

    raw_paper_path: str
    pdf_sha256: str
    pdf_size_bytes: int


class IntakeFetcher(Protocol):
    """A source-specific fetcher. PdfPathFetcher copies a local file;
    future ArxivFetcher downloads from arXiv; future DoiFetcher
    resolves a DOI to a URL and downloads."""

    @property
    def kind(self) -> str:
        """Source kind this fetcher handles, matching `source.kind`."""

    def fetch(self, source: PaperSource, *, project_id: str) -> FetchResult:
        """Materialize the paper for `project_id`. Raises IntakeFetchError
        on failure with a stable cause_kind for metrics + a retryable flag."""


__all__ = ["FetchResult", "IntakeFetchError", "IntakeFetcher"]
