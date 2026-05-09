# ReproLab Reliability, Accuracy, and Precision Optimizations

This file captures high-leverage improvements from the live SDK run and offline inspection. The goal is not to add features indiscriminately; the goal is to improve reliability, accuracy, and precision without compromising modularity, provider portability, offline determinism, or debuggability.

Do not implement these blindly. For each item, perform adversarial analysis first: identify failure modes, schema or migration impact, rollback path, test coverage, cost/latency impact, and how telemetry will prove the change works.

## Live-Run Context

- Stage 1 spent roughly 30-60 seconds on avoidable discovery calls (`Glob`, `ls`, `pwd`, and `Read /root/...`) before finding the parsed paper text.
- The orchestrator already knows the parsed paper location, so agents should not need to hunt for it.
- A live SDK run reported `[paper-understanding] completed in 393s`, which is too slow for iterative testing and indicates avoidable serialization, excessive tool-turns, weak progress visibility, or oversized prompts.
- The current `tail -F ... | grep ...` monitoring workflow is insufficient because it only exposes coarse stage boundaries and misses fine-grained progress, stall causes, retries, provider latency, and tool-call activity.
- Offline inspection confirmed PyMuPDF extraction already finds named sections such as Abstract, Experiments, and References.
- Workspace state currently stores paper understanding largely as a single `claim_map` blob rather than exposing section-specific context variables.
- Offline output showed assumptions `A001` through `A013` with `evidence: []`, including claims such as "Adam epsilon not specified" without cited support.
- Current evaluation can fall back to self-comparison unless paper headline metrics are provided explicitly.
- The setup guide mentions stronger parsing options such as Nougat OCR, but the current project dependency surface appears to rely on PyMuPDF for PDF parsing.

## Non-Negotiable Goals

- Reliability: reduce brittle agent discovery loops, enforce deterministic inputs, bound confused tool use, and use independent verification where possible.
- Accuracy: make context section-aware, preserve tables and equations, and ground every claim in cited paper evidence.
- Precision: improve numerical hyperparameter extraction, expose disagreements, and verify against paper metrics rather than self-generated baselines.
- Speed: parallelize independent work, eliminate avoidable tool calls, cache deterministic artifacts, and provide configurable execution modes for different quality/cost tradeoffs.
- Maintainability: keep changes modular, provider-agnostic, testable, observable, and compatible with offline deterministic mode.

## Priority Optimizations

### 1. Add Execution Modes for Speed/Quality Tradeoffs

The pipeline needs explicit execution modes so local iteration can be fast while final verification can remain exhaustive. Add at least two production modes:

- `efficient`: optimized for fast, reliable iteration with bounded tool calls, minimal self-consistency, cached artifacts, selective gates, and aggressive reuse of parsed/context artifacts.
- `max`: optimized for highest-confidence reproduction with self-consistency, cross-model verification, stronger parser backends, broader artifact discovery, and stricter gates.

The execution profile should be independent from the experiment backend:

- `local`: fast non-container execution or simulation for development and UI iteration. It must be labeled as local and must not be represented as sandbox-verified reproduction.
- `docker`: real containerized sandbox execution for cross-machine reproducibility, dependency isolation, and final verification.

Implementation notes:

- Represent modes as typed configuration, not scattered conditionals.
- Make mode choices visible in run metadata, telemetry, and final reports.
- Keep deterministic offline mode stable and testable.
- Allow individual advanced settings to override mode defaults when needed.

Adversarial concerns:

- `efficient` must not silently weaken correctness claims.
- `max` must not become unbounded in cost, retries, or tool calls.
- Different modes can hide bugs if test coverage only exercises one path.

Acceptance criteria:

- CLI/API/UI can select execution mode.
- CLI/API/UI can select local or Docker sandbox execution independently from efficient/max.
- Run metadata records selected mode and resolved settings.
- Tests cover `efficient`, `max`, and default-mode behavior.
- Reports clearly label any reduced verification in `efficient` mode.

### 2. Parallelize Independent Pipeline Work

The pipeline should run independent tasks concurrently where correctness allows. The 393-second paper-understanding stage should be broken down into smaller timed substeps so parallelization opportunities are visible and safe.

Candidate parallel work:

- Section summarization by section or section group.
- Claim extraction, assumption extraction, and metric extraction after paper text is available.
- Artifact discovery from repository metadata, paper references, DOI/arXiv metadata, and external search.
- Independent verification gates that do not depend on each other's outputs.
- Optional parser backends, when they can race or run as fallbacks with clear precedence.

Implementation notes:

- Build a dependency graph for pipeline stages instead of assuming a fully serial flow.
- Use bounded concurrency with provider-aware rate limits.
- Cache deterministic artifacts such as parsed text, section maps, DOI/arXiv metadata, and repository inventory.
- Preserve ordering in final reports even when execution is concurrent.

Adversarial concerns:

- Parallel agents can duplicate work or produce conflicting writes.
- Provider rate limits can make naive parallelism slower or less reliable.
- Shared workspace writes need clear ownership and merge rules.

Acceptance criteria:

- Stage telemetry shows queued, running, completed, skipped, retried, and failed states per task.
- No two concurrent tasks write the same workspace variable without an explicit reducer.
- End-to-end runtime improves on representative papers without reducing evidence quality.

### 3. Add Structured Progress Logging and Stall Diagnostics

Progress logging needs to be first-class, not dependent on manual `tail | grep` filters. Every stage should emit structured events that explain what work is happening, how long it has been running, and why it may be waiting.

Implementation notes:

- Emit structured JSONL progress events for run, stage, subtask, provider call, tool call, retry, validation repair, gate, and artifact write.
- Include timestamps, elapsed time, run ID, project ID, stage ID, subtask ID, provider/model, mode, token estimates, tool-call count, retry count, and current status.
- Add heartbeat events for long-running stages.
- Add stall detection that warns when no progress event has been emitted for a configurable interval.
- Provide a concise monitor command or CLI view that reads the structured log directly.

Adversarial concerns:

- Excessive logging can expose sensitive paper or repository content.
- Logging must not meaningfully slow the pipeline.
- Heartbeats should not hide a truly stuck provider call or blocked subprocess.

Acceptance criteria:

- A user can tell which exact subtask is running during a long stage.
- Stalls produce explicit warnings with the last successful event and current wait reason.
- Provider latency, tool-call counts, and validation retries are visible per stage.
- Tests cover progress event emission and stall detection without relying on wall-clock-heavy sleeps.

### 4. Inject Parsed Paper Context Into Every Agent Prompt

Agents should never need to discover the parsed paper path. The orchestrator already knows the artifact path, so every agent prompt should receive either:

- a deterministic `<paper_text_path>` such as `runs/<project_id>/parsed_full_text.txt`, or
- inline parsed sections when the paper is small enough for the token budget.

For a 13-page paper, inlining named sections is likely cheaper than spending multiple tool turns on path discovery.

Implementation notes:

- Materialize a stable parsed full-text artifact during intake or parsing.
- Include the direct path and/or inline section payload in the structured prompt context for every relevant agent.
- Add tests that assert prompts include the path or inline sections.
- Add trace telemetry for paper context source, prompt token estimate, and first paper-access method.

Adversarial concerns:

- Prompt bloat can degrade answer quality if full text is inlined unnecessarily.
- Resumed runs must not point agents at stale paths.
- Path handling must not introduce traversal or workspace escape risks.

Acceptance criteria:

- First-stage logs show no initial `Glob`, `ls`, or `pwd` churn solely to find the paper.
- Agents can access paper text deterministically from the prompt context.
- Resume/checkpoint flows use the correct parsed artifact for the current run.

### 5. Expose Paper Sections as Workspace Variables

Do not force downstream agents to consume one large claim-map blob when section-level context exists. Store named sections as first-class workspace variables with citations.

Examples:

- `abstract_section`
- `introduction_section`
- `method_section`
- `experiments_section`
- `implementation_details_section`
- `results_section`
- `references_section`

This is especially important for hyperparameter extraction because values usually cluster in Experiments, Implementation Details, Appendix, or table captions.

Implementation notes:

- Normalize section names into stable variable keys.
- Preserve section hierarchy where available.
- Attach citations or source spans to every section variable.
- Let agents request targeted variables instead of re-reading the full paper.

Adversarial concerns:

- Section title collisions can overwrite context.
- Papers may use unusual section names or split key details across appendices and tables.
- References and related work must not pollute experiment or implementation context.

Acceptance criteria:

- Workspace variables expose named sections with stable keys and citations.
- Tests cover duplicate titles, missing common sections, and appendix-heavy papers.
- Hyperparameter extraction can target experiment-like sections without reparsing the whole document.

### 6. Require Grounded Evidence for Every Assumption and Claim

Empty evidence lists should fail validation for assumptions and paper claims. The system should not emit claims such as "not specified" without evidence showing what was searched and what text supports the absence or ambiguity.

Implementation notes:

- Make `Assumption.evidence` non-empty in the schema.
- Make `PaperClaimMap` claim citations non-empty.
- Enforce the invariant in both SDK provider outputs and offline deterministic outputs.
- Update prompts so models know cited evidence is mandatory.
- Represent negative evidence carefully: cite the searched section and include a quote or locator supporting the absence or ambiguity.

Adversarial concerns:

- Negative claims are harder to cite than positive claims.
- Models may fabricate citations to satisfy validation.
- Overly strict validation can block useful partial outputs unless repair/retry paths are clear.

Acceptance criteria:

- Empty evidence fails validation.
- Cited negative evidence is allowed only with explicit source/section support.
- Tests cover positive claims, ambiguous claims, and "not specified" assumptions.
- Telemetry reports evidence coverage for each extraction stage.

### 7. Add Self-Consistency for Numerical Extraction

Numerical hyperparameters drive reproduction quality. Run the numerical extraction stage multiple times with controlled temperature variation, then majority-vote stable values or surface disagreements as ambiguities.

Implementation notes:

- Scope this to the claim or numerical extraction stage, not the entire pipeline.
- Use `N=3` initially.
- Extract value, unit, parameter name, context section, and citation for each candidate.
- Add a consensus helper that can merge equivalent numeric forms and preserve disagreements.

Adversarial concerns:

- Token cost and latency increase by roughly 3x for that stage.
- Correlated model errors can still produce the same wrong value.
- Majority vote must not override conflicting cited evidence silently.

Acceptance criteria:

- Stable numeric values include citations and consensus metadata.
- Conflicting values become explicit ambiguities, not silent picks.
- Tests cover unit normalization, equivalent numeric formats, and contradictory candidates.

### 8. Use Cross-Model or Cross-Provider Verification Gates

Verification gates should not default to the same provider and model that produced the artifact. Prefer cross-provider verification, for example Anthropic generates and OpenAI verifies, or OpenAI generates and Anthropic verifies. If only one provider is configured, use a materially different verifier model and record the fallback reason.

Implementation notes:

- Add verifier provider/model overrides per gate.
- Keep the orchestrator provider-agnostic.
- Record producer provider/model and verifier provider/model in telemetry.
- Fail closed when a configured independent verifier is unavailable, unless an explicit fallback policy allows degraded mode.

Adversarial concerns:

- Cross-provider schema drift can create false failures.
- Missing API keys may break local runs.
- Verification costs can rise.

Acceptance criteria:

- Gate telemetry proves verifier independence or records an explicit fallback reason.
- Tests cover provider override, missing provider fallback, and schema-compatible verification.
- Gates do not rubber-stamp artifacts from the same model without visibility.

### 9. Improve PDF Parsing for Tables and Equations

PyMuPDF is fast and useful, but it can lose tabular hyperparameters and equation structure. Add a stronger parser option behind the existing parser abstraction for table/equation-heavy papers, such as GROBID, Nougat, or another modular parser strategy.

Implementation notes:

- Keep PyMuPDF as the lightweight default.
- Add a parser strategy chain with optional table/equation-capable backends.
- Persist parser provenance, confidence, and extracted artifact types.
- Preserve LaTeX-like equation text and table cell structure where possible.

Adversarial concerns:

- Heavy dependencies may require model downloads, Java, GPU, or external services.
- OCR/math parsers can hallucinate or corrupt text.
- License, runtime, and deployment footprint must be evaluated.

Acceptance criteria:

- Fixtures with tables and equations preserve cell values and equation text.
- Parser provenance is available to downstream agents and debugging tools.
- The system degrades cleanly when optional parser backends are unavailable.

## Lower-Priority Quick Wins

- Add `--fresh` to `cmd_reproduce` so users can force a new run or ignore checkpoints without manually deleting state.
- Add per-agent tool-call budgets so a confused agent cannot spiral indefinitely.
- Add `cmd_eval --paper-metrics` so evaluation can compare against paper headline metrics instead of self-comparison.
- Add per-stage timeout and retry policy configuration, with mode-specific defaults.
- Add cache hit/miss logging for parsed paper text, section maps, artifact discovery, and provider-derived summaries.

## Recommended Implementation Order

1. Phase A: implement structured progress logging, stall diagnostics, execution modes, parsed-paper path or inline context injection, `--fresh`, and per-agent tool-call budget.
2. Phase B: split paper understanding into parallelizable subtasks, add mandatory evidence validation, and expose section workspace variables.
3. Phase C: add numerical self-consistency, cross-model verification gates, cache-aware artifact discovery, and mode-specific gate policies.
4. Phase D: add optional table/equation parser backends behind the parser abstraction.

Phase A should visibly improve the next live run and make stalls diagnosable. Phase B improves extraction quality and runtime. Phase C improves verifier reliability and numerical precision. Phase D improves hard-paper coverage without blocking the core pipeline.

## Guardrails

- Preserve offline deterministic mode.
- Preserve the provider abstraction; do not embed OpenAI- or Anthropic-specific logic in the orchestrator.
- Preserve citation, event-store, and workspace invariants.
- Prefer focused tests before broad refactors.
- Keep telemetry first-class: context source, section IDs, prompt token estimates, provider/model IDs, tool-call counts, validation failures, and evidence coverage.
- Treat performance as a correctness-adjacent concern: speedups are acceptable only when evidence quality, citation coverage, and verification integrity are preserved or explicitly labeled as reduced mode behavior.
- Every optimization must improve reliability, accuracy, or precision. If a change trades one of those away, document the tradeoff and require an explicit product decision.

## Definition of Done

- `efficient` and `max` modes exist, are typed, are visible in run metadata, and have tested default settings.
- Long-running stages emit structured progress and heartbeat events that identify the current subtask and wait reason.
- Representative pipeline work is parallelized where dependencies allow, with bounded concurrency and workspace write ownership.
- Agents receive deterministic paper context without discovery-tool churn.
- Every claim and assumption has non-empty validated evidence with source, locator, and cited text or span.
- Numerical hyperparameters include cited source context and explicit conflict handling.
- Verification gates use an independent provider/model where configured, or record a clear fallback reason.
- Parser outputs preserve tables and equations when available, with provenance.
- End-to-end paper/repo runs show fewer wasted tool calls, stronger citations, and no silent self-comparison evaluation.
