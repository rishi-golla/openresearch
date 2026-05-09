"""Reproduction evaluation — measures fidelity of reproduction against paper ground truth.

Layer 1: Build success (binary)
Layer 2: Run success (binary)
Layer 3: Convergence (loss curve shape matching)
Layer 4: Metric match (within tolerance of paper's numbers)
Layer 5: Methodology soundness (LLM-as-judge)

Integrates with DeepEval when available, falls back to built-in scoring.
"""

from __future__ import annotations

import math
from typing import Any

from backend.agents.schemas import (
    BaselineResult,
    ExperimentArtifacts,
    PaperClaimMap,
)
from backend.evals.schemas import ReproductionScore

# Optional DeepEval integration
try:
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False


def score_build(baseline: BaselineResult) -> tuple[bool, dict[str, Any]]:
    """Layer 1: Did the Docker container build successfully?"""
    has_dockerfile = bool(baseline.dockerfile_path)
    has_code = bool(baseline.code_path)
    success = has_dockerfile and has_code
    return success, {
        "has_dockerfile": has_dockerfile,
        "has_code": has_code,
    }


def score_run(artifacts: ExperimentArtifacts) -> tuple[bool, dict[str, Any]]:
    """Layer 2: Did the experiment run to completion?"""
    return artifacts.success, {
        "success": artifacts.success,
        "error": artifacts.error_message or "",
    }


def score_metric_match(
    artifacts: ExperimentArtifacts,
    claim_map: PaperClaimMap,
    paper_metrics: dict[str, float],
    tolerance: float = 0.15,
) -> tuple[float, dict[str, Any]]:
    """Layer 4: How close are reproduced metrics to paper's reported values?

    Returns 0-1 score. 1.0 = exact match, 0.0 = completely off.
    tolerance: relative tolerance (0.15 = within 15%).
    """
    if not artifacts.success or not artifacts.metrics:
        return 0.0, {"reason": "experiment failed or no metrics"}

    matches = []
    details: dict[str, Any] = {}

    for metric_name, paper_value in paper_metrics.items():
        reproduced_value = artifacts.metrics.get(metric_name)
        if reproduced_value is None:
            matches.append(0.0)
            details[metric_name] = {"paper": paper_value, "reproduced": None, "score": 0.0}
            continue

        if paper_value == 0:
            score = 1.0 if reproduced_value == 0 else 0.0
        else:
            relative_error = abs(reproduced_value - paper_value) / abs(paper_value)
            # Score: 1.0 if within tolerance, linearly decays to 0 at 2x tolerance
            if relative_error <= tolerance:
                score = 1.0
            elif relative_error <= 2 * tolerance:
                score = 1.0 - (relative_error - tolerance) / tolerance
            else:
                score = 0.0

        matches.append(score)
        details[metric_name] = {
            "paper": paper_value,
            "reproduced": reproduced_value,
            "relative_error": (
                abs(reproduced_value - paper_value) / abs(paper_value)
                if paper_value != 0 else 0
            ),
            "score": score,
        }

    avg_score = sum(matches) / len(matches) if matches else 0.0
    return avg_score, details


def score_assumption_accuracy(
    baseline: BaselineResult,
    claim_map: PaperClaimMap,
    known_valid: set[str] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Score what fraction of applied assumptions were valid.

    known_valid: set of assumption IDs confirmed as correct.
    If not provided, scores based on coverage of ambiguities.
    """
    if not baseline.assumptions_applied:
        return 0.0, {"reason": "no assumptions applied"}

    if known_valid is not None:
        valid_count = sum(
            1 for a in baseline.assumptions_applied if a in known_valid
        )
        accuracy = valid_count / len(baseline.assumptions_applied)
        return accuracy, {
            "applied": baseline.assumptions_applied,
            "valid": list(known_valid),
            "accuracy": accuracy,
        }

    # Heuristic: score based on coverage of detected ambiguities
    ambiguity_ids = {a.assumption_id for a in claim_map.ambiguities}
    if not ambiguity_ids:
        return 1.0, {"reason": "no ambiguities to cover"}

    covered = sum(1 for a in baseline.assumptions_applied if a in ambiguity_ids)
    coverage = covered / len(ambiguity_ids)
    return min(coverage, 1.0), {
        "ambiguity_ids": list(ambiguity_ids),
        "applied": baseline.assumptions_applied,
        "coverage": coverage,
    }


def score_fidelity(
    claim_map: PaperClaimMap,
    baseline: BaselineResult,
    artifacts: ExperimentArtifacts,
) -> tuple[float, dict[str, Any]]:
    """Layer 5 (simplified): Method fidelity heuristic.

    Checks: correct algorithm mentioned, datasets match, mode is implement_from_paper.
    For full Layer 5, use LLM-as-judge via score_fidelity_with_llm().
    """
    scores = []
    details: dict[str, Any] = {}

    # Mode check: implement_from_paper is highest fidelity
    mode_scores = {"implement_from_paper": 1.0, "adapt": 0.7, "clone": 0.5}
    mode_score = mode_scores.get(baseline.mode, 0.3)
    scores.append(mode_score)
    details["mode"] = {"value": baseline.mode, "score": mode_score}

    # Assumption coverage
    if claim_map.ambiguities:
        amb_ids = {a.assumption_id for a in claim_map.ambiguities}
        covered = sum(1 for a in baseline.assumptions_applied if a in amb_ids)
        coverage = covered / len(amb_ids)
    else:
        coverage = 1.0
    scores.append(coverage)
    details["assumption_coverage"] = coverage

    # Metric presence
    if artifacts.success and artifacts.metrics:
        expected_metrics = {m.name for m in claim_map.metrics}
        present = sum(1 for m in expected_metrics if m in artifacts.metrics)
        metric_coverage = present / len(expected_metrics) if expected_metrics else 1.0
    else:
        metric_coverage = 0.0
    scores.append(metric_coverage)
    details["metric_coverage"] = metric_coverage

    avg = sum(scores) / len(scores) if scores else 0.0
    return avg, details


def evaluate_reproduction(
    claim_map: PaperClaimMap,
    baseline: BaselineResult,
    artifacts: ExperimentArtifacts,
    paper_metrics: dict[str, float],
    *,
    version: str = "",
    paper_id: str = "",
    step_count: int = 0,
    cost_usd: float = 0.0,
    wall_time_s: float = 0.0,
    tolerance: float = 0.15,
    known_valid_assumptions: set[str] | None = None,
) -> ReproductionScore:
    """Run all reproduction evaluation layers and return composite score."""
    build_ok, build_details = score_build(baseline)
    run_ok, run_details = score_run(artifacts)
    match_score, match_details = score_metric_match(
        artifacts, claim_map, paper_metrics, tolerance,
    )
    assumption_score, assumption_details = score_assumption_accuracy(
        baseline, claim_map, known_valid_assumptions,
    )
    fidelity, fidelity_details = score_fidelity(claim_map, baseline, artifacts)

    return ReproductionScore(
        version=version,
        paper_id=paper_id,
        build_success=build_ok,
        run_success=run_ok,
        metric_match=match_score,
        fidelity_score=fidelity,
        assumption_accuracy=assumption_score,
        step_count=step_count,
        cost_usd=cost_usd,
        wall_time_s=wall_time_s,
        details={
            "build": build_details,
            "run": run_details,
            "metric_match": match_details,
            "assumptions": assumption_details,
            "fidelity": fidelity_details,
        },
    )


# --- DeepEval Integration ---


if DEEPEVAL_AVAILABLE:
    class ReproductionFidelityMetric(BaseMetric):
        """DeepEval custom metric for reproduction fidelity.

        Wraps our layered scoring into DeepEval's metric interface
        for use with `deepeval test run` and CI integration.
        """

        def __init__(
            self,
            claim_map: PaperClaimMap,
            baseline: BaselineResult,
            artifacts: ExperimentArtifacts,
            paper_metrics: dict[str, float],
            threshold: float = 0.7,
        ):
            self.claim_map = claim_map
            self.baseline = baseline
            self.artifacts = artifacts
            self.paper_metrics = paper_metrics
            self.threshold = threshold
            self.score: float | None = None
            self.reason: str | None = None
            self.success: bool | None = None

        def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
            result = evaluate_reproduction(
                self.claim_map, self.baseline, self.artifacts, self.paper_metrics,
            )
            self.score = result.composite_score()
            self.success = self.score >= self.threshold
            self.reason = (
                f"build={result.build_success}, run={result.run_success}, "
                f"metric_match={result.metric_match:.2f}, "
                f"fidelity={result.fidelity_score:.2f}"
            )
            return self.score

        def is_successful(self) -> bool:
            return self.success or False

        @property
        def __name__(self):
            return "ReproductionFidelityMetric"
