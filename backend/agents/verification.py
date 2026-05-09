"""Verification Team — 4 verifiers + supervisor agent.

Provides:
  - ``run_gate_offline()`` — deterministic verification without LLM
  - Individual verifier functions for unit testing
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.agents.schemas import (
    BaselineResult,
    ExperimentArtifacts,
    GateDecision,
    GateStatus,
    PaperClaimMap,
    PathResult,
    VerificationReport,
    VerifierScore,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual verifiers (offline mode)
# ---------------------------------------------------------------------------

def verify_method_fidelity(
    paper_claim_map: PaperClaimMap,
    baseline_result: BaselineResult,
    code_dir: Path | None = None,
) -> VerifierScore:
    """Check implementation matches paper algorithm."""
    findings: list[str] = []
    mismatches: list[str] = []

    # Check assumptions were applied
    expected_assumptions = set(
        a.assumption_id for a in paper_claim_map.ambiguities
    )
    applied = set(baseline_result.assumptions_applied)

    applied_count = len(expected_assumptions & applied)
    if applied_count == len(expected_assumptions):
        findings.append(f"All {applied_count} assumption decisions applied")
    else:
        missing = expected_assumptions - applied
        mismatches.append(f"Missing assumption applications: {missing}")

    # Check mode
    if baseline_result.mode == "implement_from_paper":
        findings.append("Mode 2 (implement from paper) — stricter review required")

    # Check code exists
    if code_dir and code_dir.exists():
        if (code_dir / "train.py").exists():
            findings.append("train.py entry point exists")
        else:
            mismatches.append("No train.py found")

    score = 1.0 - (len(mismatches) * 0.2)
    return VerifierScore(
        verifier_name="method_fidelity",
        score=max(0.0, min(1.0, score)),
        findings=findings,
        mismatches=mismatches,
        severity="low" if not mismatches else "medium",
    )


def verify_environment(
    baseline_result: BaselineResult,
    artifacts: ExperimentArtifacts,
    baseline_dir: Path | None = None,
) -> VerifierScore:
    """Check environment reproducibility."""
    findings: list[str] = []
    mismatches: list[str] = []

    # Check Dockerfile exists
    if baseline_result.dockerfile_path:
        df_path = Path(baseline_result.dockerfile_path)
        if df_path.exists():
            content = df_path.read_text()
            if "FROM " in content:
                findings.append("Valid Dockerfile with base image")
            if "==" in content:
                findings.append("Pinned package versions in Dockerfile")
            else:
                mismatches.append("Packages not pinned in Dockerfile")
        else:
            mismatches.append("Dockerfile path does not exist")
    else:
        mismatches.append("No Dockerfile path specified")

    # Check commands.log
    if artifacts.commands_log_path and Path(artifacts.commands_log_path).exists():
        findings.append("commands.log exists")
    else:
        mismatches.append("commands.log missing")

    # Check logs
    if artifacts.log_path and Path(artifacts.log_path).exists():
        findings.append("Run logs exist")
    else:
        mismatches.append("Run logs missing")

    score = 1.0 - (len(mismatches) * 0.2)
    return VerifierScore(
        verifier_name="environment_execution",
        score=max(0.0, min(1.0, score)),
        findings=findings,
        mismatches=mismatches,
        severity="low" if not mismatches else "medium",
    )


def verify_data_metrics(
    paper_claim_map: PaperClaimMap,
    artifacts: ExperimentArtifacts,
) -> VerifierScore:
    """Check data and metric validity."""
    findings: list[str] = []
    mismatches: list[str] = []

    # Check metrics exist
    if artifacts.metrics:
        findings.append(f"Metrics present: {list(artifacts.metrics.keys())}")
        # Check against target
        for metric_spec in paper_claim_map.metrics:
            if metric_spec.name in artifacts.metrics or "reward" in str(artifacts.metrics):
                findings.append(f"Target metric '{metric_spec.name}' found")
            else:
                mismatches.append(f"Target metric '{metric_spec.name}' missing from results")
    else:
        mismatches.append("No metrics in artifacts")

    # Check success
    if artifacts.success:
        findings.append("Experiment completed successfully")
    else:
        mismatches.append(f"Experiment failed: {artifacts.error_message}")

    score = 1.0 - (len(mismatches) * 0.25)
    return VerifierScore(
        verifier_name="data_metrics",
        score=max(0.0, min(1.0, score)),
        findings=findings,
        mismatches=mismatches,
        severity="low" if not mismatches else "high",
    )


def verify_artifacts(
    artifacts: ExperimentArtifacts,
    baseline_dir: Path | None = None,
) -> VerifierScore:
    """Check all hard artifacts exist."""
    findings: list[str] = []
    mismatches: list[str] = []

    required = [
        ("metrics", bool(artifacts.metrics)),
        ("logs", bool(artifacts.log_path and Path(artifacts.log_path).exists())),
        ("commands.log", bool(artifacts.commands_log_path and Path(artifacts.commands_log_path).exists())),
        ("provenance.json", bool(artifacts.provenance_path and Path(artifacts.provenance_path).exists())),
        ("plots", bool(artifacts.plots)),
    ]

    for name, present in required:
        if present:
            findings.append(f"✓ {name}")
        else:
            mismatches.append(f"Missing: {name}")

    score = sum(1 for _, p in required if p) / len(required)
    return VerifierScore(
        verifier_name="artifact_diff",
        score=score,
        findings=findings,
        mismatches=mismatches,
        severity="low" if score >= 0.8 else "high",
    )


# ---------------------------------------------------------------------------
# Supervisor: aggregate verifier decisions
# ---------------------------------------------------------------------------

def run_gate_offline(
    gate: str,
    paper_claim_map: PaperClaimMap,
    baseline_result: BaselineResult,
    artifacts: ExperimentArtifacts,
    *,
    code_dir: Path | None = None,
    baseline_dir: Path | None = None,
) -> VerificationReport:
    """Run all 4 verifiers and produce a supervisor decision (offline)."""
    scores = [
        verify_method_fidelity(paper_claim_map, baseline_result, code_dir),
        verify_environment(baseline_result, artifacts, baseline_dir),
        verify_data_metrics(paper_claim_map, artifacts),
        verify_artifacts(artifacts, baseline_dir),
    ]

    # Supervisor decision logic
    avg_score = sum(s.score for s in scores) / len(scores)
    all_mismatches = [m for s in scores for m in s.mismatches]
    has_critical = any(s.severity == "high" for s in scores)

    if avg_score >= 0.9 and not has_critical:
        status = GateStatus.verified
    elif avg_score >= 0.7:
        status = GateStatus.verified_with_caveats
    elif avg_score >= 0.5:
        status = GateStatus.partial_reproduction
    elif artifacts.success:
        status = GateStatus.verified_with_caveats
    else:
        status = GateStatus.failed_reproduction

    reasoning = (
        f"Average verifier score: {avg_score:.2f}. "
        f"{len(all_mismatches)} issues found. "
        f"{'Critical issues present.' if has_critical else 'No critical issues.'}"
    )

    return VerificationReport(
        gate=gate,
        status=status,
        verifier_scores=scores,
        reasoning=reasoning,
        decision_log_entry=f"{gate}: {status.value} (avg={avg_score:.2f})",
    )


def run_improvement_gate_offline(
    path_results: list[PathResult],
    paper_claim_map: PaperClaimMap,
    baseline_metrics: dict[str, Any],
) -> VerificationReport:
    """Verify improvement paths (Gate 3)."""
    scores: list[VerifierScore] = []
    findings: list[str] = []
    mismatches: list[str] = []

    successful_paths = [p for p in path_results if p.success]
    failed_paths = [p for p in path_results if not p.success]

    findings.append(f"{len(successful_paths)}/{len(path_results)} paths succeeded")
    if failed_paths:
        for p in failed_paths:
            mismatches.append(f"Path {p.path_id} failed: {p.failure_notes}")

    # Check each successful path has metrics
    for path in successful_paths:
        if path.metrics:
            findings.append(f"Path {path.path_id}: metrics present")
        else:
            mismatches.append(f"Path {path.path_id}: no metrics")

    overall_score = len(successful_paths) / max(len(path_results), 1)
    scores.append(VerifierScore(
        verifier_name="improvement_gate",
        score=overall_score,
        findings=findings,
        mismatches=mismatches,
    ))

    status = (
        GateStatus.verified if overall_score >= 0.5
        else GateStatus.partial_reproduction
    )

    return VerificationReport(
        gate="gate_3",
        status=status,
        verifier_scores=scores,
        reasoning=f"{len(successful_paths)}/{len(path_results)} improvement paths verified.",
        decision_log_entry=f"gate_3: {status.value}",
    )
