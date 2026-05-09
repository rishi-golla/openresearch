"""ReproLab Root Orchestrator — drives the full reproduction pipeline.

The orchestrator uses a hybrid approach:
  - Python code drives the pipeline sequence and manages state
  - Each agent step invokes ``claude_agent_sdk.query()``
  - Structured outputs are parsed and fed into the next agent's prompt
  - Checkpoints are saved to the event store after each gate

Usage:
    orchestrator = ReproLabOrchestrator(project_id, runs_root)
    result = await orchestrator.run(source_pdf="demo_paper.pdf")
"""

from __future__ import annotations

import enum
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from backend.agents.registry import AGENT_REGISTRY, get_agent_definitions
from backend.agents.schemas import (
    AgentOutput,
    BaselineResult,
    EnvironmentSpec,
    ExperimentArtifacts,
    GateDecision,
    GateStatus,
    ImprovementHypothesis,
    PaperClaimMap,
    PathResult,
    ReproductionContract,
    ResearchMap,
    VerificationReport,
)

logger = logging.getLogger(__name__)


class PipelineStage(str, enum.Enum):
    """Stages in the reproduction pipeline."""

    INGESTED = "ingested"
    PAPER_UNDERSTOOD = "paper_understood"
    ARTIFACTS_DISCOVERED = "artifacts_discovered"
    ENVIRONMENT_BUILT = "environment_built"
    PLAN_CREATED = "plan_created"
    GATE_1_PASSED = "gate_1_passed"
    BASELINE_IMPLEMENTED = "baseline_implemented"
    BASELINE_RUN = "baseline_run"
    GATE_2_PASSED = "gate_2_passed"
    IMPROVEMENTS_SELECTED = "improvements_selected"
    IMPROVEMENTS_RUN = "improvements_run"
    GATE_3_PASSED = "gate_3_passed"
    RESEARCH_MAP_GENERATED = "research_map_generated"
    COMPLETE = "complete"


@dataclass
class PipelineState:
    """Mutable state that accumulates as the pipeline progresses."""

    project_id: str
    stage: PipelineStage = PipelineStage.INGESTED
    paper_claim_map: PaperClaimMap | None = None
    artifact_index: dict[str, Any] | None = None
    environment_spec: EnvironmentSpec | None = None
    reproduction_contract: ReproductionContract | None = None
    gate_1: GateDecision | None = None
    baseline_result: BaselineResult | None = None
    experiment_artifacts: ExperimentArtifacts | None = None
    gate_2: GateDecision | None = None
    improvement_hypotheses: list[ImprovementHypothesis] = field(default_factory=list)
    path_results: list[PathResult] = field(default_factory=list)
    gate_3: GateDecision | None = None
    research_map: ResearchMap | None = None
    assumption_ledger: list[dict[str, Any]] = field(default_factory=list)
    decision_log: list[str] = field(default_factory=list)

    def save_checkpoint(self, runs_root: Path) -> Path:
        """Persist pipeline state to disk for crash-resume."""
        checkpoint_dir = runs_root / self.project_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoint_dir / "pipeline_state.json"
        data = {
            "project_id": self.project_id,
            "stage": self.stage.value,
            "assumption_ledger": self.assumption_ledger,
            "decision_log": self.decision_log,
        }
        if self.paper_claim_map:
            data["paper_claim_map"] = self.paper_claim_map.model_dump()
        if self.environment_spec:
            data["environment_spec"] = self.environment_spec.model_dump()
        if self.reproduction_contract:
            data["reproduction_contract"] = self.reproduction_contract.model_dump()
        if self.baseline_result:
            data["baseline_result"] = self.baseline_result.model_dump()
        if self.experiment_artifacts:
            data["experiment_artifacts"] = self.experiment_artifacts.model_dump()
        if self.research_map:
            data["research_map"] = self.research_map.model_dump()
        if self.gate_1:
            data["gate_1"] = self.gate_1.model_dump()
        if self.gate_2:
            data["gate_2"] = self.gate_2.model_dump()
        if self.gate_3:
            data["gate_3"] = self.gate_3.model_dump()
        if self.improvement_hypotheses:
            data["improvement_hypotheses"] = [h.model_dump() for h in self.improvement_hypotheses]
        if self.path_results:
            data["path_results"] = [r.model_dump() for r in self.path_results]
        path.write_text(json.dumps(data, indent=2))
        logger.info("Checkpoint saved: stage=%s path=%s", self.stage.value, path)
        return path

    @classmethod
    def load_checkpoint(cls, runs_root: Path, project_id: str) -> PipelineState | None:
        """Load pipeline state from disk if a checkpoint exists."""
        path = runs_root / project_id / "pipeline_state.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        state = cls(project_id=data["project_id"])
        state.stage = PipelineStage(data["stage"])
        state.assumption_ledger = data.get("assumption_ledger", [])
        state.decision_log = data.get("decision_log", [])
        if "paper_claim_map" in data:
            state.paper_claim_map = PaperClaimMap(**data["paper_claim_map"])
        if "environment_spec" in data:
            state.environment_spec = EnvironmentSpec(**data["environment_spec"])
        if "reproduction_contract" in data:
            state.reproduction_contract = ReproductionContract(**data["reproduction_contract"])
        if "baseline_result" in data:
            state.baseline_result = BaselineResult(**data["baseline_result"])
        if "experiment_artifacts" in data:
            state.experiment_artifacts = ExperimentArtifacts(**data["experiment_artifacts"])
        if "research_map" in data:
            state.research_map = ResearchMap(**data["research_map"])
        if "gate_1" in data:
            state.gate_1 = GateDecision(**data["gate_1"])
        if "gate_2" in data:
            state.gate_2 = GateDecision(**data["gate_2"])
        if "gate_3" in data:
            state.gate_3 = GateDecision(**data["gate_3"])
        if "improvement_hypotheses" in data:
            state.improvement_hypotheses = [
                ImprovementHypothesis(**h) for h in data["improvement_hypotheses"]
            ]
        if "path_results" in data:
            state.path_results = [PathResult(**r) for r in data["path_results"]]
        logger.info("Checkpoint loaded: stage=%s", state.stage.value)
        return state


class ReproLabOrchestrator:
    """Drives the full ReproLab pipeline using the Claude Agent SDK.

    Each pipeline step:
      1. Builds a prompt with context from previous steps
      2. Invokes ``query()`` targeting the appropriate agent
      3. Parses the structured output
      4. Updates pipeline state
      5. Saves a checkpoint after verification gates
    """

    def __init__(
        self,
        project_id: str,
        runs_root: Path,
        *,
        model: str | None = None,
        max_turns_per_agent: int = 30,
        permission_mode: str = "bypassPermissions",
    ) -> None:
        self.project_id = project_id
        self.runs_root = Path(runs_root)
        self.model = model
        self.max_turns_per_agent = max_turns_per_agent
        self.permission_mode = permission_mode
        self._project_dir = self.runs_root / project_id
        self._project_dir.mkdir(parents=True, exist_ok=True)

    async def _invoke_agent(
        self,
        agent_id: str,
        task_prompt: str,
        *,
        cwd: str | Path | None = None,
    ) -> str:
        """Invoke a single agent via the SDK and return its final text output."""
        spec = AGENT_REGISTRY[agent_id]
        agent_defs = get_agent_definitions()

        full_prompt = f"{spec.prompt}\n\n---\n\n# Current Task\n{task_prompt}"

        options = ClaudeAgentOptions(
            model=self.model,
            permission_mode=self.permission_mode,
            max_turns=self.max_turns_per_agent,
            agents=agent_defs,
            cwd=str(cwd or self._project_dir),
            system_prompt=spec.prompt,
        )

        collected_text: list[str] = []
        async for message in query(prompt=task_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        collected_text.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    logger.error(
                        "Agent %s failed: %s",
                        agent_id,
                        collected_text[-1] if collected_text else "unknown error",
                    )
        result = "\n".join(collected_text)
        logger.info("Agent %s completed (%d chars output)", agent_id, len(result))
        return result

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON from agent output, handling markdown fences."""
        # Try to find JSON in code fences first
        import re

        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1))
        # Try to find a top-level JSON object
        brace_start = text.find("{")
        if brace_start >= 0:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[brace_start : i + 1])
        raise ValueError(f"No JSON found in agent output: {text[:200]}")

    async def run_paper_understanding(self, state: PipelineState) -> PipelineState:
        """Step 1: Paper Understanding Agent."""
        logger.info("[1/9] Running Paper Understanding Agent")
        prompt = (
            f"Analyze the paper for project {self.project_id}.\n"
            f"The parsed paper content is in: {self._project_dir}\n"
            f"Read the parsed sections and extract the full PaperClaimMap.\n"
            f"Write the output to {self._project_dir}/paper_claim_map.json"
        )
        output = await self._invoke_agent("paper-understanding", prompt)
        data = self._extract_json(output)
        state.paper_claim_map = PaperClaimMap(**data)
        # Merge ambiguities into assumption ledger
        for amb in state.paper_claim_map.ambiguities:
            state.assumption_ledger.append(amb.model_dump())
        state.stage = PipelineStage.PAPER_UNDERSTOOD
        return state

    async def run_artifact_discovery(self, state: PipelineState) -> PipelineState:
        """Step 2: Artifact Discovery Agent."""
        logger.info("[2/9] Running Artifact Discovery Agent")
        claim_map_json = state.paper_claim_map.model_dump_json(indent=2) if state.paper_claim_map else "{}"
        prompt = (
            f"Find external artifacts for project {self.project_id}.\n"
            f"Paper claim map:\n```json\n{claim_map_json}\n```\n"
            f"Write artifact_index.json to {self._project_dir}/"
        )
        output = await self._invoke_agent("artifact-discovery", prompt)
        state.artifact_index = self._extract_json(output)
        state.stage = PipelineStage.ARTIFACTS_DISCOVERED
        return state

    async def run_environment_detective(self, state: PipelineState) -> PipelineState:
        """Step 3: Environment Detective Agent."""
        logger.info("[3/9] Running Environment Detective Agent")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "artifact_index": state.artifact_index or {},
        }
        prompt = (
            f"Build the Docker environment for project {self.project_id}.\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```\n"
            f"Write Dockerfile and environment_spec.json to {self._project_dir}/"
        )
        output = await self._invoke_agent("environment-detective", prompt)
        data = self._extract_json(output)
        state.environment_spec = EnvironmentSpec(**data)
        # Merge environment assumptions
        for assumption in state.environment_spec.assumptions:
            state.assumption_ledger.append(assumption.model_dump())
        state.stage = PipelineStage.ENVIRONMENT_BUILT
        return state

    async def run_reproduction_planner(self, state: PipelineState) -> PipelineState:
        """Step 4: Reproduction Planner."""
        logger.info("[4/9] Running Reproduction Planner")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "environment_spec": state.environment_spec.model_dump() if state.environment_spec else {},
            "assumption_ledger": state.assumption_ledger,
        }
        prompt = (
            f"Create the reproduction contract for project {self.project_id}.\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```\n"
            f"Write reproduction_contract.json to {self._project_dir}/"
        )
        output = await self._invoke_agent("reproduction-planner", prompt)
        data = self._extract_json(output)
        state.reproduction_contract = ReproductionContract(**data)
        state.stage = PipelineStage.PLAN_CREATED
        return state

    async def run_gate_1(self, state: PipelineState) -> PipelineState:
        """Gate 1: Plan Verification."""
        logger.info("[Gate 1] Running Plan Verification")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "reproduction_contract": state.reproduction_contract.model_dump() if state.reproduction_contract else {},
            "environment_spec": state.environment_spec.model_dump() if state.environment_spec else {},
            "assumption_ledger": state.assumption_ledger,
        }
        prompt = (
            f"Verify the reproduction plan for project {self.project_id}.\n"
            f"This is Gate 1: Plan Verification.\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```\n"
            f"Run all 4 verifiers and produce a final gate decision."
        )
        output = await self._invoke_agent("supervisor-verifier", prompt)
        data = self._extract_json(output)
        report = VerificationReport(**data)
        state.gate_1 = GateDecision(
            gate="gate_1",
            passed=report.status in (GateStatus.verified, GateStatus.verified_with_caveats),
            status=report.status,
        )
        state.decision_log.append(report.decision_log_entry)
        state.stage = PipelineStage.GATE_1_PASSED
        state.save_checkpoint(self.runs_root)
        return state

    async def run_baseline_implementation(self, state: PipelineState) -> PipelineState:
        """Step 5: Baseline Implementation Agent."""
        logger.info("[5/9] Running Baseline Implementation Agent")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "reproduction_contract": state.reproduction_contract.model_dump() if state.reproduction_contract else {},
            "environment_spec": state.environment_spec.model_dump() if state.environment_spec else {},
            "artifact_index": state.artifact_index or {},
            "assumption_ledger": state.assumption_ledger,
        }
        code_dir = self._project_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        prompt = (
            f"Implement the baseline for project {self.project_id}.\n"
            f"Write code to {code_dir}\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```"
        )
        output = await self._invoke_agent(
            "baseline-implementation", prompt, cwd=code_dir,
        )
        data = self._extract_json(output)
        state.baseline_result = BaselineResult(**data)
        state.stage = PipelineStage.BASELINE_IMPLEMENTED
        return state

    async def run_experiment(self, state: PipelineState) -> PipelineState:
        """Step 6: Experiment Runner Agent."""
        logger.info("[6/9] Running Experiment Runner Agent")
        baseline_dir = self._project_dir / "baseline"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        context = {
            "baseline_result": state.baseline_result.model_dump() if state.baseline_result else {},
            "reproduction_contract": state.reproduction_contract.model_dump() if state.reproduction_contract else {},
        }
        prompt = (
            f"Execute the baseline experiment for project {self.project_id}.\n"
            f"Write artifacts to {baseline_dir}\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```"
        )
        output = await self._invoke_agent("experiment-runner", prompt)
        data = self._extract_json(output)
        state.experiment_artifacts = ExperimentArtifacts(**data)
        state.stage = PipelineStage.BASELINE_RUN
        return state

    async def run_gate_2(self, state: PipelineState) -> PipelineState:
        """Gate 2: Baseline Verification."""
        logger.info("[Gate 2] Running Baseline Verification")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "baseline_result": state.baseline_result.model_dump() if state.baseline_result else {},
            "experiment_artifacts": state.experiment_artifacts.model_dump() if state.experiment_artifacts else {},
            "assumption_ledger": state.assumption_ledger,
        }
        prompt = (
            f"Verify the baseline reproduction for project {self.project_id}.\n"
            f"This is Gate 2: Baseline Verification.\n"
            f"Artifacts are in {self._project_dir / 'baseline'}\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```\n"
            f"Run all 4 verifiers and produce a final gate decision."
        )
        output = await self._invoke_agent("supervisor-verifier", prompt)
        data = self._extract_json(output)
        report = VerificationReport(**data)
        state.gate_2 = GateDecision(
            gate="gate_2",
            passed=report.status in (GateStatus.verified, GateStatus.verified_with_caveats),
            status=report.status,
        )
        state.decision_log.append(report.decision_log_entry)
        state.stage = PipelineStage.GATE_2_PASSED
        state.save_checkpoint(self.runs_root)
        return state

    async def run_improvements(
        self,
        state: PipelineState,
        *,
        user_hints: list[str] | None = None,
        n_paths: int = 3,
    ) -> PipelineState:
        """Steps 7-8: Improvement Orchestrator + Path Agents."""
        logger.info("[7/9] Running Improvement Orchestrator")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "experiment_artifacts": state.experiment_artifacts.model_dump() if state.experiment_artifacts else {},
            "baseline_result": state.baseline_result.model_dump() if state.baseline_result else {},
            "assumption_ledger": state.assumption_ledger,
        }
        hints_str = ""
        if user_hints:
            hints_str = f"\nUser hints: {', '.join(user_hints)}"
        prompt = (
            f"Select {n_paths} improvement hypotheses for project {self.project_id}.{hints_str}\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```"
        )
        output = await self._invoke_agent("improvement-orchestrator", prompt)
        data = self._extract_json(output)
        hypotheses_raw = data.get("hypotheses", [])
        state.improvement_hypotheses = [
            ImprovementHypothesis(**h) for h in hypotheses_raw
        ]
        state.stage = PipelineStage.IMPROVEMENTS_SELECTED

        # Run each path agent
        logger.info("[8/9] Running %d Improvement Path Agents", len(state.improvement_hypotheses))
        for hypothesis in state.improvement_hypotheses:
            path_dir = self._project_dir / "improvements" / hypothesis.path_id
            path_dir.mkdir(parents=True, exist_ok=True)
            path_prompt = (
                f"Execute improvement hypothesis for project {self.project_id}.\n"
                f"Work in: {path_dir}\n"
                f"Baseline code is in: {self._project_dir / 'code'}\n"
                f"Hypothesis:\n```json\n{hypothesis.model_dump_json(indent=2)}\n```\n"
                f"Environment:\n```json\n{state.environment_spec.model_dump_json(indent=2) if state.environment_spec else '{}'}\n```"
            )
            path_output = await self._invoke_agent(
                "improvement-path", path_prompt, cwd=path_dir,
            )
            try:
                path_data = self._extract_json(path_output)
                state.path_results.append(PathResult(**path_data))
            except (ValueError, Exception) as exc:
                logger.warning("Path %s failed to parse: %s", hypothesis.path_id, exc)
                state.path_results.append(
                    PathResult(
                        path_id=hypothesis.path_id,
                        hypothesis=hypothesis.hypothesis,
                        failure_notes=str(exc),
                        success=False,
                    )
                )
        state.stage = PipelineStage.IMPROVEMENTS_RUN
        return state

    async def run_gate_3(self, state: PipelineState) -> PipelineState:
        """Gate 3: Improvement Verification + Research Map."""
        logger.info("[Gate 3] Running Improvement Verification")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "path_results": [r.model_dump() for r in state.path_results],
            "baseline_result": state.baseline_result.model_dump() if state.baseline_result else {},
            "experiment_artifacts": state.experiment_artifacts.model_dump() if state.experiment_artifacts else {},
        }
        prompt = (
            f"Verify all improvement paths for project {self.project_id}.\n"
            f"This is Gate 3: Improvement Verification.\n"
            f"Also generate the final Research Map.\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```"
        )
        output = await self._invoke_agent("supervisor-verifier", prompt)
        data = self._extract_json(output)
        report = VerificationReport(**data)
        state.gate_3 = GateDecision(
            gate="gate_3",
            passed=report.status in (GateStatus.verified, GateStatus.verified_with_caveats),
            status=report.status,
        )
        state.decision_log.append(report.decision_log_entry)
        state.stage = PipelineStage.GATE_3_PASSED
        state.save_checkpoint(self.runs_root)
        return state

    async def generate_research_map(self, state: PipelineState) -> PipelineState:
        """Step 9: Generate final Research Map."""
        logger.info("[9/9] Generating Research Map")
        context = {
            "paper_claim_map": state.paper_claim_map.model_dump() if state.paper_claim_map else {},
            "experiment_artifacts": state.experiment_artifacts.model_dump() if state.experiment_artifacts else {},
            "path_results": [r.model_dump() for r in state.path_results],
            "gate_2": state.gate_2.model_dump() if state.gate_2 else {},
            "gate_3": state.gate_3.model_dump() if state.gate_3 else {},
            "assumption_ledger": state.assumption_ledger,
            "decision_log": state.decision_log,
        }
        prompt = (
            f"Generate the final Research Map for project {self.project_id}.\n"
            f"Summarize: baseline results, promising directions, dead ends, and next experiments.\n"
            f"Context:\n```json\n{json.dumps(context, indent=2)}\n```\n"
            f"Write research_map.json to {self._project_dir}/"
        )
        output = await self._invoke_agent("supervisor-verifier", prompt)
        data = self._extract_json(output)
        state.research_map = ResearchMap(**data)
        state.stage = PipelineStage.RESEARCH_MAP_GENERATED
        # Write final artifacts
        (self._project_dir / "research_map.json").write_text(
            state.research_map.model_dump_json(indent=2)
        )
        (self._project_dir / "assumption_ledger.json").write_text(
            json.dumps(state.assumption_ledger, indent=2)
        )
        (self._project_dir / "decision_log.json").write_text(
            json.dumps(state.decision_log, indent=2)
        )
        state.stage = PipelineStage.COMPLETE
        state.save_checkpoint(self.runs_root)
        return state

    async def run(
        self,
        *,
        resume: bool = True,
        user_hints: list[str] | None = None,
        n_improvement_paths: int = 3,
    ) -> PipelineState:
        """Run the full pipeline, resuming from the last checkpoint if available."""
        state: PipelineState | None = None
        if resume:
            state = PipelineState.load_checkpoint(self.runs_root, self.project_id)
        if state is None:
            state = PipelineState(project_id=self.project_id)

        # Define the pipeline as a sequence of (stage_threshold, step_fn) pairs.
        # Each step only runs if the pipeline hasn't passed that stage yet.
        pipeline: list[tuple[PipelineStage, Any]] = [
            (PipelineStage.PAPER_UNDERSTOOD, self.run_paper_understanding),
            (PipelineStage.ARTIFACTS_DISCOVERED, self.run_artifact_discovery),
            (PipelineStage.ENVIRONMENT_BUILT, self.run_environment_detective),
            (PipelineStage.PLAN_CREATED, self.run_reproduction_planner),
            (PipelineStage.GATE_1_PASSED, self.run_gate_1),
            (PipelineStage.BASELINE_IMPLEMENTED, self.run_baseline_implementation),
            (PipelineStage.BASELINE_RUN, self.run_experiment),
            (PipelineStage.GATE_2_PASSED, self.run_gate_2),
        ]

        stages_order = list(PipelineStage)
        current_idx = stages_order.index(state.stage)

        for target_stage, step_fn in pipeline:
            target_idx = stages_order.index(target_stage)
            if current_idx >= target_idx:
                logger.info("Skipping %s (already at %s)", target_stage.value, state.stage.value)
                continue
            state = await step_fn(state)
            current_idx = stages_order.index(state.stage)

            # Check gate results
            if state.gate_1 and not state.gate_1.passed:
                logger.error("Gate 1 FAILED: %s", state.gate_1.status.value)
                return state
            if state.gate_2 and not state.gate_2.passed:
                logger.error("Gate 2 FAILED: %s", state.gate_2.status.value)
                return state

        # Improvement phase
        if current_idx < stages_order.index(PipelineStage.IMPROVEMENTS_RUN):
            state = await self.run_improvements(
                state, user_hints=user_hints, n_paths=n_improvement_paths,
            )

        if current_idx < stages_order.index(PipelineStage.GATE_3_PASSED):
            state = await self.run_gate_3(state)

        if current_idx < stages_order.index(PipelineStage.RESEARCH_MAP_GENERATED):
            state = await self.generate_research_map(state)

        logger.info("Pipeline complete for project %s", self.project_id)
        return state
