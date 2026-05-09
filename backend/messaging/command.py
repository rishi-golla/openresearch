"""Command base class + CommandId.

Commands carry intent into application services. Unlike events, they
are not stored — their *outcome* (the resulting events) is what gets
recorded. Commands carry a `command_id` for idempotency: re-issuing
the same command on the same aggregate is a no-op (see IdempotencyTable).
"""

from __future__ import annotations

from typing import Annotated, NewType

from pydantic import BaseModel, ConfigDict, Field

from backend.messaging.envelope import _ulid

CommandId = NewType("CommandId", str)


def new_command_id() -> CommandId:
    return CommandId(f"cmd_{_ulid()}")


class Command(BaseModel):
    """Base class for every command in our system.

    Commands are immutable. Subclasses are Pydantic models with
    payload fields plus an inherited `command_id`.
    """

    model_config = ConfigDict(frozen=True)

    command_id: Annotated[CommandId, Field(default_factory=new_command_id)]


__all__ = ["Command", "CommandId", "new_command_id"]
