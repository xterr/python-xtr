"""Ambient context that follows the flow of control, not the call stack.

Threading a dict of request-scoped fields — a request id, the current user —
through every function that might log is noise. Bind them once here and every
record made downstream carries them, because a :class:`~contextvars.ContextVar`
is copied into each thread and each :mod:`asyncio` task: two requests handled at
once keep their own bindings, with no lock and no leakage between them.

The stored mapping is replaced, never mutated, so a record that captured it
sees what was bound when it was made even if the block goes on to bind more.

What is bound during a :mod:`unit of work <xtr_logging.log_unit>` is bound for
that unit; what is bound outside any unit lasts. A context does not always
end with the work it was made for — a server may start a request from a copy
of an earlier request's — so the values a request bound are tied to its unit
rather than left to whoever inherits the context: once another unit begins
there, or the unit ends where it began, they are gone. Work that still
carries the unit — a task it started, running on after it — keeps reading
them.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final

from .log_unit import unit_state

if TYPE_CHECKING:
    from collections.abc import Generator

    from xtr_logging_contracts import Context

__all__ = [
    "bind_context",
    "bound_context",
    "clear_context",
    "current_context",
    "unbind_context",
]

_EMPTY: Final[Context] = MappingProxyType({})


@final
@dataclass(frozen=True, slots=True)
class _Bound:
    """What is bound in one context, and how long each part of it is to last.

    Attributes:
        lasting: What was bound outside any unit of work.
        unit: What stands for the unit of work the rest was bound in, ``None``
            when nothing was bound in one.
        values: Everything bound: ``lasting``, and over it what was bound in
            ``unit``. Read only while that unit is the one open.
    """

    lasting: Context
    unit: object | None
    values: Context


_NOTHING: Final = _Bound(_EMPTY, None, _EMPTY)

_CONTEXT: ContextVar[_Bound] = ContextVar("xtr_logging_context", default=_NOTHING)

_UNIT_MARK: Final = object()
"""The owner under which each unit of work keeps the one object that stands for it."""


def bind_context(values: Context) -> None:
    """Add ``values`` to the ambient context, overwriting any keys they share."""
    _ = _CONTEXT.set(_holding({**current_context(), **values}))


def unbind_context(*keys: str) -> None:
    """Remove ``keys`` from the ambient context; keys not bound are ignored.

    Inside a unit of work a key bound outside any unit is set aside for that
    unit only, and is back once the unit is over.
    """
    current = current_context()
    remaining = {key: value for key, value in current.items() if key not in keys}
    if len(remaining) != len(current):
        _ = _CONTEXT.set(_holding(remaining))


def clear_context() -> None:
    """Drop every bound value."""
    _ = _CONTEXT.set(_NOTHING)


def current_context() -> Context:
    """The values bound in this thread or task, as a read-only mapping.

    What was bound in a unit of work other than the one open here is left
    out: it was bound for that unit.
    """
    bound = _CONTEXT.get()
    return bound.values if bound.unit is None or bound.unit is _unit() else bound.lasting


@contextmanager
def bound_context(values: Context) -> Generator[None]:
    """Bind ``values`` for the duration of the block, then restore what was there.

    Nesting merges: inside the block the ambient context is what was bound
    before plus ``values``, with ``values`` winning a clash. The previous state
    is put back on the way out whether the block returns or raises.
    """
    token = _CONTEXT.set(_holding({**current_context(), **values}))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def _unit() -> object | None:
    """Return what stands for the unit of work open here, or ``None`` outside one."""
    return unit_state(_UNIT_MARK, object)


def _holding(values: dict[str, object]) -> _Bound:
    """Return ``values`` as what is bound here: to last outside a unit, the unit's own in one."""
    held = MappingProxyType(values)
    unit = _unit()
    return _Bound(held if unit is None else _CONTEXT.get().lasting, unit, held)
