"""PaperSource discriminated union — what the user submits.

This slice supports PdfPath only. ArxivId and DoiRef plug in later
through the same Pydantic discriminated union; the IntakeAppService
dispatches on `source.kind`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class PdfPath(BaseModel):
    """A local file path pointing to a PDF.

    `path` may be absolute or relative; the intake service resolves it
    to an absolute path before hashing for project_id derivation, so the
    same file under different relative paths produces the same project_id.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["pdf_path"] = "pdf_path"
    path: str


# Discriminated union — Pydantic picks the right class on `kind`.
PaperSource = Annotated[PdfPath, Field(discriminator="kind")]


__all__ = ["PaperSource", "PdfPath"]
