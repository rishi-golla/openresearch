"""Tests for innovation evaluation system."""

import pytest

from backend.agents.schemas import (
    ImprovementHypothesis,
    PaperClaimMap,
    PathResult,
    ResearchMap,
)
from backend.evals.innovation import (
    check_metric_consistency,
    check_selective_reporting,
    check_variable_isolation,
    evaluate_innovation_offline,
    parse_hypothesis_llm_response,
    score_hypothesis_offline,
    score_hypothesis_with_llm_prompt,
    score_research_map_offline,
)
from backend.evals.schemas import (
    HypothesisScore,
    IntegrityFlag,
    IntegrityReport,
    InnovationScore,
    ResearchMapScore,
)


def _hypothesis(path_id="path_1", text="Tune entropy coefficient from 0.01 to 0.005"):
    return ImprovementHypothesis(
        path_id=path_id,
        hypothesis=text,
        rationale="Entropy coefficient controls exploration. Reducing it after initial "
                  "exploration phase may allow more exploitation and higher rewards.",
        expected_outcome="Reward improvement of 5-10 points",
    )


def _structural_hypothesis():
    return ImprovementHypothesis(
        path_id="path_2",
        hypothesis="Use separate actor-critic networks instead of shared backbone",
        rationale="Shared networks create gradient interference between policy and value objectives",
        expected_outcome="Better value estimation, possibly at cost of sample efficiency",
    )


def _claim_map():
    return PaperClaimMap(core_contribution="PPO")


# --- Hypothesis Scoring ---


class TestHypothesisScoring:
    def test_param_sweep_scores_low_novelty(self):
        h = ImprovementHypothesis(
            path_id="p1",
            hypothesis="Try learning rate 1e-3 instead of 3e-4",
            rationale="reason",
            expected_outcome="better",
        )
        score = score_hypothesis_offline(h)
        assert score.novelty <= 2

    def test_structural_change_scores_high_novelty(self):
        score = score_hypothesis_offline(_structural_hypothesis())
        assert score.novelty >= 4

    def test_scores_are_1_to_5(self):
        score = score_hypothesis_offline(_hypothesis())
        assert 1 <= score.novelty <= 5
        assert 1 <= score.feasibility <= 5
        assert 1 <= score.significance <= 5
        assert 1 <= score.clarity <= 5
        assert 1 <= score.actionability <= 5

    def test_mean_score(self):
        score = score_hypothesis_offline(_hypothesis())
        expected = (score.novelty + score.feasibility + score.significance
                    + score.clarity + score.actionability) / 5.0
        assert score.mean_score() == expected

    def test_above_baseline_check(self):
        score = score_hypothesis_offline(_structural_hypothesis())
        # Structural change should be above baseline
        assert score.is_above_baseline(threshold=2.5)

    def test_llm_prompt_generation(self):
        prompt = score_hypothesis_with_llm_prompt(_hypothesis(), _claim_map())
        assert "NOVELTY" in prompt
        assert "FEASIBILITY" in prompt
        assert "entropy" in prompt.lower()

    def test_llm_response_parsing(self):
        response = """
NOVELTY: 3
FEASIBILITY: 5
SIGNIFICANCE: 2
CLARITY: 4
ACTIONABILITY: 4
The hypothesis is specific but not very novel.
"""
        score = parse_hypothesis_llm_response(response, _hypothesis())
        assert score.novelty == 3
        assert score.feasibility == 5
        assert score.significance == 2
        assert score.clarity == 4
        assert score.actionability == 4


# --- Integrity Checks ---


class TestVariableIsolation:
    def test_single_variable_passes(self):
        p = PathResult(
            path_id="p1", hypothesis="Reduce entropy coefficient",
            success=True, metrics={"mean_reward": 495},
        )
        report = check_variable_isolation(p, {"mean_reward": 487})
        assert report.passed is True
        assert IntegrityFlag.multi_variable_change not in report.flags

    def test_multi_variable_flagged(self):
        p = PathResult(
            path_id="p1",
            hypothesis="Increase batch size and also change learning rate",
            success=True, metrics={"mean_reward": 500},
        )
        report = check_variable_isolation(p, {"mean_reward": 487})
        assert report.passed is False
        assert IntegrityFlag.multi_variable_change in report.flags

    def test_multiple_params_detected(self):
        p = PathResult(
            path_id="p1",
            hypothesis="Change entropy and batch size and learning rate",
            success=True, metrics={"mean_reward": 500},
        )
        report = check_variable_isolation(p, {"mean_reward": 487})
        assert len(report.variables_changed) >= 2

    def test_suspiciously_uniform_improvement(self):
        p = PathResult(
            path_id="p1", hypothesis="Magic improvement",
            success=True,
            metrics={"a": 100, "b": 200, "c": 300},
        )
        baseline = {"a": 50, "b": 100, "c": 150}  # all doubled
        report = check_variable_isolation(p, baseline)
        assert IntegrityFlag.data_leakage in report.flags


class TestMetricConsistency:
    def test_consistent_metrics_pass(self):
        p = PathResult(
            path_id="p1", hypothesis="test",
            success=True, metrics={"mean_reward": 495.0},
        )
        report = check_metric_consistency(p, rerun_metrics={"mean_reward": 494.5})
        assert report.passed is True
        assert report.metric_deviation < 0.05

    def test_inconsistent_metrics_flagged(self):
        p = PathResult(
            path_id="p1", hypothesis="test",
            success=True, metrics={"mean_reward": 495.0},
        )
        report = check_metric_consistency(p, rerun_metrics={"mean_reward": 400.0})
        assert report.passed is False
        assert IntegrityFlag.metric_inconsistency in report.flags

    def test_success_without_metrics_flagged(self):
        p = PathResult(
            path_id="p1", hypothesis="test",
            success=True, metrics={},
        )
        report = check_metric_consistency(p)
        assert IntegrityFlag.selective_reporting in report.flags

    def test_no_rerun_data_structural_only(self):
        p = PathResult(
            path_id="p1", hypothesis="test",
            success=True, metrics={"mean_reward": 495.0},
        )
        report = check_metric_consistency(p)
        assert report.passed is True  # no rerun data, structural check passes


class TestSelectiveReporting:
    def test_consistent_reporting_passes(self):
        paths = [
            PathResult(path_id="p1", hypothesis="h1", success=True,
                       metrics={"reward": 500, "loss": 0.1}),
            PathResult(path_id="p2", hypothesis="h2", success=True,
                       metrics={"reward": 490, "loss": 0.2}),
        ]
        reports = check_selective_reporting(paths, {"reward": 487})
        assert all(r.passed for r in reports)

    def test_selective_reporting_flagged(self):
        paths = [
            PathResult(path_id="p1", hypothesis="h1", success=True,
                       metrics={"reward": 500, "loss": 0.1, "steps": 1000}),
            PathResult(path_id="p2", hypothesis="h2", success=True,
                       metrics={"reward": 490}),  # missing loss and steps
        ]
        reports = check_selective_reporting(paths, {"reward": 487})
        # p2 is missing >50% of metrics that p1 reports
        assert any(not r.passed for r in reports)


# --- Research Map Scoring ---


class TestResearchMapScoring:
    def _map_and_results(self):
        paths = [
            PathResult(path_id="path_1", hypothesis="entropy tuning",
                       success=True, metrics={"mean_reward": 495, "improvement": 8}),
            PathResult(path_id="path_2", hypothesis="separate networks",
                       success=True, metrics={"mean_reward": 475, "improvement": -12}),
            PathResult(path_id="path_3", hypothesis="lambda tuning",
                       success=False, failure_notes="diverged"),
        ]
        rmap = ResearchMap(
            baseline_summary="PPO baseline: 487 reward",
            promising_directions=["path_1: entropy tuning (reward=495)"],
            dead_ends=["path_2: separate networks (reward=475)"],
            inconclusive=["path_3: lambda tuning (diverged)"],
            next_experiments=["Combine entropy tuning with baseline",
                              "Test on Hopper environment",
                              "Run for full 500k steps"],
            overall_reproducibility_assessment="Baseline verified. 1 promising, 1 dead end.",
        )
        return rmap, paths

    def test_classification_accuracy(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        # path_1 correctly classified as promising (improvement > 0)
        # path_2 correctly classified as dead end (improvement < 0)
        assert score.classification_accuracy == 1.0

    def test_direction_validity(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        assert score.direction_validity == 1.0  # path_1 has improvement > 0

    def test_negative_result_honesty(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        # 2 negatives (path_2 regression + path_3 failure), both documented
        assert score.negative_result_honesty == 1.0

    def test_next_experiment_novelty(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        # "Run for full 500k steps" contains "run longer" pattern → not novel
        # Other two are novel
        assert score.next_experiment_novelty > 0.5

    def test_synthesis_quality(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        assert score.synthesis_quality == 1.0  # has baseline_summary + assessment

    def test_composite_score(self):
        rmap, paths = self._map_and_results()
        score = score_research_map_offline(rmap, paths, {"mean_reward": 487})
        assert 0.5 < score.composite_score() <= 1.0


# --- Full Innovation Evaluation ---


class TestEvaluateInnovationOffline:
    def test_full_evaluation(self):
        hypotheses = [_hypothesis("path_1"), _structural_hypothesis()]
        paths = [
            PathResult(path_id="path_1", hypothesis="entropy tuning",
                       success=True, metrics={"mean_reward": 495, "improvement": 8}),
            PathResult(path_id="path_2", hypothesis="separate networks",
                       success=True, metrics={"mean_reward": 475, "improvement": -12}),
        ]
        rmap = ResearchMap(
            baseline_summary="PPO baseline",
            promising_directions=["path_1: better"],
            dead_ends=["path_2: worse"],
            next_experiments=["Try new optimizer"],
            overall_reproducibility_assessment="OK",
        )
        score = evaluate_innovation_offline(
            hypotheses, paths, rmap, {"mean_reward": 487},
            version="v1.0", paper_id="ppo",
        )
        assert isinstance(score, InnovationScore)
        assert score.version == "v1.0"
        assert len(score.hypothesis_scores) == 2
        assert len(score.integrity_reports) == 2
        assert score.research_map_score is not None
        assert score.mean_hypothesis_quality() > 0
        assert score.integrity_pass_rate() >= 0
