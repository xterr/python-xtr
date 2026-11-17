"""Every unit of work a container opens — a request, a message, a command — is a log unit."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_service_contracts import UnitParticipantInterface

from .log_unit import enter_nested_unit, exit_nested_unit

__all__ = ["LogUnitParticipant"]


@final
class LogUnitParticipant(UnitParticipantInterface):
    """Opens a log unit as each unit of work begins, and closes it once the unit has ended.

    So what is kept per unit — a fingers-crossed buffer, the id tying records
    together, values bound to the log context — is one request's, one
    message's, one command's, however many run at once. A unit opened inside
    another — a message handled inside a request — is a log unit of its own,
    and the one around it is open again once it ends.

    The container closes a unit's scoped services before it tells this the
    unit ended, so what their teardown logs lands in the unit's log unit.

    Registered by the logging bundle; outside a container, open and close
    units with :func:`~xtr_logging.log_unit.begin_unit` and
    :func:`~xtr_logging.log_unit.end_unit` instead.
    """

    __slots__ = ()

    @override
    def unit_began(self) -> object | None:
        """Open the unit's log unit."""
        return enter_nested_unit()

    @override
    def unit_ended(self, token: object | None) -> None:
        """Close the unit's log unit, running what its end flushes."""
        exit_nested_unit(token)
