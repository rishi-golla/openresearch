# Hermes Verification And Paper Depiction Design

## Goal

Extend the `/lab` experience with two separate visual surfaces:

1. `Hermes Verification`
   A standalone verification panel that communicates whether the system's current claims are grounded, supported, and safe to surface.

2. `Paper Depiction`
   A standalone depiction panel that visually explains how one paper concept is being translated into implementation and evidence.

These surfaces must stay separate. Hermes is about trust and publishability. Paper depiction is about understanding what the system is building from the paper.

## Product Intent

The pipeline should clearly support two user goals:

1. Implement research paper concepts and show that implementation visually in real time.
2. Explore improvements and show whether those improvements are actually supported.

Hermes should protect the truthfulness of what the UI says.
Paper depiction should explain the implementation journey in a clear visual form.

## Hermes Verification Panel

### Responsibilities

- Show live verification status for the current run.
- Make unsupported or weakly supported claims visible.
- Separate `verified` from `tentative`.
- Summarize whether the current stage is safe to present as fact.

### Visual Shape

- Eyebrow label
- Strong title
- One-sentence summary
- Checklist rows with status markers

### Checklist Rows

The initial panel should support rows such as:

- Paper concept extracted
- Claim grounded in source text
- Implementation matches concept
- Artifacts support reported result
- Improvement claim verified

### Status Model

- `pending`
- `checking`
- `verified`
- `caveat`
- `unsupported`

## Paper Depiction Panel

### Responsibilities

- Show one active concept at a time.
- Combine a storyboard feel with technical specificity.
- Explain how a paper concept becomes code, artifacts, and an optional improvement.

### Visual Shape

- Concept title
- Plain-English interpretation
- Storyboard strip:
  - Extracted
  - Interpreted
  - Implemented
  - Validated
  - Improved
- Technical evidence block:
  - implemented surface
  - validation artifact
  - metric hint
  - improvement delta when available

### Status Model

- `planned`
- `active`
- `validated`
- `improved`

## Frontend Contract Changes

Extend the dashboard snapshot with:

- `hermesPanel`
- `conceptCards`

Extend dashboard events with:

- `hermes_check_updated`
- `concept_card_updated`

These events should be independent from the generic reasoning/message stream so the UI can render both panels as first-class surfaces.

## Dashboard Placement

- Keep `Hermes Verification` and `Paper Depiction` separate.
- Place them near the top of the lab experience, above the denser operational dashboard grid.
- Keep the existing dashboard shell intact below them.

## Initial Data Strategy

For the current lab implementation:

- Hermes states are derived from pipeline stage, gates, baseline artifacts, and path results.
- Paper depiction content is derived from the claim map, baseline result, and experiment artifacts.
- The replay event stream should update both panels over time, just like the rest of the dashboard.

## Out Of Scope

- Adding Hermes as a fully orchestrated Claude SDK backend agent in this slice.
- Reworking the supervisor-verifier backend flow.
- Merging Hermes and depiction into a single combined card.
