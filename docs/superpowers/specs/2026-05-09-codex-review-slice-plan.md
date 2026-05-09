# Codex Review — Vertical Slice Plan (2026-05-09)

Reviewer: Codex (rescue agent)
Reviewing: `docs/superpowers/plans/2026-05-09-ingestion-context-vertical-slice.md`
Status: Captured inline; sandbox blocked Codex's filesystem write to `/tmp`,
so the content is preserved here verbatim for the record.

---

## 1. Slice Scope

Not too narrow for the stated demo: the plan targets "a local PDF" to "a queryable Workspace with citation-bearing variables" with `ingest`/`inspect` CLI output (plan L13-20). The ship risk is width: five commits span four aggregates, events, app services, adapters/tools, projections, CLI, and tests — roughly ~2000 LOC source + ~1500 LOC tests (plan L299-306).

## 2. Commit Independence

They are sequentially mergeable, not truly independently mergeable. The hidden chains:
- Commit 2 depends on Commit 1: parsing requires `ProjectAggregate` state `FETCHED` (plan L144-146)
- Commit 3 depends on Commit 2: indexing requires `ParsedPaperAggregate` state `PARSED` (plan L198-202)
- Commit 3 → Commit 4: workspace build requires `IndexAggregate` state `INDEXED` (plan L231-234)
- Commit 2 → Commit 4: `claim_map` is preloaded "from parsed sections" (plan L235)
- Commits 1-4 → Commit 5: smoke test runs all four services in sequence (plan L254-256)

## 3. Aggregate Purity

No violation apparent. The plan states aggregates "validate transitions and emit events" and "never call IO" (plan L103-104); `PdfPathFetcher.fetch()` is "the only IO" (plan L114); parser invocation lives in `ParserAppService` (plan L144-150). The spec concurs: app services own IO, aggregates only validate transitions (spec L105-111, L594-620).

## 4. Idempotent Re-Ingest

Partial, with a real edge case. `project_id` is `sha256(source_kind + source_locator)` — not content-addressed by PDF bytes (plan L112). `pdf_sha256` is recorded separately in `PaperFetched` (plan L108). ID stability depends on stable locator, stable parser output, stable source ordering, and stable spans/text. The plan itself flags nondeterministic source ordering as a risk (plan L295). If source ordering varies between runs, `SourceRef.id` and `Chunk.id` hashes will diverge.

## 5. Citation Invariant

Not fully addressed. The plan says `claim_map` is loaded from parsed sections (plan L231-236) and tests should verify citations "referencing real source_ids" (plan L239-242). `LookupTool` sets both `quote` and `locator` to `src.locator` (plan L227-230), which is a locator string, not an evidence excerpt. The spec validates non-empty, resolvable `source_id`s (spec L827-841) but not whether `quote` is meaningful. These are placeholder-grade citations, not evidence-grade ones.

## 6. PyMuPDF Section Detection Robustness

Deliberately weak by design: numbered headings + known names, with a fallback to "single section" if nothing matches (plan L137-140). `SectionChunker` makes one chunk per section (plan L196), so a failed heading match collapses the entire paper into one full-document chunk. The plan rates this as medium risk (plan L293) but does not propose a mitigation or fallback chunking strategy.

## 7. Smoke Test Determinism

`parse_duration_ms` will not break the ID-equality assertion if the smoke test only compares `SourceId`s and `ChunkId`s (plan L254-257, L273-274). However, `ParsingCompleted` includes `parse_duration_ms` (plan L130-135; spec L646-655), and the spec's full replay target is byte-identical event stores (spec L971-980, L1196). Whether `parse_duration_ms` is normalized or excluded from the determinism check is not addressed in the plan or spec. This will surface as a gap when replay determinism is implemented properly.

## 8. Out-of-Scope Gaps

A `DiscoveryAdapter` is not required for the plan's demo, which is local PDF to workspace (plan L13-22). Discovery is explicitly deferred (plan L7-8, L278-282). The gap appears against full spec acceptance: spec acceptance criteria include arXiv ingestion and discovery-adapter failure paths (spec L1190-1192). The demo is credible without it; spec closure is not.

## 9. Silent Spec Skips

- **§3.5 Coordinators**: Explicitly deferred — the plan says "Coordinator-free" (plan L26-27) and "No coordinators in this slice" (plan L263-264). Not silent, but real debt given spec §3.5 and §8.10 require durable inbox/outbox and parser subprocess isolation (spec L153-200, L1026-1035).
- **§8.10 Security / parser isolation**: Labeled follow-up (plan L142, L287). Subprocess isolation is required by spec but skipped silently in the out-of-scope list.
- **§8.5 Replay Determinism**: The quietest skip. The plan only tests stable IDs (plan L273-274); the spec requires byte-identical replay (spec L971-980, L1196). This gap is not listed in the out-of-scope section (plan L278-288).

## Overall Verdict

This is a credible local-PDF demo slice, not a spec-complete implementation. The plan is honest about discovery, coordinator, and parser-isolation deferrals (plan L278-288), and delivers a visible CLI result covering intake through workspace (plan L13-22). The main engineering risks are: (1) "independently mergeable" overstates the dependency graph — these commits must land in order; (2) the idempotency claim is locator-stable, not content-stable, and source-ordering nondeterminism is a known crack; (3) the spec's byte-identical replay requirement is silently downgraded to ID-only stability with no entry in the out-of-scope list. Ship it as a demo slice; do not treat it as spec closure for #12, #13, #15, or #16.

---

## Resolutions applied to the plan (2026-05-09)

In response to this review, the plan was edited:

1. **§2 Approach** rewritten from "independently mergeable" to "sequentially mergeable" with the dependency chain made explicit.
2. **§4 Commit 3 / SectionChunker** now sorts incoming sections by `(depth, char_offset, section_id)` before chunking, pinning ChunkId determinism even if parser emit order shifts.
3. **§4 Commit 4 / LookupTool** now produces evidence-grade citations: `Citation.quote` is the source's first chunk text (truncated to 240 chars), not the locator.
4. **§7 Out-of-Scope** expanded to call out:
   - Byte-identical replay (spec §8.5) is downgraded to SourceId/ChunkId stability for this slice.
   - None of #12, #13, #15, #16 are *closed* by this slice — they remain open for follow-ups.

Items NOT addressed because they are deliberately deferred:
- Discovery adapters (#14) — not required for the demo.
- Subprocess isolation for the parser (spec §8.10) — labeled follow-up; out of scope row remains.
- Coordinators (spec §3.5) — slice uses sequential CLI; coordinators land when concurrency matters.
