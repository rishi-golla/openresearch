# Catch-up — what changed since you were last here (≈2026-06-14 → 2026-06-21)

> **Who/why:** You (Armaan) last touched `main` around **2026-06-14** (the last
> commits here are `#108 Integrate/azure-gcp` and `#106 Integrate/grader-fidelity`).
> Since then the real line of development moved to a feature trunk and **`main` is
> now 173 commits behind it**. This doc is the bridge so you don't have to read 173
> commits. TL;DR at top, details below, the one decision you need to make at the end.

---

## 0. TL;DR (read this, then skim the rest)

- **`main` is stale.** The active line is **`feat/bes-conversion-correctness`** (the
  "trunk") — `main` is **2 ahead / 173 behind** it, and the two had *diverged* (not a
  fast-forward) because `#106`/`#108` were integrated straight to `main` while the
  trunk kept going. **This has all been reconciled.**
- **One PR lands everything on `main`:** **#115** (`consolidate/main-trunk → main`,
  MERGEABLE/CLEAN, full suite **7036 green**). Merging it makes `main` the canonical
  superset — trunk + three new workstreams + a big harness integration + cleanup.
- **PRs were consolidated 10 → 2** this week: only **#115** (the hinge) and **#107**
  (BES P0, clean) remain open; everything else was merged into the trunk or closed as
  superseded. **Branches pruned 18 → 13.**
- **Nothing was pushed to `main` except this doc.** The big merge (#115) is staged and
  **waiting on your call** — we deliberately did not touch `main`.
- **Read these 5 strategic docs** (all on the trunk / in #115): the SDAR unification
  mega-prompt, the Run/Test Bank mega-prompt, the evidence-first ADR, the cleanup
  design, and the finish-line handoff. Paths in §5.

---

## 1. The project, unchanged at its core

OpenResearch: an RLM agent that reproduces ML papers end-to-end (ingest → build env →
implement baseline → run on GPU → score against a rubric → improve). **North Star =
the SDAR paper (arXiv 2605.15155)** reproduced at the highest *grounded* rubric score
(it stresses every dimension: 3 Qwen sizes, 3 envs, GRPO+OPSD, the `g_t=σ(β·Δ_t)`
gate). Everything below serves making that score real and repeatable.

## 2. What landed on the TRUNK since you left (the 173 commits, by theme)

You're behind on a lot of correctness/reliability work. The headline lines:

- **BES conversion + archival correctness (P0)** — the trunk's namesake. The
  evolutionary BES redesign was CUT; the proven failure was *conversion/archival*, not
  generation. Coherent champion bundle, conversion-provenance guard, archival gate,
  SELECT-stability instrumentation. (`#107`.)
- **Grader-fidelity suite** — the leaf grade is a non-deterministic LLM call; this
  denoises it: median-of-N (`OPENRESEARCH_GRADER_SAMPLES`), decoupled grader transport,
  evidence-fingerprint floor (median not max), champion-artifact snapshotting,
  deterministic-leaf checker, and the **evidence gate (A7)** that vetoes result-claiming
  leaves with no on-disk evidence. σ-gate calibration cleared at temperature=0
  (σ=0.0067 @ samples=1).
- **Leaf-frontier remediation** — leaf triage (cost-ordered repair plan, zero LLM),
  leaf actuator (stages concrete repair artifacts), scope-inclusion exclusion.
- **Execution reliability** — `run_experiment` streams output, stall detection,
  finalize-on-timeout (partial metrics scored, never zeroed), finalize-time freshness
  re-grade, hard-stop salvage.
- **One-GPU-per-cell execution** — `run_matrix` (one subprocess per cell pinned to one
  GPU), capacity gate, OOM shrink-retry, STOP semantics; the shared cell scheduler.
- **Cloud backends** — Azure AKS GPU backend (Bicep/Helm IaC) and the GCP/GKE backend
  (now first-class via `--sandbox gke`, see §3).
- **OAuth-root degenerate-loop detector** — `claude-oauth` root sometimes churns
  `FINAL_VAR` without implementing; now detected + early-aborted.
- Plus the stability invariants (REPL safe-builtins, forced-iteration, Dockerfile shape
  guard, run-status enum, claude-agent-sdk isolation) — all in `CLAUDE.md`.

## 3. What THIS session added (2026-06-20 → 21) — all on the trunk / in #115

**Three independent workstreams (audit → plan → TDD → review):**
- **A — Foundry provider unification (#111):** any Azure AI Foundry model usable in
  every tier (root/executor/sub-agents/grader/navigation) through one config path.
  Default-OFF; existing providers byte-identical when unset.
- **B — GKE first-class (#112):** `--sandbox gke` is a supported peer of runpod/aks
  (cell scheduler + capacity gate + OOM retry + torchrun-wrap + `gke_check.sh`
  preflight + GCP L4/H100 catalog SKUs). Hermetic tests, zero GPU CI spend.
- **C — Hallucination diagnosis + Fix-1 (#114):** characterized the gap from real run
  artifacts; added a default-OFF `all-models-failed` greenlight guard
  (`OPENRESEARCH_PER_MODEL_STATUS_GATE`).

**The grounded-harness integration (#116) — your #110, landed:** your
`feat/grounded-self-improvement-harness-reliability` work was squash-integrated onto the
trunk (clean history, not 1,413 commits). **13 feature clusters, all default-OFF/dark:**
evidence-audit critic, external adversarial validator (fail-closed), pre-GPU code-review
gate, report-claim gate + claim-grounding engine, metric-reality smoke, recipe library
(positive recipes), lifecycle ledger, arg-contracts, anti-fab guards, asset
provisioning. **Nothing enabled by default → no behaviour change ships.**

**Evidence-first architecture (Phase 1 ADR):** unified the actor → in-loop critic →
external validator → finalize gate pipeline. Audit found the machinery already mostly
composes; one real dedupe shipped (single Azure deployment resolver), and the two
"scary" items (folding evidence_audit into the default-ON forge gate; finalize coverage
asymmetry) were investigated and **correctly left alone** (forge defense untouched,
SIGTERM handlers untouched).

**Cleanup foundation (#117):** two characterization tests guarding the
`REPROLAB_→OPENRESEARCH_` bridge + the `reprolab.db→openresearch.db` fallback (both were
untested), and a research-grounded cleanup design.

**Consolidation:** reconciled the divergent `main`↔trunk into #115; collapsed 5 PRs into
the trunk; pruned merged branches. PRs 10→2, branches 18→13.

## 4. State of your specific work
Your `#110` content is **fully present on the trunk** (via #116). The PR `#110` itself
was closed as superseded (its 76 net-new modules are all in the trunk; the residual was
older shared-file versions). **Your branch is retained and the PR is reopenable** if you
want to inspect anything. Same for the grader-fidelity (#104) and azure-bicep (#109)
PRs — closed as superseded, branches intact, content on the trunk.

## 5. The 5 docs to read (on the trunk; arrive on `main` when #115 merges)
1. `docs/superpowers/prompts/2026-06-20-sdar-unification-megaprompt.md` — drive SDAR to
   the highest grounded score by unifying the harness.
2. `docs/superpowers/prompts/2026-06-21-run-test-bank-megaprompt.md` — a durable,
   cross-contributor bank of every run's outputs/logs/provenance (the right home for the
   12 MB `best_runs/` git bloat).
3. `docs/superpowers/specs/2026-06-21-evidence-first-architecture-adr.md` — the
   actor/critic/validator architecture + dedupe decisions.
4. `docs/superpowers/specs/2026-06-21-project-cleanup-design.md` — the phased cleanup
   (env/db rename is ~90% already done; `best_runs/` is the real bloat; 7 CLAUDE.md
   contradictions catalogued with code-verified correct values).
5. `docs/runbooks/2026-06-21-consolidation-finish-line-handoff.md` — the exact
   merge/close/prune sequence to finish.

## 6. PR + branch state right now
- **Open PRs (2):** **#115** (consolidate/main-trunk → main, the hinge) · **#107** (BES
  P0, clean, redundant-with-#115).
- **Branches (13 remote):** the 2 PR branches + `main` + your stale ones
  (`feat/azure-aks-gpu`, `feat/gcp-gke-backend`, `feat/grader-fidelity`,
  `feat/azure-bicep…`, `feat/grounded-self-improvement…`, two `integrate/*`) +
  `feat/gepa-integration` + two handoff/doc branches.

## 7. THE decision (yours)
**Merge #115 → `main`.** One merge lands the entire reconciled world on `main` (trunk +
A/B/C + your #110 integration + cleanup), 7036-green. Then #107 + your stale branches
close/prune cleanly (sequence in the finish-line handoff). We held off doing this so the
call is yours.

## 8. Still open / needs you
- **The private "other repo"** (a history-cleanup task from the original brief) — never
  started; needs its URL + what's wrong.
- **Phase B cleanup** (CLAUDE.md de-drift, env canonicalize, dead-code, runbook
  archiving, `best_runs/`→Bank) — staged in the cleanup design, runs after #115 lands.
- **SDAR GPU validation + default-flip A/B** — operator/GPU-gated; commands in the SDAR
  runbooks.

— Generated 2026-06-21. Questions → read `CLAUDE.md` (day-to-day) + `system_overview.md`
(the why); both are current on the trunk.
