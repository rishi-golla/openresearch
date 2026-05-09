"""Adapter for the Nous Hermes Python runtime."""

from __future__ import annotations

import importlib
import json
import re
from typing import Any

from backend.hermes_audit.models import (
    HermesAuditReport,
    HermesAuditScope,
    HermesAuditStatus,
    HermesInterventionType,
)


class NousHermesClient:
    """Thin adapter around the official Nous Hermes Python runtime."""

    def __init__(self, *, model: str = "anthropic/claude-sonnet-4", enabled: bool = True) -> None:
        self.model = model
        self.enabled = enabled

    def audit(self, *, scope: HermesAuditScope, target: str, payload: dict[str, Any]) -> HermesAuditReport:
        if not self.enabled:
            return HermesAuditReport(
                target=target,
                scope=scope,
                status=HermesAuditStatus.unavailable,
                summary="Nous Hermes audit disabled",
                recommended_intervention=HermesInterventionType.annotate,
            )

        try:
            response = self._run_agent(self._build_prompt(scope=scope, target=target, payload=payload))
            data = self._extract_json(response)
            data.setdefault("target", target)
            data.setdefault("scope", scope.value)
            data.setdefault("provider", "nous-hermes")
            return HermesAuditReport(**data)
        except Exception as exc:  # pragma: no cover - exercised by integration/failure tests later
            return HermesAuditReport(
                target=target,
                scope=scope,
                status=HermesAuditStatus.unavailable,
                summary="Nous Hermes runtime unavailable",
                recommended_intervention=HermesInterventionType.annotate,
                error_message=str(exc),
            )

    def _run_agent(self, prompt: str) -> str:
        module = importlib.import_module("run_agent")
        agent_cls = getattr(module, "AIAgent")
        agent = agent_cls(
            model=self.model,
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        if hasattr(agent, "chat"):
            return str(agent.chat(prompt))
        if hasattr(agent, "run"):
            return str(agent.run(prompt))
        if callable(agent):
            return str(agent(prompt))
        raise RuntimeError("Unsupported Nous Hermes runtime interface")

    @staticmethod
    def _build_prompt(*, scope: HermesAuditScope, target: str, payload: dict[str, Any]) -> str:
        return (
            "You are auditing a research reproduction pipeline for unsupported claims.\n"
            f"Scope: {scope.value}\n"
            f"Target: {target}\n"
            "Return only JSON with fields: target, scope, status, summary, findings, "
            "unsupported_claims, evidence_refs, recommended_intervention, corrective_note, confidence.\n"
            f"Payload:\n```json\n{json.dumps(payload, indent=2)}\n```"
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1))
        brace_start = text.find("{")
        if brace_start >= 0:
            depth = 0
            for idx in range(brace_start, len(text)):
                if text[idx] == "{":
                    depth += 1
                elif text[idx] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[brace_start : idx + 1])
        raise ValueError("No JSON found in Nous Hermes response")
