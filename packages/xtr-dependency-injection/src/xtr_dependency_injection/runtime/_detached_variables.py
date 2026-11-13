"""The context variables a new connection starts without, and the value each starts from.

A server may start a connection's task from a copy of an earlier connection's
context, taken mid-request. What that request opened — its unit of work, the
connection it serves — must not reach the new one, whatever the server
copied; everything else the context holds, a tracing span an outer wrapper
set, must. So each module holding per-request state in a context variable
registers it here, and a new connection starts in a copy of its context with
every registered variable set back.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextvars import ContextVar

__all__ = ["detach_variables", "register_detached_variable"]

T = TypeVar("T")

# Each registered variable, and what sets it back to the value a new connection starts from.
_DETACHED: dict[object, Callable[[], object]] = {}


def register_detached_variable(var: ContextVar[T], value: T) -> None:
    """Have every new connection start with ``var`` set to ``value``."""
    _DETACHED[var] = partial(var.set, value)


def detach_variables() -> None:
    """Set every registered variable back to the value a new connection starts from, here."""
    for detach in tuple(_DETACHED.values()):
        _ = detach()
