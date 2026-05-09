"""Eval runner — orchestrates reproduction and innovation evaluation.

Usage:
    # Run reproduction eval on a completed pipeline
    runner = EvalRunner(store=EvalStore("evals.db"))
    repro_score = runner.evaluate_reproduction(state, paper_metrics, version="v1.0")

    # Run innovation eval
    innov_score = runner.evaluate_innovation(state, version="v1.0")

    # A/B test two versions
    result = runner.run_ab_test("v1.0", "v1.1", paper_ids=["ppo", "mixmatch"])

    # Elo tournament
    rankings = runner.run_elo_tournament(["v1.0", "v1.1", "v2.0"], paper_ids=["ppo"])
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from backend.agents.orchestrator import PipelineState
from backend.agents.schemas import PaperClaimMap
from backend.evals.ab_testing import BayesianABTest, MultiMetricABTest
from backend.evals.elo import EloTournament
from backend.evals.innovation import evaluate_innovation_offline
from backend.evals.reproduction import evaluate_reproduction
from backend.evals.schemas import (
    ABTestResult,
    EloRating,
    InnovationScore,
    ReproductionScore,
)
from backend.evals.store import EvalStore


class EvalRunner:
    """Orchestrates evaluation of pipeline runs."""

    def __init__(self, store: EvalStore | None = None):
        self.store = store

    def evaluate_reproduction(
        self,
        state: PipelineState,
        paper_metrics: dict[str, float],
        *,
        version: str = "",
        paper_id: str = "",
        step_count: int = 0,
        cost_usd: float = 0.0,
        wall_time_s: float = 0.0,
        tolerance: float = 0.15,
    ) -> ReproductionScore:
        """Evaluate reproduction quality from a completed pipeline state."""
        if state.paper_claim_map is None:
            raise ValueError("Pipeline state has no paper_claim_map")
        if state.baseline_result is None:
            raise ValueError("Pipeline state has no baseline_result")
        if state.experiment_artifacts is None:
            raise ValueError("Pipeline state has no experiment_artifacts")

        score = evaluate_reproduction(
            claim_map=state.paper_claim_map,
            baseline=state.baseline_result,
            artifacts=state.experiment_artifacts,
            paper_metrics=paper_metrics,
            version=version,
            paper_id=paper_id or state.project_id,
            step_count=step_count,
            cost_usd=cost_usd,
            wall_time_s=wall_time_s,
            tolerance=tolerance,
        )

        if self.store:
            self.store.save_reproduction(score)

        return score

    def evaluate_innovation(
        self,
        state: PipelineState,
        *,
        version: str = "",
        paper_id: str = "",
    ) -> InnovationScore:
        """Evaluate innovation quality from a completed pipeline state."""
        if not state.improvement_hypotheses:
            raise ValueError("Pipeline state has no improvement_hypotheses")
        if state.research_map is None:
            raise ValueError("Pipeline state has no research_map")
        if state.experiment_artifacts is None:
            raise ValueError("Pipeline state has no experiment_artifacts")

        baseline_metrics = state.experiment_artifacts.metrics or {}

        score = evaluate_innovation_offline(
            hypotheses=state.improvement_hypotheses,
            path_results=state.path_results,
            research_map=state.research_map,
            baseline_metrics=baseline_metrics,
            claim_map=state.paper_claim_map,
            version=version,
            paper_id=paper_id or state.project_id,
        )

        if self.store:
            self.store.save_innovation(score)

        return score

    def evaluate_full(
        self,
        state: PipelineState,
        paper_metrics: dict[str, float],
        *,
        version: str = "",
        paper_id: str = "",
        step_count: int = 0,
        cost_usd: float = 0.0,
        wall_time_s: float = 0.0,
    ) -> tuple[ReproductionScore, InnovationScore]:
        """Run both reproduction and innovation evaluation."""
        repro = self.evaluate_reproduction(
            state, paper_metrics,
            version=version, paper_id=paper_id,
            step_count=step_count, cost_usd=cost_usd, wall_time_s=wall_time_s,
        )
        innov = self.evaluate_innovation(state, version=version, paper_id=paper_id)
        return repro, innov

    def run_ab_test(
        self,
        version_a: str,
        version_b: str,
        scores_a: list[ReproductionScore],
        scores_b: list[ReproductionScore],
        *,
        significance_threshold: float = 0.95,
        seed: int | None = 42,
    ) -> dict[str, ABTestResult]:
        """Run Bayesian A/B test between two versions using collected scores."""
        ab = MultiMetricABTest(
            version_a, version_b,
            significance_threshold=significance_threshold,
            seed=seed,
        )

        # Register metrics
        ab.register_metric("build_success", is_binary=True)
        ab.register_metric("run_success", is_binary=True)
        ab.register_metric("metric_match", is_binary=False)
        ab.register_metric("fidelity_score", is_binary=False)
        ab.register_metric("composite", is_binary=False)

        # Add observations
        for s in scores_a:
            ab.add_observation_a({
                "build_success": s.build_success,
                "run_success": s.run_success,
                "metric_match": s.metric_match,
                "fidelity_score": s.fidelity_score,
                "composite": s.composite_score(),
            })
        for s in scores_b:
            ab.add_observation_b({
                "build_success": s.build_success,
                "run_success": s.run_success,
                "metric_match": s.metric_match,
                "fidelity_score": s.fidelity_score,
                "composite": s.composite_score(),
            })

        results = ab.results()

        # Save to store
        if self.store:
            for result in results.values():
                self.store.save_ab_test(result)

        return results

    def run_elo_tournament(
        self,
        versions: list[str],
        match_fn: Any,  # Callable[[str, str], str | None]
        *,
        paper_ids: list[str] | None = None,
        n_rounds: int = 1,
        seed: int | None = 42,
    ) -> list[EloRating]:
        """Run Elo tournament between agent versions.

        match_fn(version_a, version_b) -> winner version string or None for draw.
        """
        tournament = EloTournament()
        for v in versions:
            tournament.add_competitor(v)

        tournament.run_round_robin(
            match_fn, paper_ids=paper_ids,
            n_rounds=n_rounds, seed=seed,
        )

        rankings = tournament.get_rankings()

        # Save to store
        if self.store:
            for rating in rankings:
                self.store.save_elo_rating(rating)

        return rankings

    def version_comparison(self, version_a: str, version_b: str) -> dict[str, Any]:
        """Get side-by-side comparison of two versions from stored results."""
        if not self.store:
            return {"error": "no store configured"}

        summary_a = self.store.get_version_summary(version_a)
        summary_b = self.store.get_version_summary(version_b)

        return {
            "version_a": summary_a,
            "version_b": summary_b,
            "ab_tests": [
                r.model_dump()
                for r in self.store.get_ab_tests(version_a, version_b)
            ],
        }


def print_reproduction_report(score: ReproductionScore) -> None:
    """Print a human-readable reproduction evaluation report."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"REPRODUCTION EVALUATION — {score.paper_id} (version: {score.version})", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  Build success:        {'PASS' if score.build_success else 'FAIL'}", file=sys.stderr)
    print(f"  Run success:          {'PASS' if score.run_success else 'FAIL'}", file=sys.stderr)
    print(f"  Metric match:         {score.metric_match:.2f}", file=sys.stderr)
    print(f"  Fidelity score:       {score.fidelity_score:.2f}", file=sys.stderr)
    print(f"  Assumption accuracy:  {score.assumption_accuracy:.2f}", file=sys.stderr)
    print(f"  Steps:                {score.step_count}", file=sys.stderr)
    print(f"  Cost:                 ${score.cost_usd:.2f}", file=sys.stderr)
    print(f"  Wall time:            {score.wall_time_s:.1f}s", file=sys.stderr)
    print(f"  ---", file=sys.stderr)
    print(f"  COMPOSITE SCORE:      {score.composite_score():.3f}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)


def print_innovation_report(score: InnovationScore) -> None:
    """Print a human-readable innovation evaluation report."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"INNOVATION EVALUATION — {score.paper_id} (version: {score.version})", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  Mean hypothesis quality: {score.mean_hypothesis_quality():.2f}/5.0", file=sys.stderr)
    print(f"  Integrity pass rate:     {score.integrity_pass_rate():.0%}", file=sys.stderr)
    if score.research_map_score:
        rm = score.research_map_score
        print(f"  Research Map composite:  {rm.composite_score():.2f}", file=sys.stderr)
        print(f"    Classification:        {rm.classification_accuracy:.2f}", file=sys.stderr)
        print(f"    Direction validity:     {rm.direction_validity:.2f}", file=sys.stderr)
        print(f"    Next-exp novelty:      {rm.next_experiment_novelty:.2f}", file=sys.stderr)
        print(f"    Negative honesty:      {rm.negative_result_honesty:.2f}", file=sys.stderr)
        print(f"    Synthesis quality:     {rm.synthesis_quality:.2f}", file=sys.stderr)
        print(f"    Actionability:         {rm.actionability:.2f}", file=sys.stderr)
    for h in score.hypothesis_scores:
        print(f"  [{h.hypothesis_id}] mean={h.mean_score():.1f} "
              f"(N={h.novelty} F={h.feasibility} S={h.significance} "
              f"C={h.clarity} A={h.actionability})", file=sys.stderr)
    for r in score.integrity_reports:
        status = "PASS" if r.passed else f"FAIL ({', '.join(f.value for f in r.flags)})"
        print(f"  [{r.path_id}] integrity: {status}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
