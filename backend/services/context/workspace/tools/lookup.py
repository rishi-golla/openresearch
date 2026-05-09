"""LookupTool — exact source lookup against the SourcesProjection.

Per Codex feedback (2026-05-09) the citation produced here uses the
chunk text as the `quote` (not the locator) so it's evidence-grade.
The locator goes in `Citation.locator` as it should.
"""

from __future__ import annotations

from typing import Any

from backend.schemas.citations import Citation
from backend.services.context.indexer.projections import SourcesProjection
from backend.services.context.workspace.model import Cited
from backend.services.context.workspace.tools.interface import WorkspaceToolError


_QUOTE_TRUNCATE = 240


class LookupTool:
    """Exact lookup of a SourceRef by source_id.

    Returns Cited[dict] where the dict is the SourceRef payload and the
    citation carries the first chunk's text (truncated) as evidence."""

    name = "lookup"

    def __init__(self, projection: SourcesProjection) -> None:
        self._proj = projection

    def call(self, *, workspace_id: str, source_id: str) -> Cited[dict[str, Any]]:
        src = self._proj.get_source(source_id)
        if src is None:
            raise WorkspaceToolError(f"Unknown source_id={source_id!r}")

        # Pull the first chunk for the source — its text is the
        # evidence-grade quote. If the source has no chunks (e.g., a
        # reference-kind source), fall back to a structural quote.
        chunks = self._proj.chunks_for_source(source_id)
        if chunks:
            chunk = chunks[0]
            quote = chunk.text[:_QUOTE_TRUNCATE]
            chunk_id: str | None = chunk.id
        else:
            quote = f"<source: {src.locator} (no chunked text)>"
            chunk_id = None

        citation = Citation(
            source_id=src.id,
            chunk_id=chunk_id,
            quote=quote,
            locator=src.locator,
            confidence=1.0,
        )
        return Cited(value=src.model_dump(), citations=(citation,))


__all__ = ["LookupTool"]
