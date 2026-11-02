"""A transport holding a connection open between emails."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .transport_interface import TransportInterface

__all__ = ["StoppableTransportInterface"]


@runtime_checkable
class StoppableTransportInterface(TransportInterface, Protocol):
    """A transport that keeps what it connected to between emails, and can let it go.

    A transport that talks to a server or a child process keeps the session open, so the next
    email skips connecting again. :meth:`stop` ends it — when the application shuts down, or a
    long-running worker wants a fresh one. A transport grouping others stops each of them that
    can be stopped.
    """

    async def stop(self) -> None:
        """End the session; the next send opens a new one."""
        ...
