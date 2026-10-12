"""The scopes a token is about to be granted, open for the last word."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.model.client_interface import ClientInterface
    from xtr_security_oauth2_server.value_object.grant import Grant
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ScopeResolveEvent"]


class ScopeResolveEvent(Event):
    """Carries the scopes settled so far, and the context to change them by.

    Announced after the client's own registration has already narrowed the
    requested set, and what the event holds when the last listener has run is
    what the token carries — so this really is the last word on what a token
    may do.

    The grant, the client and the resource owner are all here because a rule
    about scopes is usually a rule about one of them: a scope only one client
    may have, a scope no refresh may widen into, a scope that depends on who
    the token acts for.
    """

    def __init__(
        self,
        scopes: Sequence[Scope],
        grant: Grant,
        client: ClientInterface,
        user_identifier: str | None,
    ) -> None:
        """Announce ``scopes``, about to be granted to ``client`` under ``grant``."""
        self._scopes: tuple[Scope, ...] = tuple(scopes)
        self._grant: Grant = grant
        self._client: ClientInterface = client
        self._user_identifier: str | None = user_identifier

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes as they stand."""
        return self._scopes

    def set_scopes(self, *scopes: Scope) -> Self:
        """Grant exactly ``scopes``, or none at all when given none."""
        self._scopes = scopes

        return self

    def get_grant(self) -> Grant:
        """Return the grant handing the scopes out."""
        return self._grant

    def get_client(self) -> ClientInterface:
        """Return the client asking."""
        return self._client

    def get_user_identifier(self) -> str | None:
        """Return the resource owner the token will act for, or ``None`` for none."""
        return self._user_identifier

    @override
    def __repr__(self) -> str:
        """Name the grant, the client and how many scopes are left.

        The scope names are left out for brevity rather than secrecy: they are
        readable wherever the event is being handled, and a count is what a
        reader wants from a log line.
        """
        return (
            f"{type(self).__name__}(grant={self._grant!r}, client={self._client!r}, "
            f"scopes={len(self._scopes)})"
        )
