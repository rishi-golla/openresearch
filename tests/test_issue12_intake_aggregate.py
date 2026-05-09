"""Issue #12 — Project aggregate state machine (pure, no IO).

The aggregate validates transitions and emits events. These tests
verify every legal transition produces the expected event and every
illegal transition raises InvalidStateTransition. No event store or
fetcher is involved.
"""

from __future__ import annotations

import pytest

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
from backend.services.ingestion.intake.sources import PdfPath


def _agg() -> ProjectAggregate:
    return ProjectAggregate.empty("prj_x")


def _registered() -> ProjectAggregate:
    a = _agg()
    a.apply(ProjectCreated(project_id="prj_x", source=PdfPath(path="/p.pdf")))
    return a


# --- handle_register --------------------------------------------------------


def test_register_from_new_emits_project_created():
    agg = _agg()
    src = PdfPath(path="/some/paper.pdf")
    events = list(agg.handle_register(src))
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, ProjectCreated)
    assert ev.project_id == "prj_x"
    assert ev.source == src


def test_register_from_registered_raises():
    agg = _registered()
    with pytest.raises(InvalidStateTransition) as ei:
        agg.handle_register(PdfPath(path="/p.pdf"))
    assert ei.value.attempted == "register"
    assert ei.value.state is ProjectState.REGISTERED


def test_register_from_fetched_raises():
    agg = _registered()
    agg.apply(
        PaperFetched(
            project_id="prj_x",
            raw_paper_path="/p.pdf",
            pdf_sha256="a" * 64,
            pdf_size_bytes=10,
            fetched_via="pdf_path",
        )
    )
    with pytest.raises(InvalidStateTransition):
        agg.handle_register(PdfPath(path="/p.pdf"))


# --- handle_fetch -----------------------------------------------------------


def test_fetch_from_registered_emits_paper_fetched():
    agg = _registered()
    events = list(
        agg.handle_fetch(
            raw_paper_path="/runs/prj_x/raw_paper.pdf",
            pdf_sha256="b" * 64,
            pdf_size_bytes=1024,
            fetched_via="pdf_path",
        )
    )
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, PaperFetched)
    assert ev.pdf_size_bytes == 1024
    assert ev.fetched_via == "pdf_path"


def test_fetch_from_new_raises():
    with pytest.raises(InvalidStateTransition):
        _agg().handle_fetch(
            raw_paper_path="/p.pdf",
            pdf_sha256="x" * 64,
            pdf_size_bytes=1,
            fetched_via="pdf_path",
        )


def test_fetch_from_already_fetched_raises():
    agg = _registered()
    agg.apply(
        PaperFetched(
            project_id="prj_x",
            raw_paper_path="/p.pdf",
            pdf_sha256="a" * 64,
            pdf_size_bytes=1,
            fetched_via="pdf_path",
        )
    )
    with pytest.raises(InvalidStateTransition):
        agg.handle_fetch(
            raw_paper_path="/p.pdf",
            pdf_sha256="a" * 64,
            pdf_size_bytes=1,
            fetched_via="pdf_path",
        )


# --- handle_fetch_failure ---------------------------------------------------


def test_fetch_failure_keeps_aggregate_in_registered():
    agg = _registered()
    events = list(
        agg.handle_fetch_failure(
            cause_kind="file_not_found",
            cause_message="missing",
            retryable=True,
        )
    )
    assert len(events) == 1
    assert isinstance(events[0], PaperFetchFailed)
    agg.apply(events[0])
    # Failure does NOT advance state — retry remains valid.
    assert agg.state is ProjectState.REGISTERED


def test_fetch_failure_from_fetched_raises():
    agg = _registered()
    agg.apply(
        PaperFetched(
            project_id="prj_x",
            raw_paper_path="/p.pdf",
            pdf_sha256="a" * 64,
            pdf_size_bytes=1,
            fetched_via="pdf_path",
        )
    )
    with pytest.raises(InvalidStateTransition):
        agg.handle_fetch_failure(
            cause_kind="x", cause_message="y", retryable=False
        )


# --- apply / replay ---------------------------------------------------------


def test_apply_advances_state_and_version():
    agg = _agg()
    assert agg.version == 0
    assert agg.state is ProjectState.NEW

    src = PdfPath(path="/p.pdf")
    agg.apply(ProjectCreated(project_id="prj_x", source=src))
    assert agg.state is ProjectState.REGISTERED
    assert agg.version == 1
    assert agg.source == src

    agg.apply(
        PaperFetched(
            project_id="prj_x",
            raw_paper_path="/p.pdf",
            pdf_sha256="c" * 64,
            pdf_size_bytes=2,
            fetched_via="pdf_path",
        )
    )
    assert agg.state is ProjectState.FETCHED
    assert agg.version == 2


def test_apply_unknown_event_type_raises():
    from backend.messaging.event import DomainEvent
    from typing import ClassVar

    class WeirdEvent(DomainEvent):
        event_type: ClassVar[str] = "weird"
        schema_version: ClassVar[int] = 1

    with pytest.raises(TypeError):
        _agg().apply(WeirdEvent())


def test_apply_all_replays_in_order():
    agg = _agg()
    src = PdfPath(path="/p.pdf")
    agg.apply_all(
        [
            ProjectCreated(project_id="prj_x", source=src),
            PaperFetchFailed(
                project_id="prj_x",
                cause_kind="file_not_found",
                cause_message="missing",
                retryable=True,
            ),
            PaperFetched(
                project_id="prj_x",
                raw_paper_path="/p.pdf",
                pdf_sha256="d" * 64,
                pdf_size_bytes=3,
                fetched_via="pdf_path",
            ),
        ]
    )
    assert agg.state is ProjectState.FETCHED
    assert agg.version == 3
