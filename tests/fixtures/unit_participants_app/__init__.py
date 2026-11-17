"""An application serving a route, running a command and handling a message.

Its one unit participant journals every unit of work the container opens, so a
test reads how many units each way in opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_console import ExitCode, as_command
from xtr_dependency_injection import as_service, autoconfigure
from xtr_messenger import as_message, as_message_handler

__all__ = ["JOURNAL", "Journaling", "Ping", "handle_ping", "noop"]

JOURNAL: list[str] = []
"""``began`` and ``ended`` for every unit of work, in order, with what ran inside."""


@final
@as_service
@autoconfigure(tags=[("kernel.unit_participant", {})])
class Journaling:
    """Journals each unit of work's edges."""

    def unit_began(self) -> object | None:
        JOURNAL.append("began")
        return None

    def unit_ended(self, token: object | None) -> None:
        del token
        JOURNAL.append("ended")


@as_message(name="tests.fixtures.unit_participants_app.ping.v1")
@dataclass(frozen=True, slots=True)
class Ping:
    """A message the application handles."""


@as_message_handler(Ping)
async def handle_ping(message: Ping) -> None:
    """Note that the message was handled."""
    del message
    JOURNAL.append("handled")


@as_command("fixture:noop")
async def noop() -> int:
    """Note that the command ran."""
    JOURNAL.append("command")
    return ExitCode.SUCCESS
