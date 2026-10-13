"""The mark of a token built to decide access away from the current caller."""

from __future__ import annotations

from typing import Protocol

from .token_interface import TokenInterface

__all__ = ["OfflineTokenInterface"]


class OfflineTokenInterface(TokenInterface, Protocol):
    """A token standing in for a user who is not the current caller.

    :meth:`~xtr_security_core.authorization.authorization_checker.AuthorizationChecker.is_granted_for_user`
    builds one to decide access for a given user — or for a guest — rather than
    the one calling: a consent screen, a background worker. It carries that
    user's roles, so role checks decide as they would for the user; how that
    user authenticated is unknown, so a voter asked about authentication
    strength refuses to decide on one that carries a user.

    It adds nothing to :class:`TokenInterface`: it is a mark, declared by
    inheriting from it, and read nominally —
    ``OfflineTokenInterface in type(token).__mro__``. It is deliberately not
    runtime-checkable: with no member of its own, a structural check would
    match every token.
    """
