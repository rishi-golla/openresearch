# Nous Hermes Oversight Layer Design

## Goal

Add a backend oversight layer powered by the Nous Hermes agent that sits above the
existing ReproLab pipeline and improves output quality by detecting hallucinations,
unsupported claims, and overstatements across paper implementation and improvement
workflows.

This layer must not replace the current builder, verifier, supervisor, or
improvement agents. It must observe them, evaluate their outputs, and intervene in
bounded, explicit ways when quality issues are detected.

## Product Intent

The pipeline must do two things well:

1. Implement paper concepts and show that implementation credibly.
2. Explore improvements and only surface improvements that are actually supported.

To achieve that, we need an independent quality-control layer that can inspect both:

- what agents claim
- what the evidence actually proves

## Non-Goals

- Replacing the current orchestrator with Hermes
- Replacing existing verifier agents
- Allowing Hermes to silently rewrite history or mutate prior evidence
- Turning Hermes into a cosmetic UI-only status source

## High-Level Architecture

Introduce a new backend service layer, tentatively `backend/hermes_audit/`, that is
responsible for running Nous Hermes audits over the pipeline.

This layer is separate from the current agent registry and separate from the
frontend replay logic.

### Existing pipeline stays intact

- Current builder agents still produce structured outputs.
- Current verifier/supervisor logic still exists.
- Current improvement logic still exists.

### New oversight layer

After important steps, the orchestrator emits an audit payload to the Hermes layer.
The Hermes layer runs Nous Hermes over that payload and returns an audit result.

That result can annotate, downgrade, or trigger a bounded retry/escalation flow.

## Oversight Scope

Hermes must inspect both:

1. Structured outputs
   - paper claim map
   - reproduction contract
   - baseline result
   - experiment artifacts
   - improvement hypotheses
   - path results
   - gate decisions and research map summaries

2. Raw traces and evidence
   - Claude text returned by the agent
   - tool activity logs
   - run logs
   - commands log
   - plots, metrics, provenance, and other files on disk

This is essential because hallucinations can appear in the structured outputs, the
natural-language trace, or both.

## Audit Timing

Hermes should run at two levels.

### Step audits

Run after each major pipeline step:

- paper understanding
- artifact discovery
- environment detective
- reproduction planner
- baseline implementation
- experiment runner
- improvement orchestrator
- each improvement path
- research map generation

Step audits catch hallucinations early and produce targeted corrective actions.

### Checkpoint audits

Run after key milestones:

- after plan creation
- after baseline run
- after improvement runs
- before final synthesis/publication

Checkpoint audits use broader context and can identify overclaims that only become
visible once more evidence is available.

## Intervention Model

Hermes is not annotate-only. It has bounded intervention powers.

### Allowed interventions

- `annotate`
  Add a grounded/caveat/unsupported judgment to the audited target.

- `retry_step`
  Request the current step to be rerun with a corrective note explaining what
  evidence is missing or what claim is overstated.

- `request_evidence`
  Ask the pipeline to gather more evidence before the claim is treated as verified.

- `downgrade_claim`
  Reduce a claim from verified to caveated, partial, unsupported, or equivalent
  pipeline-safe language.

- `suppress_publication`
  Prevent unsupported claims from appearing in final implementation/improvement
  summaries or UI states presented as fact.

- `escalate_human`
  Mark the run for human review after repeated failures or contradictions.

### Disallowed interventions

- silently rewriting previous outputs
- directly replacing the orchestrator
- inventing new pipeline stages
- mutating stored artifacts
- directly editing generated code outside an orchestrated retry flow

## Nous Hermes Integration Strategy

Use Nous Hermes as a backend runtime, not as a ReproLab agent registry entry.

### Why backend layer instead of agent role

- It must audit the full system, not participate as just another node inside it.
- It needs access to cross-step context, raw traces, and artifact state.
- It needs independence from the same execution path it is judging.

### Integration boundary

Create an adapter that translates ReproLab audit payloads into the format expected
by Nous Hermes and translates Hermes results back into ReproLab audit reports.

The adapter should hide framework-specific details from the rest of the pipeline.

## Backend Components

### `backend/hermes_audit/models.py`

Core types:

- `HermesAuditTarget`
- `HermesAuditScope`
- `HermesEvidenceRef`
- `HermesIntervention`
- `HermesAuditReport`

### `backend/hermes_audit/payloads.py`

Builds step/checkpoint audit payloads from pipeline state, step outputs, traces,
and artifact paths.

### `backend/hermes_audit/client.py`

Owns the Nous Hermes integration.

Responsibilities:

- initialize/configure Hermes runtime
- submit audit tasks
- parse Hermes responses
- normalize them into stable ReproLab schema

### `backend/hermes_audit/service.py`

Application service that:

- decides when to audit
- invokes the Hermes client
- stores reports
- returns interventions to the orchestrator

### `backend/hermes_audit/storage.py`

Persists audit reports under the run directory, for example:

- `runs/<project_id>/hermes/step-<name>.json`
- `runs/<project_id>/hermes/checkpoint-<name>.json`
- `runs/<project_id>/hermes/index.json`

## Audit Report Contract

Each Hermes audit report should include at least:

- `target`
  Step or checkpoint name, e.g. `baseline-implementation`, `gate_2`

- `scope`
  `step` or `checkpoint`

- `status`
  `grounded`, `caveat`, `unsupported`

- `summary`
  Short explanation of the result

- `findings`
  Concrete supported observations

- `unsupported_claims`
  Claims that are missing evidence or contradicted

- `evidence_refs`
  File paths, artifact ids, trace snippets, or checkpoint fields used

- `recommended_intervention`
  One of the allowed intervention types

- `corrective_note`
  Text the orchestrator can pass into a retry

- `confidence`
  low, medium, or high

## Orchestrator Integration

The orchestrator remains the source of execution order, but it gains hooks into the
Hermes audit service.

### For each step

1. Run current step normally.
2. Save/collect the step output, trace text, and artifact refs.
3. Call Hermes step audit.
4. Apply the returned intervention if needed.
5. Record the audit report in pipeline state and on disk.

### For each checkpoint

1. Assemble checkpoint evidence package.
2. Run Hermes checkpoint audit.
3. Merge the resulting annotation/intervention into the current checkpoint outcome.
4. Record the report in state and on disk.

## Retry Policy

Because Hermes can intervene, retry behavior must be bounded and explainable.

Recommended policy:

- allow one corrective retry for ordinary step audits
- allow up to two retries for critical end-of-run claims
- if still unsupported, downgrade/suppress and continue or escalate

Each retry must record:

- original audit report
- retry reason
- corrective note passed into the step
- post-retry audit outcome

## State Model Changes

Extend the backend pipeline state with a Hermes section, for example:

- `hermes_step_reports`
- `hermes_checkpoint_reports`
- `hermes_interventions`

This gives the frontend and API a stable source of truth for real Hermes activity.

## API / UI Readiness

This backend slice should prepare the UI to display real Hermes updates later.

The API should eventually expose:

- latest Hermes status for each step/checkpoint
- report history
- intervention history
- evidence references

The `/lab` Hermes panel can then render actual backend audit results rather than
frontend-derived approximations.

## Failure Handling

If Nous Hermes is unavailable:

- do not crash the main pipeline by default
- record a Hermes system error report
- mark Hermes status as unavailable
- continue with the primary run unless the caller explicitly requires Hermes

If Hermes returns malformed output:

- store the raw response
- normalize where safe
- otherwise create a system-error audit report and continue safely

## Testing Strategy

### Unit tests

- payload construction from pipeline state
- response normalization
- intervention mapping
- persistence of reports

### Integration tests

- orchestrator invokes Hermes service at expected steps
- retries occur when Hermes marks output unsupported
- unsupported claims are downgraded/suppressed in final outputs

### Failure-mode tests

- Hermes unavailable
- malformed Hermes response
- repeated unsupported outputs triggering escalation

## Rollout Plan

### Phase 1

- backend models
- Hermes adapter/client
- payload builder
- persisted audit reports

### Phase 2

- orchestrator hooks for step audits
- bounded retry/intervention flow
- checkpoint audit flow

### Phase 3

- pipe real Hermes reports into `/lab`
- show intervention and evidence history

## Success Criteria

- Hermes reviews both structured outputs and raw traces
- Hermes can intervene without replacing existing agents
- unsupported claims are downgraded or suppressed before final surfacing
- retries are explicit and bounded
- final paper implementation and improvement outputs are more trustworthy
