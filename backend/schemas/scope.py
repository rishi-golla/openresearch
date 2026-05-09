"""Blackboard scope visibility levels.

Mirrors PRD §1078-1082 and the string scopes used by
`backend.services.orchestration.blackboard.BlackboardRecord`.

Defined as a typed enum here for our event payloads. Proposed upstream
to #11 in a follow-up PR; until then, we coerce to/from str at the
blackboard service boundary.
"""

from __future__ import annotations

from enum import Enum


class Scope(str, Enum):
    """Visibility of a workspace variable / blackboard record."""

    private_to_parent = "private_to_parent"
    """Only the spawning agent and its direct parent see it."""

    branch_shared = "branch_shared"
    """Shared across an improvement branch (one delegation lineage)."""

    global_verified = "global_verified"
    """Promoted after verifier confirmation; visible globally."""


__all__ = ["Scope"]
