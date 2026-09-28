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

    :meth:`reset` fits a unit of work that runs alone — one message, one
    command — where the service is idle between units and clearing its state
    is the whole story. When units overlap, as with concurrent requests
    answered on one set of services, there is no single "between" to reset
    into: each unit's state belongs to its own execution context, and it is
    ended by whatever opened the unit, not by a container calling this method.
    A service that must serve overlapping units keeps its per-unit state in
    context, so :meth:`reset` stays meaningful for the standalone case.

    Being ``@runtime_checkable`` costs precision: :func:`isinstance` confirms a
    ``reset`` attribute is present, not that it is callable, so an object whose
    ``reset`` is a plain value passes the check and then fails when called.
    Guard the call — ``callable(getattr(service, "reset", None))`` — rather
    than trust the check alone.

    A container's autoconfiguration keys on inheritance, so a service that
    means to be reset inherits this interface; a structural ``reset`` alone
    matches :func:`isinstance` but the container never sees it.
    """

    def reset(self) -> None: ...  # noqa: D102 — documented by the class docstring
