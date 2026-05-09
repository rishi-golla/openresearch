"""Tests for Issue #26: Experiment Runner Agent."""

from pathlib import Path
import json
import pytest

from backend.agents.experiment_runner import run_offline, run_offline_failure
from backend.agents.schemas import BaselineResult, ExperimentArtifacts


def _baseline():
    return BaselineResult(
        mode="implement_from_paper",
        code_path="/code",
        dockerfile_path="/code/Dockerfile",
        commands_to_run=["python train.py"],
        assumptions_applied=["A001"],
    )


class TestRunOffline:
    def test_produces_artifacts(self, tmp_path: Path):
        result = run_offline("prj_ppo", tmp_path, _baseline())
        assert isinstance(result, ExperimentArtifacts)
        assert result.success is True

    def test_writes_metrics_json(self, tmp_path: Path):
        run_offline("prj_ppo", tmp_path, _baseline())
        metrics_path = tmp_path / "prj_ppo" / "baseline" / "metrics.json"
        assert metrics_path.exists()
        metrics = json.loads(metrics_path.read_text())
        assert "mean_reward" in metrics

    def test_writes_log(self, tmp_path: Path):
        run_offline("prj_ppo", tmp_path, _baseline())
        log_path = tmp_path / "prj_ppo" / "baseline" / "logs" / "run.log"
        assert log_path.exists()
        assert len(log_path.read_text()) > 0

    def test_writes_commands_log(self, tmp_path: Path):
        run_offline("prj_ppo", tmp_path, _baseline())
        cmd_path = tmp_path / "prj_ppo" / "baseline" / "commands.log"
        assert cmd_path.exists()
        assert "train.py" in cmd_path.read_text()

    def test_writes_provenance(self, tmp_path: Path):
        run_offline("prj_ppo", tmp_path, _baseline())
        prov_path = tmp_path / "prj_ppo" / "baseline" / "provenance.json"
        assert prov_path.exists()
        prov = json.loads(prov_path.read_text())
        assert prov["project_id"] == "prj_ppo"

    def test_writes_plot(self, tmp_path: Path):
        run_offline("prj_ppo", tmp_path, _baseline())
        plot_path = tmp_path / "prj_ppo" / "baseline" / "plots" / "reward_curve.png"
        assert plot_path.exists()
        # Check it's a valid PNG (starts with PNG signature)
        assert plot_path.read_bytes()[:4] == b"\x89PNG"

    def test_custom_metrics(self, tmp_path: Path):
        result = run_offline(
            "prj_ppo", tmp_path, _baseline(),
            simulate_metrics={"mean_reward": 500.0, "custom": True},
        )
        assert result.metrics["mean_reward"] == 500.0
        assert result.metrics["custom"] is True

    def test_artifact_paths_are_valid(self, tmp_path: Path):
        result = run_offline("prj_ppo", tmp_path, _baseline())
        assert Path(result.log_path).exists()
        assert Path(result.commands_log_path).exists()
        assert Path(result.provenance_path).exists()


class TestRunOfflineFailure:
    def test_failure_mode(self, tmp_path: Path):
        result = run_offline_failure("prj_fail", tmp_path, _baseline())
        assert result.success is False
        assert result.error_message != ""

    def test_failure_still_writes_log(self, tmp_path: Path):
        result = run_offline_failure("prj_fail", tmp_path, _baseline())
        assert Path(result.log_path).exists()
        log_content = Path(result.log_path).read_text()
        assert "ERROR" in log_content

    def test_failure_has_no_metrics(self, tmp_path: Path):
        result = run_offline_failure("prj_fail", tmp_path, _baseline())
        assert result.metrics == {}
