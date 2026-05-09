"""Issue #13 — ParsedPaperAggregate state machine."""

from __future__ import annotations

import pytest

from backend.services.ingestion.parser.aggregate import (
    InvalidParseTransition,
    ParsedPaperAggregate,
    ParsedPaperState,
)
from backend.services.ingestion.parser.events import (
    ParsingCompleted,
    ParsingFailed,
    ParsingStarted,
    ReferenceExtracted,
    SectionExtracted,
)
from backend.services.ingestion.parser.model import Reference, Section, section_id_for


def _agg() -> ParsedPaperAggregate:
    return ParsedPaperAggregate.empty("prj_1")


def _section(*, project_id: str = "prj_1", title: str = "Intro", text: str = "abc",
             depth: int = 1, char_offset: int = 0) -> Section:
    sid = section_id_for(project_id, depth, char_offset, title, text)
    return Section(
        id=sid,
        project_id=project_id,
        title=title,
        text=text,
        char_offset=char_offset,
        parent_id=None,
        depth=depth,
    )


def test_start_from_pending_emits_parsing_started():
    agg = _agg()
    events = list(agg.handle_start("pymupdf", "1"))
    assert len(events) == 1
    assert isinstance(events[0], ParsingStarted)
    assert events[0].parser_name == "pymupdf"


def test_start_from_parsing_raises():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    with pytest.raises(InvalidParseTransition):
        agg.handle_start("pymupdf", "1")


def test_start_from_parsed_raises():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    agg.apply(ParsingCompleted(
        project_id="prj_1",
        section_count=0,
        reference_count=0,
        figure_count=0,
        parser_name="pymupdf",
        parser_version="1",
        full_text_blob_path="/p",
        full_text_sha256="x" * 64,
    ))
    with pytest.raises(InvalidParseTransition):
        agg.handle_start("pymupdf", "1")


def test_start_from_failed_is_allowed_for_retry():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    agg.apply(ParsingFailed(
        project_id="prj_1",
        parser_name="pymupdf",
        cause_kind="oops",
        cause_message="failure",
        retryable=True,
    ))
    # FAILED -> can retry.
    events = list(agg.handle_start("pymupdf", "1"))
    assert isinstance(events[0], ParsingStarted)


def test_apply_section_extracted_increments_count():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    agg.apply(SectionExtracted(project_id="prj_1", section=_section()))
    agg.apply(SectionExtracted(project_id="prj_1", section=_section(title="Methods", char_offset=100)))
    assert agg.section_count == 2


def test_apply_reference_extracted_increments_count():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    ref = Reference(
        id="ref_x",
        project_id="prj_1",
        raw_text="Smith et al. 2017 PPO arXiv:1707.06347",
        arxiv_id="1707.06347",
        doi=None,
        title=None,
    )
    agg.apply(ReferenceExtracted(project_id="prj_1", reference=ref))
    assert agg.reference_count == 1


def test_apply_completed_advances_to_parsed():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    agg.apply(ParsingCompleted(
        project_id="prj_1",
        section_count=1,
        reference_count=0,
        figure_count=0,
        parser_name="pymupdf",
        parser_version="1",
        full_text_blob_path="/blob",
        full_text_sha256="a" * 64,
    ))
    assert agg.state is ParsedPaperState.PARSED


def test_apply_failed_advances_to_failed():
    agg = _agg()
    agg.apply(ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"))
    agg.apply(ParsingFailed(
        project_id="prj_1",
        parser_name="pymupdf",
        cause_kind="x",
        cause_message="y",
        retryable=False,
    ))
    assert agg.state is ParsedPaperState.FAILED


def test_apply_unknown_event_type_raises():
    from backend.messaging.event import DomainEvent
    from typing import ClassVar

    class Weird(DomainEvent):
        event_type: ClassVar[str] = "weird_p"
        schema_version: ClassVar[int] = 1

    with pytest.raises(TypeError):
        _agg().apply(Weird())


def test_apply_all_advances_version_per_event():
    agg = _agg()
    events = [
        ParsingStarted(project_id="prj_1", parser_name="pymupdf", parser_version="1"),
        SectionExtracted(project_id="prj_1", section=_section()),
        SectionExtracted(project_id="prj_1", section=_section(title="Methods", char_offset=50)),
        ParsingCompleted(
            project_id="prj_1",
            section_count=2,
            reference_count=0,
            figure_count=0,
            parser_name="pymupdf",
            parser_version="1",
            full_text_blob_path="/p",
            full_text_sha256="b" * 64,
        ),
    ]
    agg.apply_all(events)
    assert agg.version == 4
    assert agg.state is ParsedPaperState.PARSED
    assert agg.section_count == 2
