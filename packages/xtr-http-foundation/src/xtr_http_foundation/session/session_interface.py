"""The one surface every session answers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["SessionInterface"]


@runtime_checkable
class SessionInterface(Protocol):
    """The attributes a stateful request carries, under an ID the cookie reattaches.

    Every member that can reach the storage is awaited — one storage must be
    swappable for another, and a remote one is awaited — exactly as every
    matcher is awaited even when it only reads the head of a request. The
    three that cannot reach it answer from memory alone.

    The first member that touches the attributes starts the session, so a
    request that never asks for its session never loads one, and ``save()``
    on a session that was never started does nothing, so the listener that
    saves every response needs no condition of its own.
    """

    async def start(self) -> None:
        """Load the attributes the storage holds under the ID.

        Idempotent. The first member that touches the attributes starts the
        session, so a caller rarely needs this one; it is the way to pay for
        the session up front, before a response is half-written.

        Raises:
            SessionError: When the storage fails to load the session.
        """
        ...

    def is_started(self) -> bool:
        """Tell whether the attributes were loaded for this request."""
        ...

    async def get(self, name: str, default: object | None = None) -> object | None:
        """Return the attribute under ``name``, or ``default`` when there is none.

        Starts the session when it was not started.
        """
        ...

    async def set(self, name: str, value: object) -> None:
        """Set the attribute under ``name`` to ``value``.

        Starts the session when it was not started. The value is kept as it
        was given; what it must be to survive the storage is the storage's
        own contract, and it is heard at ``save()``.
        """
        ...

    async def has(self, name: str) -> bool:
        """Tell whether the session carries an attribute under ``name``.

        Starts the session when it was not started.
        """
        ...

    async def remove(self, name: str) -> object | None:
        """Drop the attribute under ``name``, returning the value it had.

        Returning what was removed saves a caller that wants the value — an
        error message shown once, a path redirected to — from reading it
        first and dropping it after. Starts the session when it was not
        started.
        """
        ...

    async def clear(self) -> None:
        """Drop every attribute the session carries.

        The stored entry follows at ``save()``, which deletes it rather
        than writing an empty one. Starts the session when it was not
        started, so the attributes still stored are dropped with the rest.
        """
        ...

    async def migrate(self, destroy_old: bool = False) -> None:
        """Carry the attributes to a new ID, keeping every one of them.

        The old entry is deleted only when ``destroy_old`` says so — a
        session that may still be open in another request keeps its entry
        until the one rotating the ID decides the old one is dead. Starts
        the session when it was not started, so what is stored under the
        old ID travels with it.

        Args:
            destroy_old: Whether to delete the entry stored under the old ID.
        """
        ...

    async def invalidate(self) -> None:
        """Empty the session and carry what is left — nothing — to a new ID.

        The attributes are dropped and the entry under the old ID deleted,
        so nothing of the session survives but the session itself; the
        cookie is issued again under the new ID.
        """
        ...

    async def save(self) -> None:
        """Write the attributes through the storage.

        A session that was never started is left alone — there is nothing
        to write and no entry to make — and one that holds no attribute
        deletes the stored entry rather than writing an empty one.

        Raises:
            SessionError: When the storage fails to write or to delete.
            InvalidArgumentError: When the storage keeps values in a format
                an attribute cannot round-trip — the cache-pool storage
                refuses one here, at the boundary, rather than losing it
                quietly.
        """
        ...

    def get_id(self) -> str:
        """Return the ID the session is known under, decided at construction."""
        ...

    def staged_set_cookie(self) -> str | None:
        """Return the ``Set-Cookie`` value that carries the ID, when it must be sent.

        The cookie is staged when the ID was made for this request — no
        readable one arrived — or was changed by ``migrate()`` or
        ``invalidate()``; a request that reattached the ID it was given
        sends nothing, so the client is not told a cookie it already has.

        Returns:
            The header value, ready for the response's ``Set-Cookie``, or
            ``None`` when the ID the request arrived with still stands.
        """
        ...
