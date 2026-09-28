"""A unit of work: state that lives for one request, message or command.

A long-running process handles many units of work one after another, and a
server handles several at once. Some logging state — the id tying a request's
records together, the buffer a fingers-crossed handler fills — belongs to the
current unit, not to the process and not to the handler instance shared between
units.

A unit lives in a :class:`~contextvars.ContextVar`, so it is copied into each
thread and each :mod:`asyncio` or :mod:`anyio` task: two requests handled at
once keep their own units with no lock and no leakage. The unit *object* is
shared by every context copied from the one that opened it, so state kept on it
is mutated **in place** and the change is seen everywhere — a synchronous
endpoint anyio runs in a copied context (its own ``context.run``) can enrich the
same unit, whereas a :meth:`~contextvars.ContextVar.set` there would be lost.

:func:`begin_unit` and :func:`end_unit` are called at the edges of a unit — by
whatever opens it (a request lifecycle, a message worker) — never from a handler,
processor or endpoint. Those mutate their share of the unit through
:func:`unit_state` and leave the boundary to the caller.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import partial
from typing import TYPE_CHECKING, TypeVar, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["begin_unit", "end_unit", "unit_state"]

_T = TypeVar("_T")


@final
class _Unit:
    """The state of one unit of work: per-owner state plus its end callbacks."""

    __slots__ = ("callbacks", "state")

    def __init__(self) -> None:
        self.state: dict[int, object] = {}
        self.callbacks: list[Callable[[], object]] = []


_CURRENT: ContextVar[_Unit | None] = ContextVar("xtr_logging_unit", default=None)


def begin_unit() -> None:
    """Open a fresh unit of work in the current context.

    Any unit still open is ended first, so a caller that forgot :func:`end_unit`
    cannot leak one unit's state into the next.
    """
    end_unit()
    _ = _CURRENT.set(_Unit())


def end_unit() -> None:
    """Close the open unit, running every end callback, then clear the context.

    Callbacks run in registration order. Every one runs even if an earlier one
    raised; the failures are then raised together as an :class:`ExceptionGroup`.
    Does nothing when no unit is open.

    Raises:
        ExceptionGroup: If one or more end callbacks raised.
    """
    unit = _CURRENT.get()
    if unit is None:
        return
    failures: list[Exception] = []
    for callback in unit.callbacks:
        try:
            _ = callback()
        except Exception as error:  # noqa: BLE001 — run every callback, then raise all failures together
            failures.append(error)
    _ = _CURRENT.set(None)
    if failures:
        raise ExceptionGroup("errors ending a unit of work", failures)


def unit_state(
    owner: object,
    factory: Callable[[], _T],
    on_end: Callable[[_T], object] | None = None,
) -> _T | None:
    """Return ``owner``'s state in the open unit, or ``None`` outside a unit.

    The state is created with ``factory()`` the first time ``owner`` asks in a
    unit and returned unchanged on every later call, so an owner keeps one
    mutable object per unit and mutates it in place. When given, ``on_end`` is
    registered the moment the state is created and called with that state when
    the unit ends.

    Args:
        owner: The object the state belongs to; distinct owners keep distinct
            state within one unit.
        factory: Builds the state on first use in a unit.
        on_end: Called with the state when the unit ends, registered once.

    Returns:
        The owner's state for the open unit, or ``None`` if no unit is open.
    """
    unit = _CURRENT.get()
    if unit is None:
        return None
    key = id(owner)
    if key in unit.state:
        return cast("_T", unit.state[key])
    state = factory()
    unit.state[key] = state
    if on_end is not None:
        unit.callbacks.append(partial(on_end, state))
    return state
