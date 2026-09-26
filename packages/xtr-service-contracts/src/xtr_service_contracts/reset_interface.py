"""Something holding state that must not leak from one unit of work to the next."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ResetInterface"]


@runtime_checkable
class ResetInterface(Protocol):
    r"""Returns to a clean state between units of work.

    A long-running process — a worker consuming messages, a server answering
    requests — builds its services once and uses them many times. Buffers,
    caches, accumulated state and generated ids belong to one unit of work
    rather than to the service that holds them; :meth:`reset` ends that unit,
    so the next starts clean while configuration survives.

    A container is the usual caller. It knows what it built, so it can reset
    whatever asks for it between units of work, and neither side has to know
    anything else about the other.

    Named after Symfony's ``Symfony\Contracts\Service\ResetInterface``.
    """

    def reset(self) -> None: ...  # noqa: D102 — documented by the class docstring
