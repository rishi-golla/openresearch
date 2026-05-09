"""Tests for reproduction evaluation system."""

from pathlib import Path
import pytest

from backend.agents.schemas import (
    Ambiguity,
    BaselineResult,
    ExperimentArtifacts,
    MetricSpec,
    PaperClaimMap,
    RiskLevel,
)
from backend.evals.reproduction import (
    evaluate_reproduction,
    score_assumption_accuracy,
    score_build,
    score_fidelity,
    score_metric_match,
    score_run,
)
from backend.evals.schemas import ReproductionScore


def _claim_map():
    return PaperClaimMap(
        core_contribution="PPO",
        metrics=[
            MetricSpec(name="mean_reward", definition="Mean over 100 eps"),
            MetricSpec(name="std_reward", definition="Std over 100 eps"),
        ],
        ambiguities=[
            Ambiguity(assumption_id="A001", detail="epsilon", risk=RiskLevel.medium),
            Ambiguity(assumption_id="A002", detail="init", risk=RiskLevel.high),
            Ambiguity(assumption_id="A003", detail="lr schedule", risk=RiskLevel.low),
        ],
    )


def _baseline():
    return BaselineResult(
        mode="implement_from_paper",
        code_path="/code",
        dockerfile_path="/code/Dockerfile",
        commands_to_run=["python train.py"],
        assumptions_applied=["A001", "A002", "A003"],
    )


def _success_artifacts():
    return ExperimentArtifacts(
        metrics={"mean_reward": 487.3, "std_reward": 12.5},
        success=True,
    )


class TestScoreBuild:
    def test_success(self):
        ok, details = score_build(_baseline())
        assert ok is True
        assert details["has_dockerfile"] is True

    def test_failure_no_dockerfile(self):
        bl = BaselineResult(mode="adapt", code_path="/code")
        ok, _ = score_build(bl)
        assert ok is False

    def test_failure_no_code(self):
        bl = BaselineResult(mode="adapt", dockerfile_path="/Dockerfile")
        ok, _ = score_build(bl)
        assert ok is False


class TestScoreRun:
    def test_success(self):
        ok, _ = score_run(_success_artifacts())
        assert ok is True

    def test_failure(self):
        arts = ExperimentArtifacts(success=False, error_message="OOM")
        ok, details = score_run(arts)
        assert ok is False
        assert details["error"] == "OOM"


class TestScoreMetricMatch:
    def test_exact_match(self):
        paper = {"mean_reward": 487.3, "std_reward": 12.5}
        score, _ = score_metric_match(_success_artifacts(), _claim_map(), paper)
        assert score == 1.0

    def test_within_tolerance(self):
        paper = {"mean_reward": 500.0}  # 487.3 vs 500 = 2.5% off
        score, _ = score_metric_match(_success_artifacts(), _claim_map(), paper, tolerance=0.15)
        assert score == 1.0  # within 15%

    def test_outside_tolerance(self):
        paper = {"mean_reward": 1000.0}  # 487.3 vs 1000 = 51% off
        score, _ = score_metric_match(_success_artifacts(), _claim_map(), paper, tolerance=0.15)
        assert score == 0.0

    def test_partial_match(self):
        paper = {"mean_reward": 550.0}  # 487.3 vs 550 = 11.4% off
        score, _ = score_metric_match(_success_artifacts(), _claim_map(), paper, tolerance=0.10)
        # Between tolerance and 2*tolerance -> partial score
        assert 0 < score < 1.0

    def test_failed_experiment(self):
        arts = ExperimentArtifacts(success=False)
        score, _ = score_metric_match(arts, _claim_map(), {"mean_reward": 500})
        assert score == 0.0

    def test_missing_metric(self):
        paper = {"mean_reward": 487.3, "nonexistent": 100}
        score, details = score_metric_match(_success_artifacts(), _claim_map(), paper)
        # mean_reward matches, nonexistent is missing -> avg of 1.0 and 0.0
        assert score == 0.5


class TestScoreAssumptionAccuracy:
    def test_full_coverage(self):
        score, _ = score_assumption_accuracy(_baseline(), _claim_map())
        assert score == 1.0  # all 3 ambiguities covered

    def test_partial_coverage(self):
        bl = BaselineResult(mode="adapt", assumptions_applied=["A001"])
        score, _ = score_assumption_accuracy(bl, _claim_map())
        assert abs(score - 1/3) < 0.01

    def test_with_known_valid(self):
        score, _ = score_assumption_accuracy(
            _baseline(), _claim_map(), known_valid={"A001", "A002"},
        )
        assert abs(score - 2/3) < 0.01

    def test_no_assumptions(self):
        bl = BaselineResult(mode="adapt", assumptions_applied=[])
        score, _ = score_assumption_accuracy(bl, _claim_map())
        assert score == 0.0


class TestScoreFidelity:
    def test_high_fidelity(self):
        score, _ = score_fidelity(_claim_map(), _baseline(), _success_artifacts())
        assert score >= 0.8

    def test_low_fidelity_adapt_mode(self):
        bl = BaselineResult(mode="adapt", assumptions_applied=[])
        arts = ExperimentArtifacts(success=True, metrics={})
        score, _ = score_fidelity(_claim_map(), bl, arts)
        assert score < 0.5


class TestEvaluateReproduction:
    def test_full_evaluation(self):
        paper_metrics = {"mean_reward": 487.3, "std_reward": 12.5}
        result = evaluate_reproduction(
            _claim_map(), _baseline(), _success_artifacts(), paper_metrics,
            version="v1.0", paper_id="ppo",
        )
        assert isinstance(result, ReproductionScore)
        assert result.build_success is True
        assert result.run_success is True
        assert result.metric_match == 1.0
        assert result.composite_score() > 0.8
        assert result.version == "v1.0"

    def test_failed_reproduction(self):
        arts = ExperimentArtifacts(success=False, error_message="crash")
        bl = BaselineResult(mode="adapt")
        result = evaluate_reproduction(
            _claim_map(), bl, arts, {"mean_reward": 500},
        )
        assert result.build_success is False
        assert result.run_success is False
        assert result.composite_score() < 0.3

    def test_has_details(self):
        result = evaluate_reproduction(
            _claim_map(), _baseline(), _success_artifacts(),
            {"mean_reward": 487.3},
        )
        assert "build" in result.details
        assert "run" in result.details
        assert "metric_match" in result.details
        assert "fidelity" in result.details
