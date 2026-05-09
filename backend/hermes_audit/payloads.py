"""Builders for Hermes audit payloads."""

from __future__ import annotations

from typing import Any


def build_step_audit_payload(
    *,
    project_id: str,
    target: str,
    state_snapshot: dict[str, Any],
    structured_output: dict[str, Any],
    trace_text: str,
    artifact_paths: list[str],
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "target": target,
        "state_snapshot": state_snapshot,
        "structured_output": structured_output,
        "trace_text": trace_text,
        "artifact_paths": artifact_paths,
    }


def build_checkpoint_audit_payload(
    *,
    project_id: str,
    target: str,
    state_snapshot: dict[str, Any],
    evidence_bundle: dict[str, Any],
    trace_text: str,
    artifact_paths: list[str],
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "target": target,
        "state_snapshot": state_snapshot,
        "evidence_bundle": evidence_bundle,
        "trace_text": trace_text,
        "artifact_paths": artifact_paths,
    }
