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

A unit belongs to the context that began it, and ends there. A copy of that
context only carries the unit — a task started inside it, or a request a
server began from an earlier request's context — and beginning or ending a
unit there does not end one still open where it began: whoever began it is
still filling it, and ends it. A carried unit that is already over is flushed
once more as it is let go of, so what was logged into it late is not stranded.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from functools import partial
from typing import TYPE_CHECKING, TypeVar, cast, final

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["begin_unit", "end_unit", "in_unit", "unit_state"]

_T = TypeVar("_T")


@final
class _Unit:
    """The state of one unit of work: per-owner state plus its end callbacks.

    Built in the context that begins the unit: ``begun`` is that context's
    mark on it, and ``ended`` turns true once that context has ended it.
    """

    __slots__ = ("begun", "callbacks", "ended", "state")

    def __init__(self) -> None:
        self.state: dict[int, object] = {}
        self.callbacks: list[Callable[[], object]] = []
        self.begun: Token[None] = _BEGUN.set(None)
        self.ended = False


_CURRENT: ContextVar[_Unit | None] = ContextVar("xtr_logging_unit", default=None)

# Set only for the token it returns. A token resets in the very context that
# made it and in no copy of it, and only once — which is what tells the context
# that began a unit apart from one that merely carries it.
_BEGUN: ContextVar[None] = ContextVar("xtr_logging_unit_begun", default=None)


def begin_unit() -> None:
    """Open a fresh unit of work in the current context.

    A unit this context began and never ended is ended first, so a caller that
    forgot :func:`end_unit` cannot leak one unit's state into the next. A unit
    the context only carries is let go of the way :func:`end_unit` lets go of
    one.
    """
    end_unit()
    _ = _CURRENT.set(_Unit())


def in_unit() -> bool:
    """Whether a unit of work is open in the current context."""
    return _CURRENT.get() is not None


def end_unit() -> None:
    """Close the unit this context began, running every end callback, then clear the context.

    Callbacks run in registration order. Every one runs even if an earlier one
    raised; the failures are then raised together as an :class:`ExceptionGroup`.
    Does nothing when no unit is open.

    A unit the context only carries — begun in the context this one was copied
    from — is let go of rather than ended. While it is still open where it
    began, the context is cleared and nothing else: its callbacks are for
    whoever began it. Once it is over there, its callbacks run again first, so
    what this context logged into it since is flushed rather than stranded.

    Raises:
        ExceptionGroup: If one or more end callbacks raised.
    """
    unit = _CURRENT.get()
    if unit is None:
        return
    if _began_here(unit):
        unit.ended = True
    elif not unit.ended:
        _ = _CURRENT.set(None)
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
