from __future__ import annotations

from pathlib import Path

from backend.agents.orchestrator import PipelineState, ReproLabOrchestrator
from backend.agents.schemas import GateDecision, GateStatus, ResearchMap
from backend.hermes_audit.models import (
    HermesAuditReport,
    HermesAuditScope,
    HermesAuditStatus,
    HermesInterventionType,
)


def test_pipeline_state_roundtrips_hermes_reports(tmp_path: Path):
    state = PipelineState(project_id="prj_hermes")
    state.gate_2 = GateDecision(gate="gate_2", passed=True, status=GateStatus.verified)
    state.research_map = ResearchMap(promising_directions=["Entropy tuning path"])
    state.hermes_step_reports = {
        "paper-understanding": [
            HermesAuditReport(
                target="paper-understanding",
                scope=HermesAuditScope.step,
                status=HermesAuditStatus.grounded,
                summary="Grounded",
            )
        ]
    }
    state.hermes_interventions = [
        {
            "target": "gate_2",
            "action": HermesInterventionType.downgrade_claim.value,
            "reason": "Unsupported metric summary",
        }
    ]

    state.save_checkpoint(tmp_path)
    loaded = PipelineState.load_checkpoint(tmp_path, "prj_hermes")

    assert loaded is not None
    assert loaded.hermes_step_reports["paper-understanding"][0].status == HermesAuditStatus.grounded
    assert loaded.hermes_interventions[0]["action"] == HermesInterventionType.downgrade_claim.value


def test_gate_status_is_downgraded_when_hermes_requests_it(tmp_path: Path):
    orchestrator = ReproLabOrchestrator(project_id="prj_hermes", runs_root=tmp_path)

    downgraded = orchestrator._downgrade_gate_status(GateStatus.verified)

    assert downgraded == GateStatus.verified_with_caveats


def test_research_map_suppresses_unsupported_claims(tmp_path: Path):
    orchestrator = ReproLabOrchestrator(project_id="prj_hermes", runs_root=tmp_path)
    state = PipelineState(project_id="prj_hermes")
    state.research_map = ResearchMap(
        promising_directions=["Entropy tuning path improved reward", "GAE sweep improved stability"],
        inconclusive=[],
    )
    report = HermesAuditReport(
        target="research_map_generated",
        scope=HermesAuditScope.checkpoint,
        status=HermesAuditStatus.unsupported,
        summary="One path is unsupported",
        unsupported_claims=["Entropy tuning path"],
        recommended_intervention=HermesInterventionType.suppress_publication,
    )

    orchestrator._apply_research_map_intervention(state, report)

    assert "Entropy tuning path improved reward" not in state.research_map.promising_directions
    assert any("Entropy tuning path" in item for item in state.research_map.inconclusive)
