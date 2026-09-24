"""Ambient context that follows the flow of control, not the call stack.

Threading a dict of request-scoped fields — a request id, the current user —
through every function that might log is noise. Bind them once here and every
record made downstream carries them, because a :class:`~contextvars.ContextVar`
is copied into each thread and each :mod:`asyncio` task: two requests handled at
once keep their own bindings, with no lock and no leakage between them.

The stored mapping is replaced, never mutated, so a record that captured it
sees what was bound when it was made even if the block goes on to bind more.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Generator

    from .log_record import Context

__all__ = [
    "bind_context",
    "bound_context",
    "clear_context",
    "current_context",
    "unbind_context",
]

_EMPTY: Final[Context] = MappingProxyType({})

_CONTEXT: ContextVar[Context] = ContextVar("xtr_logging_context", default=_EMPTY)


def bind_context(values: Context) -> None:
    """Add ``values`` to the ambient context, overwriting any keys they share."""
    _ = _CONTEXT.set(MappingProxyType({**_CONTEXT.get(), **values}))


def unbind_context(*keys: str) -> None:
    """Remove ``keys`` from the ambient context; keys not bound are ignored."""
    current = _CONTEXT.get()
    remaining = {key: value for key, value in current.items() if key not in keys}
    if len(remaining) != len(current):
        _ = _CONTEXT.set(MappingProxyType(remaining))


def clear_context() -> None:
    """Drop every bound value."""
    _ = _CONTEXT.set(_EMPTY)


def current_context() -> Context:
    """The values bound in this thread or task, as a read-only mapping."""
    return _CONTEXT.get()


@contextmanager
def bound_context(values: Context) -> Generator[None]:
    """Bind ``values`` for the duration of the block, then restore what was there.

    Nesting merges: inside the block the ambient context is what was bound
    before plus ``values``, with ``values`` winning a clash. The previous state
    is put back on the way out whether the block returns or raises.
    """
    token = _CONTEXT.set(MappingProxyType({**_CONTEXT.get(), **values}))
    try:
        yield
    finally:
        _CONTEXT.reset(token)
