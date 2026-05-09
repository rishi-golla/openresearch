"""Cited[T] — the architectural keystone that makes citations
unbypassable at materialization time.

Pydantic + the `model_construct` ban on Citation already protect events
on the way INTO the store; `Cited[T]` protects derived values on the
way OUT. The four-layer chain is documented in the spec §5.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from backend.schemas.citations import Citation


class CitationMissingError(Exception):
    """Raised when constructing a Cited[T] without any citations."""


T = TypeVar("T")


@dataclass(frozen=True)
class Cited(Generic[T]):
    """A value paired with one or more citations.

    Citation invariant: empty citations raise CitationMissingError.
    Tests at the workspace boundary verify this.
    """

    value: T
    citations: tuple[Citation, ...]

    def __post_init__(self) -> None:
        if not self.citations:
            raise CitationMissingError(
                "Cited[T] requires at least one Citation. "
                "Empty citations would let an agent claim leak through "
                "the workspace boundary unsourced."
            )

    @classmethod
    def from_payload(cls, value: Any, citations: tuple[Citation, ...]) -> "Cited[Any]":
        """Convenience constructor used by projections that materialize
        events back into Cited[T]. The Pydantic event already validated
        non-emptiness; this is the third defense layer."""
        return cls(value=value, citations=citations)


__all__ = ["Cited", "CitationMissingError"]
