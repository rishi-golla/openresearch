"""Tests for Issue #29: End-to-end PPO demo pipeline.

Validates the full offline pipeline produces a complete Research Map.
"""

from pathlib import Path
import json
import pytest

from backend.agents.pipeline import run_pipeline_offline
from backend.agents.orchestrator import PipelineStage, PipelineState
from backend.agents.schemas import GateStatus


PPO_WORKSPACE = {
    "project_id": "prj_e2e_test",
    "entries": [
        {"source_id": "src_1", "title": "Abstract",
         "excerpt": "We propose a new family of policy gradient methods for reinforcement learning, "
                    "which alternate between sampling data and optimizing a surrogate objective."},
        {"source_id": "src_2", "title": "Experiments",
         "excerpt": "We test on CartPole-v1 environment. We use Adam optimizer with learning rate 3e-4 "
                    "and batch size 64. We report mean reward over 100 episodes after 500000 timesteps."},
        {"source_id": "src_3", "title": "Conclusion",
         "excerpt": "We have introduced proximal policy optimization, a family of methods that use "
                    "multiple epochs of stochastic gradient ascent."},
    ],
}


class TestFullPipeline:
    def test_runs_to_completion(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.stage == PipelineStage.COMPLETE

    def test_produces_research_map(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.research_map is not None
        assert len(state.research_map.promising_directions) >= 1

    def test_all_gates_pass(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.gate_1 is not None and state.gate_1.passed
        assert state.gate_2 is not None and state.gate_2.passed
        assert state.gate_3 is not None and state.gate_3.passed

    def test_produces_paper_claim_map(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.paper_claim_map is not None
        assert state.paper_claim_map.core_contribution != ""
        assert len(state.paper_claim_map.ambiguities) >= 3

    def test_produces_environment_spec(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.environment_spec is not None
        assert "FROM python" in state.environment_spec.dockerfile

    def test_produces_baseline_result(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.baseline_result is not None
        assert len(state.baseline_result.assumptions_applied) == 8

    def test_produces_experiment_artifacts(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert state.experiment_artifacts is not None
        assert state.experiment_artifacts.success is True
        assert "mean_reward" in state.experiment_artifacts.metrics

    def test_produces_3_improvement_paths(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert len(state.path_results) == 3

    def test_identifies_dead_ends(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert len(state.research_map.dead_ends) >= 1

    def test_identifies_promising_directions(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert len(state.research_map.promising_directions) >= 1

    def test_assumption_ledger_populated(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert len(state.assumption_ledger) >= 5

    def test_decision_log_populated(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        assert len(state.decision_log) >= 3  # gate_1, gate_2, gate_3


class TestPipelineOutputFiles:
    def test_writes_research_map_json(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "research_map.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "promising_directions" in data

    def test_writes_assumption_ledger(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "assumption_ledger.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) >= 5

    def test_writes_decision_log(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "decision_log.json"
        assert path.exists()

    def test_writes_pipeline_checkpoint(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "pipeline_state.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["stage"] == "complete"

    def test_writes_paper_claim_map(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "paper_claim_map.json"
        assert path.exists()

    def test_writes_environment_spec(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "environment_spec.json"
        assert path.exists()

    def test_writes_dockerfile(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "Dockerfile"
        assert path.exists()

    def test_writes_baseline_code(self, tmp_path: Path):
        run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        path = tmp_path / "prj_e2e" / "code" / "train.py"
        assert path.exists()


class TestCheckpointResume:
    def test_checkpoint_preserves_state(self, tmp_path: Path):
        state = run_pipeline_offline("prj_e2e", tmp_path, PPO_WORKSPACE)
        loaded = PipelineState.load_checkpoint(tmp_path, "prj_e2e")
        assert loaded is not None
        assert loaded.stage == PipelineStage.COMPLETE
        assert loaded.paper_claim_map is not None


class TestUserHints:
    def test_hints_influence_improvement_paths(self, tmp_path: Path):
        state = run_pipeline_offline(
            "prj_hints", tmp_path, PPO_WORKSPACE,
            user_hints=["Try learning rate 1e-3"],
        )
        # First hypothesis should reflect user hint
        assert "learning rate" in state.improvement_hypotheses[0].hypothesis.lower()
