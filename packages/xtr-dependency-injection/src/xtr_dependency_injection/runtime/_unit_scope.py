"""Where the unit of work open in this context is kept.

Kept apart from the public :mod:`~xtr_dependency_injection.runtime.unit_of_work`
so the engine glue — :func:`~xtr_dependency_injection.bind_callable` — can
read it without importing the container wrapper the public API hands out.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Generator

    from wireup import AsyncContainer, ScopedAsyncContainer

__all__ = ["Unit", "current_unit_record", "entered", "open_unit"]


@final
class Unit:
    """One unit of work: the engine it was opened on, and its scope until it exits.

    A context copied while the unit is open — a task it started, a request a
    server began from an earlier one's context — keeps pointing at it after it
    is over, and so does every container handed out for it. The scope is
    dropped at the exit so such a context finds no unit there, and such a
    container refuses to resolve, rather than handing out scoped services
    that have been released.
    """

    __slots__ = ("engine", "scope")

    def __init__(self, engine: AsyncContainer, scope: ScopedAsyncContainer) -> None:
        self.engine = engine
        self.scope: ScopedAsyncContainer | None = scope

    @property
    def closed(self) -> bool:
        """Whether the unit has exited, its scoped services released."""
        return self.scope is None


# The units of work this context was handed, innermost last; each open for as
# long as it holds a scope. A chain, not one slot, so the units of several
# kernels nest: a unit of one kernel opened inside another kernel's still
# finds the outer one of its own kernel.
_current: ContextVar[tuple[Unit, ...]] = ContextVar(
    "xtr_dependency_injection_unit_of_work", default=()
)


def current_unit_record() -> Unit | None:
    """Return the innermost unit of work open in this context, if any."""
    return next((unit for unit in reversed(_current.get()) if not unit.closed), None)


def open_unit(engine: AsyncContainer) -> Unit | None:
    """Return the innermost unit of work open in this context on ``engine``, if any.

    A unit another engine opened — a second kernel's — is not ``engine``'s to join.
    """
    return next(
        (unit for unit in reversed(_current.get()) if unit.engine is engine and not unit.closed),
        None,
    )


@contextmanager
def entered(engine: AsyncContainer, scope: ScopedAsyncContainer) -> Generator[Unit]:
    """Make ``scope`` of ``engine`` this context's unit of work until the block exits.

    The unit is closed first, for every context that carries it, so a block
    exited from another context than the one it was entered in — a context
    manager handed to another task — still leaves no context finding it open.
    """
    unit = Unit(engine, scope)
    token = _current.set((*_current.get(), unit))
    try:
        yield unit
    finally:
        unit.scope = None
        # Refused when the exiting context is not the one that entered: it
        # never held this unit, so there is nothing of ours to restore there.
        with suppress(ValueError):
            _current.reset(token)
