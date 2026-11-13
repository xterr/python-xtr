"""Where the unit of work open in this context is kept.

Kept apart from the public :mod:`~xtr_dependency_injection.runtime.unit_of_work`
so the engine glue — :func:`~xtr_dependency_injection.bind_callable` — can
read it without importing the container wrapper the public API hands out.
"""

from __future__ import annotations

import weakref
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from typing import TYPE_CHECKING, final

from wireup.errors import UnknownServiceRequestedError

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from wireup import AsyncContainer, ScopedAsyncContainer
    from xtr_service_contracts import UnitParticipantInterface

__all__ = [
    "Unit",
    "UnitParticipants",
    "current_unit_record",
    "entered",
    "open_unit",
    "participants_of",
    "participating",
]


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


@final
class UnitParticipants:
    """Every service tagged ``kernel.unit_participant``, in the order they are told."""

    __slots__ = ("participants",)

    def __init__(self, participants: Sequence[UnitParticipantInterface]) -> None:
        self.participants: tuple[UnitParticipantInterface, ...] = tuple(participants)


# Each engine's participants, looked up the first time one of its units opens.
_PARTICIPANTS: weakref.WeakKeyDictionary[AsyncContainer, tuple[UnitParticipantInterface, ...]] = (
    weakref.WeakKeyDictionary()
)


async def participants_of(engine: AsyncContainer) -> tuple[UnitParticipantInterface, ...]:
    """Return the participants told of every unit of work ``engine`` opens.

    Built the first time a unit opens rather than at boot, so a container
    never booted — one ``create_container`` compiled, one attached without a
    lifespan — still tells them; looked up before the unit is set, so their
    construction reads no unit. An engine no kernel compiled has none.
    """
    participants = _PARTICIPANTS.get(engine)
    if participants is None:
        try:
            participants = (await engine.get(UnitParticipants)).participants
        except UnknownServiceRequestedError:
            participants = ()
        _PARTICIPANTS[engine] = participants
    return participants


@contextmanager
def participating(participants: Sequence[UnitParticipantInterface]) -> Generator[None]:
    """Tell ``participants`` a unit of work begins, and that it ended once the block exits.

    Each is told it began in order, and it ended in reverse, handed back
    what it returned when it began. The tokens stay in this frame, never in
    a context variable, so a unit exited from another context still hands
    each participant its own.

    Raises:
        ExceptionGroup: When a participant fails to begin — those already
            begun are ended, and the block does not run — or, the block
            having succeeded, when any fails to end. A failure to end while
            the block raised is a note on the block's exception instead.
    """
    began: list[tuple[UnitParticipantInterface, object | None]] = []
    for participant in participants:
        try:
            began.append((participant, participant.unit_began()))
        except Exception as error:  # noqa: BLE001 — raised below, with any failure to end the ones begun
            failures = [error, *(failure for _, failure in _ended(began))]
            raise ExceptionGroup("a unit participant failed to begin the unit", failures) from None
    try:
        yield
    except BaseException as error:
        for participant, failure in _ended(began):
            error.add_note(f"{type(participant).__qualname__}.unit_ended failed: {failure!r}")
        raise
    failures = [failure for _, failure in _ended(began)]
    if failures:
        raise ExceptionGroup("a unit participant failed to end the unit", failures)


def _ended(
    began: Sequence[tuple[UnitParticipantInterface, object | None]],
) -> list[tuple[UnitParticipantInterface, Exception]]:
    """End every participant in ``began``, last first; return the ones that failed."""
    failures: list[tuple[UnitParticipantInterface, Exception]] = []
    for participant, token in reversed(began):
        try:
            participant.unit_ended(token)
        except Exception as error:  # noqa: BLE001 — collected: every participant is ended whatever another does
            failures.append((participant, error))
    return failures
