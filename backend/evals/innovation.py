"""Innovation evaluation — scores hypothesis quality, experiment integrity, research map.

No ground truth exists for innovation. We use:
1. LLM-as-judge rubrics (with offline deterministic fallback)
2. Structural integrity checks (automated)
3. Consistency verification (automated)
"""

from __future__ import annotations

from typing import Any

from backend.agents.schemas import (
    ImprovementHypothesis,
    PaperClaimMap,
    PathResult,
    ResearchMap,
)
from backend.evals.schemas import (
    HypothesisScore,
    InnovationScore,
    IntegrityFlag,
    IntegrityReport,
    ResearchMapScore,
)


# --- Hypothesis Quality Evaluation ---


HYPOTHESIS_RUBRIC = """Rate this hypothesis on 5 dimensions (1-5 each):

1. NOVELTY (1=pure parameter sweep, 5=structural algorithmic insight)
   - 1: "Try lr=1e-3 instead of 3e-4" (just changing a number)
   - 3: "Use cosine annealing instead of linear LR schedule" (known technique, new application)
   - 5: "Replace policy gradient with implicit differentiation through environment model"

2. FEASIBILITY (1=requires resources/data we don't have, 5=immediately testable)
   - 1: Requires 1000 GPU-hours or proprietary data
   - 3: Requires moderate compute or additional libraries
   - 5: Can test with a one-line code change in existing setup

3. SIGNIFICANCE (1=trivial effect expected, 5=could change conclusions)
   - 1: Might improve reward by 0.1%
   - 3: Could improve by 5-15%
   - 5: Could fundamentally change how the algorithm works

4. CLARITY (1=vague, 5=precisely stated with clear success criteria)
   - 1: "Make it better somehow"
   - 3: "Increase batch size" (clear but no success criteria)
   - 5: "Reduce entropy coeff from 0.01 to 0.005; success = reward > 495 within 500k steps"

5. ACTIONABILITY (1=no clear implementation path, 5=obvious code change)
   - 1: "Explore alternative paradigms"
   - 3: "Try a different optimizer" (which one?)
   - 5: "Change line 42: entropy_coef=0.005"

Hypothesis: {hypothesis}
Rationale: {rationale}
Context: {context}
"""


def score_hypothesis_offline(
    hypothesis: ImprovementHypothesis,
    claim_map: PaperClaimMap | None = None,
) -> HypothesisScore:
    """Deterministic hypothesis scoring using heuristics.

    Used for testing. For real evaluation, use score_hypothesis_with_llm().
    """
    text = hypothesis.hypothesis.lower()

    # Novelty: penalize pure parameter changes
    param_keywords = ["learning rate", "lr", "batch size", "epochs", "steps"]
    structural_keywords = ["network", "architecture", "algorithm", "loss function", "objective"]
    novelty = 2  # default
    if any(k in text for k in structural_keywords):
        novelty = 4
    elif any(k in text for k in param_keywords):
        novelty = 2
    elif len(text) > 80:  # longer = more complex idea
        novelty = 3

    # Feasibility: assume most offline hypotheses are feasible
    feasibility = 4

    # Significance: based on expected outcome language
    significance = 3
    if "fundamental" in text or "paradigm" in text:
        significance = 5
    elif "marginal" in text or "slight" in text:
        significance = 2

    # Clarity: based on specificity
    clarity = 3
    if any(c.isdigit() for c in hypothesis.hypothesis):
        clarity = 4  # has specific numbers
    if hypothesis.expected_outcome and len(hypothesis.expected_outcome) > 20:
        clarity = min(clarity + 1, 5)

    # Actionability: based on rationale length and specificity
    actionability = 3
    if hypothesis.rationale and len(hypothesis.rationale) > 50:
        actionability = 4

    return HypothesisScore(
        hypothesis_id=hypothesis.path_id,
        hypothesis_text=hypothesis.hypothesis,
        novelty=novelty,
        feasibility=feasibility,
        significance=significance,
        clarity=clarity,
        actionability=actionability,
        rationale="Scored via offline heuristics",
    )


def score_hypothesis_with_llm_prompt(
    hypothesis: ImprovementHypothesis,
    claim_map: PaperClaimMap | None = None,
    context: str = "",
) -> str:
    """Generate the LLM prompt for hypothesis scoring.

    Returns the prompt to send to an LLM. Parse the response with
    parse_hypothesis_llm_response().
    """
    return HYPOTHESIS_RUBRIC.format(
        hypothesis=hypothesis.hypothesis,
        rationale=hypothesis.rationale,
        context=context or (claim_map.core_contribution if claim_map else ""),
    )


def parse_hypothesis_llm_response(
    response: str,
    hypothesis: ImprovementHypothesis,
) -> HypothesisScore:
    """Parse LLM response into HypothesisScore.

    Expects response to contain lines like:
    NOVELTY: 3
    FEASIBILITY: 4
    etc.
    """
    scores: dict[str, int] = {}
    for line in response.strip().split("\n"):
        line = line.strip().upper()
        for dim in ("NOVELTY", "FEASIBILITY", "SIGNIFICANCE", "CLARITY", "ACTIONABILITY"):
            if line.startswith(dim):
                try:
                    val = int("".join(c for c in line.split(":")[-1] if c.isdigit())[:1])
                    scores[dim.lower()] = max(1, min(5, val))
                except (ValueError, IndexError):
                    pass

    return HypothesisScore(
        hypothesis_id=hypothesis.path_id,
        hypothesis_text=hypothesis.hypothesis,
        novelty=scores.get("novelty", 3),
        feasibility=scores.get("feasibility", 3),
        significance=scores.get("significance", 3),
        clarity=scores.get("clarity", 3),
        actionability=scores.get("actionability", 3),
        rationale=response[:500],
    )


# --- Integrity Checks ---


def check_variable_isolation(
    path_result: PathResult,
    baseline_metrics: dict[str, float],
) -> IntegrityReport:
    """Check if the experiment changed only one variable.

    Flags multi-variable changes that make results uninterpretable.
    """
    flags: list[IntegrityFlag] = []
    variables_changed: list[str] = []

    # Analyze hypothesis text for multiple changes
    hypothesis_lower = path_result.hypothesis.lower()
    change_indicators = [
        "and", "also", "additionally", "plus", "combined with",
        "together with", "along with",
    ]

    multi_change = any(ind in hypothesis_lower for ind in change_indicators)
    if multi_change:
        flags.append(IntegrityFlag.multi_variable_change)

    # Check for specific parameter mentions
    params = ["learning rate", "batch size", "entropy", "lambda", "gamma",
              "epochs", "hidden", "layers", "optimizer", "network"]
    for p in params:
        if p in hypothesis_lower:
            variables_changed.append(p)

    if len(variables_changed) > 1:
        if IntegrityFlag.multi_variable_change not in flags:
            flags.append(IntegrityFlag.multi_variable_change)

    # Check metric consistency
    if path_result.success and path_result.metrics:
        # If all metrics improved uniformly, suspicious (might be data leakage)
        improvements = []
        for key, val in path_result.metrics.items():
            if key in baseline_metrics and baseline_metrics[key] != 0:
                pct = (val - baseline_metrics[key]) / abs(baseline_metrics[key])
                improvements.append(pct)

        # All metrics improved by > 20% — suspicious
        if improvements and all(i > 0.2 for i in improvements) and len(improvements) > 2:
            flags.append(IntegrityFlag.data_leakage)

    passed = len(flags) == 0
    return IntegrityReport(
        path_id=path_result.path_id,
        flags=flags,
        variables_changed=variables_changed,
        reported_metrics=path_result.metrics or {},
        passed=passed,
        details=f"Changed {len(variables_changed)} variables" if variables_changed else "Clean",
    )


def check_metric_consistency(
    path_result: PathResult,
    rerun_metrics: dict[str, float] | None = None,
    tolerance: float = 0.05,
) -> IntegrityReport:
    """Check if reported metrics match re-execution.

    If rerun_metrics not provided, performs structural checks only.
    """
    flags: list[IntegrityFlag] = []
    deviation = 0.0

    if rerun_metrics and path_result.metrics:
        for key in path_result.metrics:
            if key in rerun_metrics:
                reported = path_result.metrics[key]
                rerun = rerun_metrics[key]
                if reported != 0:
                    dev = abs(reported - rerun) / abs(reported)
                    deviation = max(deviation, dev)
                    if dev > tolerance:
                        flags.append(IntegrityFlag.metric_inconsistency)
                        break

    # Structural check: success claimed but no metrics
    if path_result.success and not path_result.metrics:
        flags.append(IntegrityFlag.selective_reporting)

    # Structural check: failure claimed but has good metrics
    if not path_result.success and path_result.metrics:
        good_metrics = sum(1 for v in path_result.metrics.values()
                          if isinstance(v, (int, float)) and v > 0)
        if good_metrics > 2:
            flags.append(IntegrityFlag.selective_reporting)

    return IntegrityReport(
        path_id=path_result.path_id,
        flags=flags,
        reported_metrics=path_result.metrics or {},
        rerun_metrics=rerun_metrics or {},
        metric_deviation=deviation,
        passed=len(flags) == 0,
        details=f"Max deviation: {deviation:.3f}" if deviation > 0 else "Consistent",
    )


def check_selective_reporting(
    path_results: list[PathResult],
    baseline_metrics: dict[str, float],
) -> list[IntegrityReport]:
    """Check across all paths for selective metric reporting.

    Flags if paths report different metrics (cherry-picking which to show).
    """
    reports = []
    all_metric_keys = set()
    for p in path_results:
        if p.metrics:
            all_metric_keys.update(p.metrics.keys())

    for p in path_results:
        flags: list[IntegrityFlag] = []
        if p.metrics and all_metric_keys:
            reported_keys = set(p.metrics.keys())
            missing_keys = all_metric_keys - reported_keys
            # If this path is missing metrics that others report, flag it
            if len(missing_keys) > len(reported_keys) * 0.5:
                flags.append(IntegrityFlag.selective_reporting)

        reports.append(IntegrityReport(
            path_id=p.path_id,
            flags=flags,
            reported_metrics=p.metrics or {},
            passed=len(flags) == 0,
        ))

    return reports


# --- Research Map Evaluation ---


def score_research_map_offline(
    research_map: ResearchMap,
    path_results: list[PathResult],
    baseline_metrics: dict[str, float],
) -> ResearchMapScore:
    """Deterministic research map scoring using structural checks.

    For full evaluation, use LLM-as-judge on the research map text.
    """
    # Classification accuracy: do dead_ends actually show regression?
    classification_correct = 0
    classification_total = 0

    for dead_end in research_map.dead_ends:
        classification_total += 1
        # Check if this path actually had regression
        for p in path_results:
            if p.path_id in dead_end:
                improvement = p.metrics.get("improvement", 0) if p.metrics else 0
                if improvement < 0:
                    classification_correct += 1
                break

    for promising in research_map.promising_directions:
        classification_total += 1
        for p in path_results:
            if p.path_id in promising:
                improvement = p.metrics.get("improvement", 0) if p.metrics else 0
                if improvement > 0:
                    classification_correct += 1
                break

    classification_accuracy = (
        classification_correct / classification_total
        if classification_total > 0 else 0.0
    )

    # Direction validity: promising directions have positive improvement
    direction_valid = 0
    direction_total = len(research_map.promising_directions)
    for promising in research_map.promising_directions:
        for p in path_results:
            if p.path_id in promising and p.success:
                if p.metrics and p.metrics.get("improvement", 0) > 0:
                    direction_valid += 1
                break
    direction_validity = direction_valid / direction_total if direction_total > 0 else 0.0

    # Next experiment novelty: penalize generic suggestions
    generic_phrases = [
        "run longer", "more data", "increase", "decrease",
        "try again", "repeat", "more epochs",
    ]
    novel_count = 0
    for exp in research_map.next_experiments:
        is_generic = any(g in exp.lower() for g in generic_phrases)
        if not is_generic:
            novel_count += 1
    next_novelty = (
        novel_count / len(research_map.next_experiments)
        if research_map.next_experiments else 0.0
    )

    # Negative result honesty: dead ends and inconclusive should be populated
    has_dead_ends = len(research_map.dead_ends) > 0
    has_inconclusive = len(research_map.inconclusive) > 0
    # If there were failures/regressions, they should be documented
    actual_failures = sum(1 for p in path_results if not p.success or
                         (p.metrics and p.metrics.get("improvement", 0) < 0))
    documented_negatives = len(research_map.dead_ends) + len(research_map.inconclusive)
    neg_honesty = (
        min(documented_negatives / actual_failures, 1.0)
        if actual_failures > 0 else 1.0
    )

    # Synthesis quality: does it reference baseline + improvements together?
    has_baseline_ref = bool(research_map.baseline_summary)
    has_assessment = bool(research_map.overall_reproducibility_assessment)
    synthesis = (float(has_baseline_ref) + float(has_assessment)) / 2.0

    # Actionability: next experiments should be specific
    actionability = next_novelty  # novel suggestions are more actionable

    return ResearchMapScore(
        classification_accuracy=classification_accuracy,
        direction_validity=direction_validity,
        next_experiment_novelty=next_novelty,
        negative_result_honesty=neg_honesty,
        synthesis_quality=synthesis,
        actionability=actionability,
        rationale="Scored via offline structural checks",
    )


RESEARCH_MAP_RUBRIC = """Evaluate this Research Map on 6 dimensions (0.0-1.0 each):

1. CLASSIFICATION ACCURACY: Are "dead ends" actually worse and "promising directions" actually better?
2. DIRECTION VALIDITY: Do the promising directions have evidence of real improvement?
3. NEXT EXPERIMENT NOVELTY: Are suggested next experiments novel (not just "run longer")?
4. NEGATIVE RESULT HONESTY: Are failures and regressions documented honestly?
5. SYNTHESIS QUALITY: Does it integrate baseline + improvements into a coherent narrative?
6. ACTIONABILITY: Could a researcher pick this up and know what to do next?

Research Map:
{research_map_text}

Baseline metrics: {baseline_metrics}
Path results: {path_results_text}
"""


# --- Full Innovation Evaluation ---


def evaluate_innovation_offline(
    hypotheses: list[ImprovementHypothesis],
    path_results: list[PathResult],
    research_map: ResearchMap,
    baseline_metrics: dict[str, float],
    claim_map: PaperClaimMap | None = None,
    *,
    version: str = "",
    paper_id: str = "",
) -> InnovationScore:
    """Run full innovation evaluation suite (offline/deterministic)."""
    # Score hypotheses
    hypothesis_scores = [
        score_hypothesis_offline(h, claim_map) for h in hypotheses
    ]

    # Run integrity checks
    integrity_reports = []
    for p in path_results:
        isolation = check_variable_isolation(p, baseline_metrics)
        consistency = check_metric_consistency(p)
        # Merge flags
        all_flags = list(set(isolation.flags + consistency.flags))
        integrity_reports.append(IntegrityReport(
            path_id=p.path_id,
            flags=all_flags,
            variables_changed=isolation.variables_changed,
            reported_metrics=p.metrics or {},
            metric_deviation=consistency.metric_deviation,
            passed=len(all_flags) == 0,
        ))

    # Score research map
    research_map_score = score_research_map_offline(
        research_map, path_results, baseline_metrics,
    )

    return InnovationScore(
        version=version,
        paper_id=paper_id,
        hypothesis_scores=hypothesis_scores,
        integrity_reports=integrity_reports,
        research_map_score=research_map_score,
    )
