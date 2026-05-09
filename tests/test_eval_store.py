"""Tests for evaluation SQLite store."""

from pathlib import Path
import pytest

from backend.evals.schemas import (
    ABTestResult,
    EloRating,
    HypothesisScore,
    InnovationScore,
    IntegrityReport,
    ReproductionScore,
    ResearchMapScore,
)
from backend.evals.store import EvalStore


@pytest.fixture
def store(tmp_path: Path):
    s = EvalStore(tmp_path / "test_evals.db")
    yield s
    s.close()


class TestReproductionStorage:
    def test_save_and_retrieve(self, store: EvalStore):
        score = ReproductionScore(
            version="v1.0", paper_id="ppo",
            build_success=True, run_success=True,
            metric_match=0.95, fidelity_score=0.88,
            assumption_accuracy=0.75, step_count=42,
            cost_usd=1.50, wall_time_s=120.0,
        )
        run_id = store.save_reproduction(score)
        assert run_id

        rows = store.get_reproduction_scores(version="v1.0")
        assert len(rows) == 1
        assert rows[0]["paper_id"] == "ppo"
        assert rows[0]["build_success"] == 1
        assert rows[0]["metric_match"] == 0.95

    def test_filter_by_paper(self, store: EvalStore):
        for pid in ["ppo", "mixmatch", "ppo"]:
            store.save_reproduction(ReproductionScore(
                version="v1.0", paper_id=pid,
                build_success=True, run_success=True,
            ))

        ppo_rows = store.get_reproduction_scores(paper_id="ppo")
        assert len(ppo_rows) == 2

    def test_composite_stored(self, store: EvalStore):
        score = ReproductionScore(
            version="v1.0", paper_id="ppo",
            build_success=True, run_success=True,
            metric_match=1.0, fidelity_score=0.9,
        )
        store.save_reproduction(score)
        rows = store.get_reproduction_scores()
        assert rows[0]["composite"] == score.composite_score()


class TestInnovationStorage:
    def test_save_and_retrieve(self, store: EvalStore):
        score = InnovationScore(
            version="v1.0", paper_id="ppo",
            hypothesis_scores=[
                HypothesisScore(hypothesis_id="p1", novelty=3, feasibility=4,
                                significance=3, clarity=4, actionability=3),
            ],
            integrity_reports=[
                IntegrityReport(path_id="p1", passed=True),
            ],
            research_map_score=ResearchMapScore(
                classification_accuracy=0.9, direction_validity=0.8,
            ),
        )
        run_id = store.save_innovation(score)
        assert run_id

        rows = store.get_innovation_scores(version="v1.0")
        assert len(rows) == 1
        assert rows[0]["mean_hypothesis_quality"] == score.mean_hypothesis_quality()


class TestEloStorage:
    def test_save_and_retrieve(self, store: EvalStore):
        rating = EloRating(
            version="v1.0", rating=1550, matches_played=10,
            wins=7, losses=2, draws=1,
        )
        store.save_elo_rating(rating)

        ratings = store.get_elo_ratings()
        assert len(ratings) == 1
        assert ratings[0].version == "v1.0"
        assert ratings[0].rating == 1550

    def test_sorted_by_rating(self, store: EvalStore):
        for v, r in [("v1", 1400), ("v2", 1600), ("v3", 1500)]:
            store.save_elo_rating(EloRating(version=v, rating=r))

        ratings = store.get_elo_ratings()
        assert ratings[0].version == "v2"
        assert ratings[-1].version == "v1"


class TestABTestStorage:
    def test_save_and_retrieve(self, store: EvalStore):
        result = ABTestResult(
            version_a="v1", version_b="v2", metric="build_success",
            n_a=10, n_b=10, mean_a=0.9, mean_b=0.5,
            p_a_better=0.97, p_b_better=0.03,
            is_significant=True, winner="v1",
        )
        test_id = store.save_ab_test(result)
        assert test_id

        tests = store.get_ab_tests(version_a="v1")
        assert len(tests) == 1
        assert tests[0].winner == "v1"
        assert tests[0].p_a_better == 0.97


class TestVersionSummary:
    def test_summary_aggregates(self, store: EvalStore):
        for mm in [0.8, 0.9, 1.0]:
            store.save_reproduction(ReproductionScore(
                version="v1.0", paper_id="ppo",
                build_success=True, run_success=True,
                metric_match=mm, fidelity_score=0.85,
            ))

        summary = store.get_version_summary("v1.0")
        assert summary["reproduction_runs"] == 3
        assert abs(summary["mean_metric_match"] - 0.9) < 0.01
        assert summary["build_success_rate"] == 1.0

    def test_empty_version(self, store: EvalStore):
        summary = store.get_version_summary("nonexistent")
        assert summary["reproduction_runs"] == 0
        assert summary["mean_composite"] == 0
