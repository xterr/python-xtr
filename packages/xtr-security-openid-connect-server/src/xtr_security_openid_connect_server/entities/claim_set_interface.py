"""What a user's claims are read through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ClaimSetInterface"]


@runtime_checkable
class ClaimSetInterface(Protocol):
    """The claims an end-user holds, each under its name.

    A claim is one thing known about the user — ``name``, ``email``,
    ``email_verified``. This hands back every claim the user has, whatever a
    token was granted: which of them a token reveals is decided afterwards, by
    the claim sets of its scopes
    (:class:`~xtr_security_openid_connect_server.entities.ClaimSetEntityInterface`),
    so a user is described once and serves every scope.

    The reading is awaitable because the claims often live apart from the
    object naming the user — in a profile store, a directory — and reading
    them may reach it.
    """

    async def get_claims(self) -> Mapping[str, object]:
        """Return every claim this user holds, keyed by claim name.

        A claim the user does not have is left out rather than given as
        ``None`` or an empty string: a client reads a claim that is present as
        one that is known. Each value is one JSON can carry — a string, a
        number, a boolean, or an object such as ``address`` — because claims
        are answered as JSON.
        """
        ...
