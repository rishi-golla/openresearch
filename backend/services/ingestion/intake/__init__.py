"""Paper-source intake: turns a PaperSource into a Project aggregate.

Public surface:
  - PaperSource (discriminated union; only PdfPath in this slice)
  - Project, PaperMetadata domain types
  - ProjectCreated, PaperFetched, PaperFetchFailed events
  - ProjectAggregate (state machine; no IO)
  - IntakeAppService (the IO boundary)
"""

from backend.services.ingestion.intake.aggregate import (
    InvalidStateTransition,
    ProjectAggregate,
    ProjectState,
)
from backend.services.ingestion.intake.events import (
    PaperFetched,
    PaperFetchFailed,
    ProjectCreated,
)
from backend.services.ingestion.intake.service import (
    FetchPaper,
    IntakeAppService,
    RegisterProject,
)
from backend.services.ingestion.intake.sources import PaperSource, PdfPath

__all__ = [
    "FetchPaper",
    "IntakeAppService",
    "InvalidStateTransition",
    "PaperFetchFailed",
    "PaperFetched",
    "PaperSource",
    "PdfPath",
    "ProjectAggregate",
    "ProjectCreated",
    "ProjectState",
    "RegisterProject",
]
