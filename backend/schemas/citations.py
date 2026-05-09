"""Citation primitives shared by the workspace and any agent claim.

Defined locally for now; proposed upstream to #8 in a follow-up PR.
Import from this module across the codebase so the move to #8 is one
import change.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """A single piece of evidence backing an agent claim.

    `source_id` and (optional) `chunk_id` resolve to entries in the
    SourcesProjection / chunks store. `quote` is the exact evidence text
    the agent grounded its claim in. `locator` is a human-readable pointer
    rendered by the dashboard ("PPO §3.2", "github.com/openai/baselines/README.md:42").
    `confidence` is 0..1; default 1.0 means "directly cited from primary source".
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    chunk_id: str | None = None
    quote: str
    locator: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# Pydantic-validated typed alias: every list[Citation] in an event payload
# must be non-empty. Enforced at construction; bypasses (model_construct)
# are caught by EventStore.append() re-validation (spec §5.6).
NonEmptyCitations = Annotated[tuple[Citation, ...], Field(min_length=1)]


__all__ = ["Citation", "NonEmptyCitations"]
