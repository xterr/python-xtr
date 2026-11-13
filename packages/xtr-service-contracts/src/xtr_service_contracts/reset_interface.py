"""Something holding state that must not leak from one unit of work to the next."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ResetInterface"]


@runtime_checkable
class ResetInterface(Protocol):
    """Returns to a clean state between units of work.

    A long-running process — a worker consuming messages, a server answering
    requests — builds its services once and uses them many times. Buffers,
    caches, accumulated state and generated ids belong to one unit of work
    rather than to the service that holds them; :meth:`reset` ends that unit,
    so the next starts clean while configuration survives.

    A container is the usual caller. It knows what it built, so it can reset
    whatever asks for it between units of work, and neither side has to know
    anything else about the other.

    :meth:`reset` is awaited, because clearing state is not always a local
    assignment: a rate limiter's count or a cache's entries may live in
    another process entirely, and reaching them is I/O. A service whose state
    is its own awaits nothing and returns at once; one whose state lives
    elsewhere awaits the trip, and the caller — a worker between messages —
    is already somewhere it can wait.

    A container resets singletons only. A service built for one unit of work
    — scoped or transient — lives and dies with that unit, so it has nothing
    to reset. Units overlap — a worker handling several messages at once,
    requests answered together — so a singleton is reset while other units
    are still running: its :meth:`reset` must be safe then, clearing only
    what it can work out again, never state a running unit reads. A service
    that holds state for one unit keeps it in that unit — a scoped service,
    or state kept per unit of work — rather than waiting for a reset.

    Being ``@runtime_checkable`` costs precision: :func:`isinstance` confirms a
    ``reset`` attribute is present, not that it is callable, so an object whose
    ``reset`` is a plain value passes the check and then fails when called.
    Guard the call — ``callable(getattr(service, "reset", None))`` — rather
    than trust the check alone.

    A container's autoconfiguration keys on inheritance, so a service that
    means to be reset inherits this interface; a structural ``reset`` alone
    matches :func:`isinstance` but the container never sees it.
    """

    async def reset(self) -> None: ...  # noqa: D102 — documented by the class docstring
