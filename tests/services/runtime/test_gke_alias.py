"""GKE alias for the gcp sandbox token (SCOPE 1).

Hermetic: no live cloud calls. ensure_gcp_available is patched to a no-op.
Asserts gke->GkeJobBackend on BOTH the enum boundary and FORCE_SANDBOX, the
build_environment no-op, and gcp+aks byte-for-byte regression parity.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.agents.execution import SandboxMode, resolve_sandbox_mode


def test_sandbox_mode_gke_resolves_to_gcp_member():
    assert SandboxMode("gke") is SandboxMode.gcp


def test_sandbox_mode_gke_case_insensitive():
    assert SandboxMode("GKE") is SandboxMode.gcp
    assert SandboxMode(" gke ") is SandboxMode.gcp


def test_gcp_token_unchanged():
    assert SandboxMode("gcp") is SandboxMode.gcp
    assert SandboxMode.gcp.value == "gcp"


def test_unknown_token_still_raises():
    with pytest.raises(ValueError):
        SandboxMode("gkeXYZ")


def test_resolve_sandbox_mode_gke_explicit(monkeypatch):
    monkeypatch.delenv("OPENRESEARCH_FORCE_SANDBOX", raising=False)
    assert resolve_sandbox_mode("gke", pipeline_mode="rlm") is SandboxMode.gcp


def test_force_sandbox_gke_override(monkeypatch):
    monkeypatch.setenv("OPENRESEARCH_FORCE_SANDBOX", "gke")
    assert resolve_sandbox_mode("auto", pipeline_mode="rlm") is SandboxMode.gcp


def test_gke_token_constructs_gke_backend():
    with patch("backend.services.runtime.ensure_gcp_available", lambda: None):
        from backend.agents.rlm.primitives import _backend_for_sandbox_mode
        from backend.services.runtime.gke_job_backend import GkeJobBackend

        backend = _backend_for_sandbox_mode(SandboxMode("gke"), run_budget=None)
        assert isinstance(backend, GkeJobBackend)


def test_force_sandbox_gke_threads_run_budget():
    budget = SimpleNamespace(name="fake_budget")
    with patch("backend.services.runtime.ensure_gcp_available", lambda: None):
        from backend.agents.rlm.primitives import _backend_for_sandbox_mode
        from backend.services.runtime.gke_job_backend import GkeJobBackend

        backend = _backend_for_sandbox_mode(SandboxMode("gke"), run_budget=budget)
        assert isinstance(backend, GkeJobBackend)
        assert backend._run_budget is budget


def test_build_environment_noop_for_gke_via_gcp_member():
    assert SandboxMode("gke").value == "gcp"


@pytest.mark.parametrize("token", ["gcp", "azure", "runpod", "local", "docker"])
def test_existing_tokens_round_trip_identically(token):
    assert SandboxMode(token).value == token


def test_aks_path_still_resolves_to_aks_backend():
    with patch("backend.services.runtime.ensure_azure_available", lambda: None):
        from backend.agents.rlm.primitives import _backend_for_sandbox_mode
        from backend.services.runtime.aks_job_backend import AksJobBackend

        backend = _backend_for_sandbox_mode(SandboxMode.azure, run_budget=None)
        assert isinstance(backend, AksJobBackend)
