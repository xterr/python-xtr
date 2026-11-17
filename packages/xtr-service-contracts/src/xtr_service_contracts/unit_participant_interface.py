"""Something that takes part in every unit of work a container opens."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["UnitParticipantInterface"]


@runtime_checkable
class UnitParticipantInterface(Protocol):
    """Is told when each unit of work begins and when it ends.

    A unit of work — a request, a message, a command — is opened by a
    container; a service that keeps state per unit opens its own part of it
    here, and closes it when the unit ends, however the unit ends. A unit
    joined by work started inside it is not a new one: only the unit that
    was opened begins and ends.

    :meth:`unit_began` runs before the unit's scope exists, so it cannot read
    the unit; :meth:`unit_ended` runs after the unit's scoped services were
    torn down, so what their teardown did still happened inside the unit.

    Keep nothing per unit on the participant itself, nor in a stack in a
    context variable: return from :meth:`unit_began` whatever
    :meth:`unit_ended` needs back — a context variable's token, say — and the
    container hands exactly that to :meth:`unit_ended` for the same unit.
    :meth:`unit_ended` may run in another context than :meth:`unit_began`
    did, when the unit is exited from another task, so a token it is handed
    is reset under ``contextlib.suppress(ValueError)``.

    Both hooks are synchronous: they run at every unit's edges, where nothing
    may be awaited.
    """

    def unit_began(self) -> object | None:
        """Open this participant's part of a new unit of work.

        Returns:
            What :meth:`unit_ended` is handed back when the unit ends.
        """
        ...

    def unit_ended(self, token: object | None) -> None:
        """Close this participant's part of the unit :meth:`unit_began` returned ``token`` for."""
        ...
