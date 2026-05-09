"""WorkspaceTool Protocol — slot for lookup, semantic_search, and the
five other PRD tools."""

from __future__ import annotations

from typing import Any, Protocol

from backend.services.context.workspace.model import Cited


class WorkspaceToolError(Exception):
    """A tool failed in a way that is NOT modeled as an event (e.g.,
    invalid arguments). Tool failures that the workspace should record
    raise their own typed errors."""


class WorkspaceTool(Protocol):
    """A callable that, given a Workspace + arguments, produces a
    Cited[Any]. Tool implementations are pure-ish: they may consult
    the workspace's projection and external clients (semantic search
    against Chroma, web search), but their output is always Cited[Any]
    so the citation invariant flows through every agent decision."""

    @property
    def name(self) -> str: ...

    def call(self, *, workspace_id: str, **kwargs: Any) -> Cited[Any]:
        """Invoke the tool. The Workspace service appends a ToolInvoked
        event with the result citations."""


__all__ = ["WorkspaceTool", "WorkspaceToolError"]
