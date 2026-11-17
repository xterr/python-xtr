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

Under a container, every unit of work it opens — a request, a message, a
command — is a unit here too: the bundle's
:class:`~xtr_logging.log_unit_participant.LogUnitParticipant` opens one with
:func:`enter_nested_unit` as the container's unit begins and closes it with
:func:`exit_nested_unit` once it has ended, the unit around it — a request a
message was handled inside — open again afterwards.

A unit belongs to the context that began it, and ends there. A copy of that
context only carries the unit — a task started inside it, or a request a
server began from an earlier request's context — and beginning or ending a
unit there does not end one still open where it began: whoever began it is
still filling it, and ends it.

Ending a unit closes it: its end callbacks run, and from then on a context
still carrying it finds no unit — :func:`unit_state` hands out nothing for
it, so what is logged there late is handled at once rather than kept in a
unit nobody ends again. Work queued for the unit — records a queue has yet to
write — holds it open with :func:`hold_unit`: ended while held, the unit
closes when the last hold is released, so its end callbacks see everything
that was logged into it.
"""

from __future__ import annotations

import threading
from contextlib import suppress
from contextvars import ContextVar, Token
from functools import partial
from typing import TYPE_CHECKING, Final, TypeVar, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "DETACHED_VARIABLE",
    "begin_unit",
    "end_unit",
    "enter_nested_unit",
    "exit_nested_unit",
    "hold_unit",
    "in_closed_unit",
    "in_unit",
    "unit_state",
]

_T = TypeVar("_T")


@final
class _Unit:
    """The state of one unit of work: per-owner state plus its end callbacks.

    Built in the context that begins the unit: ``begun`` is that context's
    mark on it. ``ended`` turns true once its owner has ended it, ``closed``
    once its end callbacks ran — later, while ``holds`` work queued for it
    is still outstanding.
    """

    __slots__ = ("begun", "callbacks", "closed", "ended", "holds", "lock", "state")

    def __init__(self) -> None:
        self.state: dict[int, object] = {}
        self.callbacks: list[Callable[[], object]] = []
        self.begun: Token[None] = _BEGUN.set(None)
        self.ended = False
        self.closed = False
        self.holds = 0
        # Ending and releasing a hold may race between the event loop and a
        # queue's worker thread; the unit closes exactly once.
        self.lock = threading.Lock()


@final
class _Nested:
    """A unit :func:`enter_nested_unit` opened, and what the context held before it."""

    __slots__ = ("previous", "unit")

    def __init__(self, unit: _Unit, previous: Token[_Unit | None]) -> None:
        self.unit = unit
        self.previous = previous


_CURRENT: ContextVar[_Unit | None] = ContextVar("xtr_logging_unit", default=None)

DETACHED_VARIABLE: Final = (_CURRENT, None)
"""What a new connection starts without: the log unit of the request its context was copied from.

The logging bundle registers it with the container, so a request a server
starts from a copy of an earlier one's context logs into no unit of that one.
"""

# Set only for the token it returns. A token resets in the very context that
# made it and in no copy of it, and only once — which is what tells the context
# that began a unit apart from one that merely carries it.
_BEGUN: ContextVar[None] = ContextVar("xtr_logging_unit_begun", default=None)


def begin_unit() -> None:
    """Open a fresh unit of work in the current context.

    A unit this context began and never ended is ended first, so a caller that
    forgot :func:`end_unit` cannot leak one unit's state into the next. A unit
    the context only carries is let go of the way :func:`end_unit` lets go of
    one. The new unit is open even when ending the earlier one raised.

    Raises:
        ExceptionGroup: If one or more end callbacks of the earlier unit raised.
    """
    try:
        end_unit()
    finally:
        _ = _CURRENT.set(_Unit())


def in_unit() -> bool:
    """Whether a unit of work is open in the current context."""
    unit = _CURRENT.get()
    return unit is not None and not unit.ended


def in_closed_unit() -> bool:
    """Whether the current context carries a unit of work that is over and closed.

    A handler keeping state per unit handles a record arriving there at
    once, by the rule it applies when a unit ends: nobody ends that unit
    again, so whatever it kept there would be stranded.
    """
    unit = _CURRENT.get()
    return unit is not None and unit.closed


def end_unit() -> None:
    """Close the unit this context began, running every end callback, then clear the context.

    Callbacks run in registration order. Every one runs even if an earlier one
    raised; the failures are then raised together as an :class:`ExceptionGroup`.
    Does nothing when no unit is open. A unit work is still queued for closes
    — and its callbacks run — once that work releases it; see :func:`hold_unit`.

    A unit the context only carries — begun in the context this one was copied
    from — is let go of rather than ended: the context is cleared and nothing
    else, its callbacks being for whoever began it. Once that unit is closed
    it hands out no state, so nothing this context logs can be stranded in it.

    Raises:
        ExceptionGroup: If one or more end callbacks raised.
    """
    unit = _CURRENT.get()
    if unit is None:
        return
    try:
        if _began_here(unit):
            _end(unit)
    finally:
        _ = _CURRENT.set(None)


def enter_nested_unit() -> object:
    """Open a unit of work of its own in the current context, inside whichever one is open.

    For work that is new rather than part of the unit around it — a message
    handled inside a request: what it logs is its own until it ends.

    Returns:
        What :func:`exit_nested_unit` is handed to close it.
    """
    unit = _Unit()
    return _Nested(unit, _CURRENT.set(unit))


def exit_nested_unit(token: object) -> None:
    """End the unit :func:`enter_nested_unit` opened, and open the one around it again.

    The unit is ended — its end callbacks run, once nothing holds it —
    whichever context ends it: it may be exited from another task than the
    one that entered it. Only the context that entered it has the unit
    around it put back.

    Args:
        token: What :func:`enter_nested_unit` returned.

    Raises:
        ExceptionGroup: If one or more end callbacks raised; the unit around
            it is open again all the same.
    """
    # Handed back exactly what enter_nested_unit returned.
    nested = cast("_Nested", token)
    # Spent, so a context carrying the unit never takes itself for the one that began it.
    _ = _began_here(nested.unit)
    try:
        _end(nested.unit)
    finally:
        # Refused when the exiting context is not the one that entered: it never
        # held this unit, so there is nothing of ours to put back.
        with suppress(ValueError):
            _CURRENT.reset(nested.previous)


def hold_unit() -> Callable[[], None] | None:
    """Keep the unit open here from closing until the returned release is called.

    For work queued for the unit and done later, elsewhere — a record a
    queue's worker thread writes: ended meanwhile, the unit closes, and its
    end callbacks run, when the last hold is released, so they see what that
    work put into it. Call the release once, in a context carrying the unit;
    the end callbacks then run there.

    Returns:
        The release, or ``None`` when no unit is carried here or it is closed
        already — there is nothing to hold then.
    """
    unit = _CURRENT.get()
    if unit is None:
        return None
    with unit.lock:
        if unit.closed:
            return None
        unit.holds += 1
    return partial(_release, unit)


def _end(unit: _Unit) -> None:
    """End ``unit``, closing it now unless work still holds it."""
    with unit.lock:
        unit.ended = True
        if unit.holds or unit.closed:
            return
        unit.closed = True
    _run_callbacks(unit)


def _release(unit: _Unit) -> None:
    """Release one hold on ``unit``, closing it if it ended and this was the last."""
    with unit.lock:
        unit.holds -= 1
        if unit.holds or not unit.ended or unit.closed:
            return
        unit.closed = True
    _run_callbacks(unit)


def _run_callbacks(unit: _Unit) -> None:
    """Run every end callback of ``unit``, in registration order, then raise the failures together.

    Raises:
        ExceptionGroup: If one or more end callbacks raised.
    """
    failures: list[Exception] = []
    for callback in unit.callbacks:
        try:
            _ = callback()
        except Exception as error:  # noqa: BLE001 — run every callback, then raise all failures together
            failures.append(error)
    if failures:
        raise ExceptionGroup("errors ending a unit of work", failures)


def _began_here(unit: _Unit) -> bool:
    """Tell whether the current context began ``unit``, the one time it ends it."""
    try:
        _BEGUN.reset(unit.begun)
    except (ValueError, RuntimeError):
        # The mark was made in another context, or this one already spent it.
        return False
    return True


def unit_state(
    owner: object,
    factory: Callable[[], _T],
    on_end: Callable[[_T], object] | None = None,
) -> _T | None:
    """Return ``owner``'s state in the unit carried here, or ``None`` outside one.

    The state is created with ``factory()`` the first time ``owner`` asks in a
    unit and returned unchanged on every later call, so an owner keeps one
    mutable object per unit and mutates it in place. When given, ``on_end`` is
    registered the moment the state is created and called with that state when
    the unit closes. A closed unit — one a context still carries once it is
    over — is no unit: it hands out nothing, and takes no callback it would
    never run.

    Args:
        owner: The object the state belongs to; distinct owners keep distinct
            state within one unit.
        factory: Builds the state on first use in a unit.
        on_end: Called with the state when the unit closes, registered once.

    Returns:
        The owner's state for the unit, or ``None`` if none is carried here or
        it is closed.
    """
    unit = _CURRENT.get()
    if unit is None or unit.closed:
        return None
    key = id(owner)
    if key in unit.state:
        return cast("_T", unit.state[key])
    state = factory()
    unit.state[key] = state
    if on_end is not None:
        unit.callbacks.append(partial(on_end, state))
    return state
