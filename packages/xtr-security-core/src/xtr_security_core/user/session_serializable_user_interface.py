"""A user a session can keep whole, and rebuild as the class it is."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from .user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SessionSerializableUserInterface"]


@runtime_checkable
class SessionSerializableUserInterface(UserInterface, Protocol):
    """A user that turns itself into JSON for a session, and back.

    A stateful firewall keeps the user a token carries in the session between
    requests, and a session holds JSON only. A user implementing this is kept
    as the state :meth:`to_session` answers and rebuilt as its own class by
    :meth:`from_session`, so the firewall's provider is handed it through
    ``refresh_user``. Any other user is kept as a snapshot — its identifier, its
    roles and a digest of its password — and reloaded by its identifier
    instead.

    Inherit it explicitly: the class a session names is found again among the
    classes already loaded, by their inheritance, so a user that merely has
    the two methods is not one a session rebuilds — it is kept as a snapshot.

    The state must hold nothing a session store should not: never a password
    hash — keep :func:`~xtr_security_core.user.password_digest.password_digest`
    of it instead, which tells a changed password from the same one and
    verifies nothing. And the rebuilt user is a snapshot of what the session
    held, not the stored record: a provider reloads it, and never persists it
    or merges it into what it stores as it is.
    """

    def to_session(self) -> Mapping[str, object]:
        """Return the state this user is kept in a session as.

        Every value must come back from JSON exactly as it went in — strings,
        numbers, booleans, ``None``, lists and objects keyed by strings, never
        a tuple — or the token carrying the user is refused when the session
        is written.
        """
        ...

    @classmethod
    def from_session(cls, state: Mapping[str, object]) -> Self:
        """Rebuild the user a session kept as ``state``.

        Pure: no I/O, and nothing but ``state`` is read. Every field's type is
        checked, because the state comes back from a store outside the
        process.

        Raises:
            InvalidArgumentError: When ``state`` is malformed — a field
                missing or of the wrong type; the session then reads as
                holding no token.
        """
        ...
