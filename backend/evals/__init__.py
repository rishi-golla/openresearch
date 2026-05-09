"""ReproLab Evaluation System.

Two evaluation surfaces:
  1. Reproduction — ground-truth-based (DeepEval integration, Bayesian A/B testing)
  2. Innovation — judgment-based (hypothesis rubric, integrity checks, research map scoring, Elo)

Usage:
    from backend.evals import EvalRunner, EvalStore
    from backend.evals.sources import EVAL_SOURCES, format_all_citations

    store = EvalStore("evals.db")
    runner = EvalRunner(store=store)
    repro_score = runner.evaluate_reproduction(state, paper_metrics, version="v1.0")
    innov_score = runner.evaluate_innovation(state, version="v1.0")
"""

from backend.evals.schemas import (
    ABTestResult,
    EloMatchResult,
    EloRating,
    EvalMode,
    EvalRun,
    HypothesisScore,
    InnovationScore,
    IntegrityFlag,
    IntegrityReport,
    ReproductionScore,
    ResearchMapScore,
)
from backend.evals.store import EvalStore
from backend.evals.runner import EvalRunner

__all__ = [
    "ABTestResult",
    "EloMatchResult",
    "EloRating",
    "EvalMode",
    "EvalRun",
    "EvalRunner",
    "EvalStore",
    "HypothesisScore",
    "InnovationScore",
    "IntegrityFlag",
    "IntegrityReport",
    "ReproductionScore",
    "ResearchMapScore",
]
