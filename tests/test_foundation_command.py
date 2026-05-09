"""Tests for backend.messaging.command."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.messaging.command import Command, CommandId, new_command_id


def test_new_command_id_is_prefixed_and_unique():
    a = new_command_id()
    b = new_command_id()
    assert a.startswith("cmd_")
    assert b.startswith("cmd_")
    assert a != b


def test_command_subclass_inherits_command_id():
    class DoThing(Command):
        target: str

    cmd = DoThing(target="x")
    assert cmd.command_id.startswith("cmd_")
    assert cmd.target == "x"


def test_command_caller_can_pin_command_id_for_idempotency():
    class DoThing(Command):
        target: str

    pinned = CommandId("cmd_test_pinned")
    cmd = DoThing(command_id=pinned, target="x")
    assert cmd.command_id == pinned


def test_command_is_frozen():
    class DoThing(Command):
        target: str

    cmd = DoThing(target="x")
    with pytest.raises(ValidationError):
        cmd.target = "y"  # type: ignore[misc]
