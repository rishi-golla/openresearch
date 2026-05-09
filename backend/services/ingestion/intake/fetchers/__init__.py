"""IntakeFetcher adapters by PaperSource kind.

Each fetcher takes one PaperSource variant and produces the file
artifacts the aggregate records: `raw_paper_path`, `pdf_sha256`,
`pdf_size_bytes`. Fetchers are the only place file IO happens
inside intake.
"""

from backend.services.ingestion.intake.fetchers.interface import (
    FetchResult,
    IntakeFetcher,
    IntakeFetchError,
)
from backend.services.ingestion.intake.fetchers.pdf_path import PdfPathFetcher

__all__ = [
    "FetchResult",
    "IntakeFetchError",
    "IntakeFetcher",
    "PdfPathFetcher",
]
