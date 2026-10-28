"""Running a workflow's guards with the security services of the unit of work they run in."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_dependency_injection import ScopeFactoryInterface

    from xtr_workflow.event import GuardEvent
    from xtr_workflow.event_listener.guard_listener import GuardListener

__all__ = ["UnitOfWorkGuardListener"]


@final
class UnitOfWorkGuardListener:
    """Hands each guard event of a workflow to its guard listener, built for the unit of work.

    The token a guard reads belongs to whoever is moving the subject — the
    request being served, the message being handled — so the security
    services behind the guard listener live for one unit of work, while the
    dispatcher keeps its listeners for the container's life. This one is what
    the dispatcher keeps: for each event it joins the unit of work open where
    the event is dispatched, or opens one of its own, and calls the guard
    listener built there.

    Outside any unit of work — a console command moving a subject — the unit
    opened for the event has no one authenticated: a guard sees no token.
    """

    __slots__: tuple[str, ...] = ("_guard_listener", "_qualifier", "_scopes")

    _scopes: ScopeFactoryInterface
    _guard_listener: type[GuardListener]
    _qualifier: str

    def __init__(
        self, scopes: ScopeFactoryInterface, guard_listener: type[GuardListener], qualifier: str
    ) -> None:
        """Run the guard listener registered as ``(guard_listener, qualifier)``.

        Args:
            scopes: Opens the unit of work an event runs the guards in, or joins it.
            guard_listener: The guard listener's class, as registered.
            qualifier: The workflow's name, which the guard listener is registered under.
        """
        self._scopes = scopes
        self._guard_listener = guard_listener
        self._qualifier = qualifier

    async def on_transition(self, event: GuardEvent, event_name: str) -> None:
        """Run the guards configured for ``event_name`` in the unit of work of the event."""
        async with self._scopes.unit_of_work() as unit:
            listener = await unit.get(self._guard_listener, self._qualifier)
            await listener.on_transition(event, event_name)

    async def get_guard_listener(self) -> GuardListener:
        """Return the guard listener built for the unit of work open where it is asked.

        For a tool naming what a guard event runs: the guards are the same in
        every unit of work, so the guard listener of this one names them for
        all.
        """
        async with self._scopes.unit_of_work() as unit:
            return await unit.get(self._guard_listener, self._qualifier)
