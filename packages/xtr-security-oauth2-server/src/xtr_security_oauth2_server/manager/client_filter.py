"""The criteria a client listing is narrowed by."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.value_object.grant import Grant
    from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["ClientFilter"]


@final
class ClientFilter:
    """What to narrow a listing of clients by, built up one criterion at a time.

    Three kinds of criterion, and a client has to hold everything that was
    named: a filter naming a grant and a scope lists the clients holding that
    grant *and* that scope, and one naming two grants lists the clients
    registered for both.

    A filter that names nothing narrows nothing, and :meth:`has_filters` says
    which it is — a manager asks before building a query it does not need.

    Mutable and built by chaining, deliberately: the command that lists
    clients adds a criterion per option the caller passed, and reads better
    doing it in one expression.
    """

    __slots__ = ("_grants", "_redirect_uris", "_scopes")

    def __init__(self) -> None:
        """Start a filter that narrows nothing."""
        self._grants: tuple[Grant, ...] = ()
        self._redirect_uris: tuple[RedirectUri, ...] = ()
        self._scopes: tuple[Scope, ...] = ()

    @classmethod
    def create(cls) -> Self:
        """Return a fresh filter, so a chain can start in an argument list."""
        return cls()

    def add_grant_criteria(self, *grants: Grant) -> Self:
        """Narrow the listing to the clients holding any of ``grants``."""
        self._grants = (*self._grants, *grants)

        return self

    def add_redirect_uri_criteria(self, *redirect_uris: RedirectUri) -> Self:
        """Narrow the listing to the clients registered with any of ``redirect_uris``."""
        self._redirect_uris = (*self._redirect_uris, *redirect_uris)

        return self

    def add_scope_criteria(self, *scopes: Scope) -> Self:
        """Narrow the listing to the clients holding any of ``scopes``."""
        self._scopes = (*self._scopes, *scopes)

        return self

    def get_grants(self) -> Sequence[Grant]:
        """Return the grants named, in the order they were added."""
        return self._grants

    def get_redirect_uris(self) -> Sequence[RedirectUri]:
        """Return the redirect URIs named, in the order they were added."""
        return self._redirect_uris

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes named, in the order they were added."""
        return self._scopes

    def has_filters(self) -> bool:
        """Tell whether anything was named at all."""
        return bool(self._grants or self._redirect_uris or self._scopes)
