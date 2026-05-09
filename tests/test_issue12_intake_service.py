"""Issue #12 — IntakeAppService integration tests against SqliteEventStore.

Verifies the full path:
  RegisterProject -> deterministic project_id, ProjectCreated event in store
  FetchPaper      -> PaperFetched event with sha + path
  Retry behaviors (idempotent register, failure event leaves REGISTERED)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.eventstore.sqlite_store import SqliteEventStore
from backend.messaging.envelope import AggregateId
from backend.messaging.event import _clear_registry_for_tests
from backend.services.ingestion.intake import (
    FetchPaper,
    IntakeAppService,
    PaperFetched,
    PaperFetchFailed,
    PdfPath,
    ProjectCreated,
    ProjectState,
    RegisterProject,
)
from backend.services.ingestion.intake.fetchers.pdf_path import PdfPathFetcher
from backend.services.ingestion.intake.service import (
    UnknownProject,
    project_id_for,
)


def _re_register_intake_events() -> None:
    """Re-register intake events on the existing class objects after a
    registry clear. Reload would create new class objects; we want the
    same classes the aggregate module imported at module-load time so
    isinstance() checks still work."""
    from backend.messaging.event import register_event
    from backend.services.ingestion.intake.events import (
        PaperFetchFailed,
        PaperFetched,
        ProjectCreated,
    )

    for cls in (ProjectCreated, PaperFetched, PaperFetchFailed):
        register_event(cls)


@pytest.fixture
def store(tmp_path: Path):
    _clear_registry_for_tests()
    _re_register_intake_events()
    s = SqliteEventStore(f"sqlite:///{tmp_path}/events.db")
    yield s
    s.close()
    _clear_registry_for_tests()


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    return tmp_path / "runs"


@pytest.fixture
def good_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4\n%\xc7\xec\x8f\xa2\n... fake but plausible body ...\n%%EOF")
    return p


@pytest.fixture
def service(store, runs_dir: Path) -> IntakeAppService:
    return IntakeAppService(
        store=store,
        fetchers={"pdf_path": PdfPathFetcher(runs_root=runs_dir)},
    )


# --- Deterministic project_id ----------------------------------------------


def test_project_id_is_deterministic_for_same_path(good_pdf: Path):
    src = PdfPath(path=str(good_pdf))
    a = project_id_for(src)
    b = project_id_for(src)
    assert a == b
    assert a.startswith("prj_")
    assert len(a) == len("prj_") + 16


def test_project_id_differs_across_paths(tmp_path: Path):
    p1 = tmp_path / "a.pdf"
    p1.write_bytes(b"%PDF-")
    p2 = tmp_path / "b.pdf"
    p2.write_bytes(b"%PDF-")
    a = project_id_for(PdfPath(path=str(p1)))
    b = project_id_for(PdfPath(path=str(p2)))
    assert a != b


# --- RegisterProject -------------------------------------------------------


def test_register_project_writes_one_event(service, store, good_pdf):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    events = list(store.load(AggregateId(pid)))
    assert len(events) == 1
    assert events[0].event_type == "project_created"
    assert events[0].payload["project_id"] == pid


def test_register_is_idempotent_on_duplicate_command(service, store, good_pdf):
    src = PdfPath(path=str(good_pdf))
    pid_a = service.register_project(RegisterProject(source=src))
    pid_b = service.register_project(RegisterProject(source=src))
    assert pid_a == pid_b
    # Only one event in store — second register was a no-op.
    events = list(store.load(AggregateId(pid_a)))
    assert len(events) == 1


def test_register_state_advances_to_registered(service, good_pdf):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    assert service.get_state(pid) is ProjectState.REGISTERED


# --- FetchPaper happy path -------------------------------------------------


def test_fetch_writes_paper_fetched_event_and_copies_file(
    service, store, good_pdf, runs_dir
):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    success = service.fetch_paper(FetchPaper(project_id=pid))
    assert success is True

    events = list(store.load(AggregateId(pid)))
    assert [e.event_type for e in events] == ["project_created", "paper_fetched"]

    fetched_payload = events[1].payload
    expected = runs_dir / pid / "raw_paper.pdf"
    assert Path(fetched_payload["raw_paper_path"]) == expected.resolve()
    assert expected.exists()
    assert fetched_payload["pdf_size_bytes"] == good_pdf.stat().st_size
    assert len(fetched_payload["pdf_sha256"]) == 64


def test_fetch_advances_state_to_fetched(service, good_pdf):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    service.fetch_paper(FetchPaper(project_id=pid))
    assert service.get_state(pid) is ProjectState.FETCHED


def test_fetch_idempotent_after_success(service, store, good_pdf):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    service.fetch_paper(FetchPaper(project_id=pid))
    service.fetch_paper(FetchPaper(project_id=pid))  # no-op
    events = list(store.load(AggregateId(pid)))
    assert len(events) == 2  # still just project_created + paper_fetched


# --- FetchPaper failure paths ----------------------------------------------


def test_fetch_unknown_project_raises_unknown_project(service):
    with pytest.raises(UnknownProject):
        service.fetch_paper(FetchPaper(project_id="prj_does_not_exist"))


def test_fetch_missing_file_emits_retryable_failure(service, store, tmp_path):
    missing = tmp_path / "nope.pdf"
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(missing))))
    success = service.fetch_paper(FetchPaper(project_id=pid))
    assert success is False

    events = list(store.load(AggregateId(pid)))
    assert events[-1].event_type == "paper_fetch_failed"
    assert events[-1].payload["cause_kind"] == "file_not_found"
    assert events[-1].payload["retryable"] is True
    # State stays REGISTERED so a retry is valid.
    assert service.get_state(pid) is ProjectState.REGISTERED


def test_fetch_non_pdf_emits_non_retryable_failure(service, store, tmp_path):
    not_pdf = tmp_path / "fake.pdf"
    not_pdf.write_bytes(b"this is not a pdf")
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(not_pdf))))
    success = service.fetch_paper(FetchPaper(project_id=pid))
    assert success is False

    events = list(store.load(AggregateId(pid)))
    last = events[-1]
    assert last.event_type == "paper_fetch_failed"
    assert last.payload["cause_kind"] == "not_a_pdf"
    assert last.payload["retryable"] is False


def test_fetch_then_retry_succeeds(service, store, tmp_path):
    """File missing on first attempt; appears on disk; second attempt succeeds.
    Verifies the state machine genuinely permits retry from REGISTERED."""
    missing = tmp_path / "delayed.pdf"
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(missing))))
    assert service.fetch_paper(FetchPaper(project_id=pid)) is False

    # Now create the file and retry.
    missing.write_bytes(b"%PDF-1.4\n%body\n%%EOF")
    assert service.fetch_paper(FetchPaper(project_id=pid)) is True
    assert service.get_state(pid) is ProjectState.FETCHED

    events = list(store.load(AggregateId(pid)))
    types = [e.event_type for e in events]
    assert types == ["project_created", "paper_fetch_failed", "paper_fetched"]


# --- Replay parity ---------------------------------------------------------


def test_aggregate_replays_correctly_after_full_lifecycle(service, store, good_pdf):
    pid = service.register_project(RegisterProject(source=PdfPath(path=str(good_pdf))))
    service.fetch_paper(FetchPaper(project_id=pid))

    # Now drop the in-memory aggregate (creating a new service instance is
    # the equivalent — same store, no shared state) and re-derive state
    # purely from the event log.
    s2 = IntakeAppService(
        store=store,
        fetchers={"pdf_path": PdfPathFetcher(runs_root=Path("/tmp"))},  # not invoked
    )
    assert s2.get_state(pid) is ProjectState.FETCHED
