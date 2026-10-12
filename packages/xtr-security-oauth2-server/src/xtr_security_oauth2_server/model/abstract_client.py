"""The stored client every client class here starts from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override

from ._short_identifier import short_identifier

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.value_object.grant import Grant
    from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["AbstractClient"]


# Deliberately not a subclass of ClientInterface, although it satisfies it:
# an application maps its own client class on this base together with a
# declarative one of its own, and a contract built by the typing machinery
# cannot share a class with a mapped base built by a different one — the two
# metaclasses collide and the application's class cannot be defined at all.
# Every reader here takes the contract, so nothing is lost by not declaring it.
class AbstractClient:
    """Holds a client's registration, and nothing about how it is stored.

    The base an application extends when its clients need columns of their
    own; :class:`~xtr_security_oauth2_server.model.client.Client` is the one
    shipped, and a deployment that needs no more uses it.

    Three things are fixed when a client is registered — what it is called,
    what it is called *by*, and the hash of its secret — because a client with
    no identifier is not a client, and a secret that arrives later would mean
    a window in which a confidential client is treated as a public one.
    Everything else is set afterwards, through setters that answer the client
    so a caller can chain them.

    A client with no grants may use any grant, and one with no scopes may ask
    for any scope. That is the registration a deployment gets when it says
    nothing, and it is the same rule for both lists, so a listing narrowed by
    either reads the same way.
    """

    def __init__(self, name: str, identifier: str, secret: str | None) -> None:
        """Register a client called ``name`` as ``identifier``, holding ``secret``.

        ``secret`` is a *hash*, or ``None`` for a public client. Nothing here
        hashes or compares it: the client repository does both, through the
        password hasher the deployment configured.
        """
        self._name: str = name
        self._identifier: str = identifier
        self._secret: str | None = secret
        self._redirect_uris: tuple[RedirectUri, ...] = ()
        self._grants: tuple[Grant, ...] = ()
        self._scopes: tuple[Scope, ...] = ()
        self._active: bool = True
        self._allow_plain_text_pkce: bool = False

    def get_identifier(self) -> str:
        """Return the identifier this client is registered under."""
        return self._identifier

    def get_name(self) -> str:
        """Return the name to show the resource owner when asking for consent."""
        return self._name

    def set_name(self, name: str) -> Self:
        """Rename this client ``name``."""
        self._name = name

        return self

    def get_secret(self) -> str | None:
        """Return the hash of this client's secret, or ``None`` when it has none."""
        return self._secret

    def set_secret(self, secret: str) -> None:
        """Replace the hash of this client's secret."""
        self._secret = secret

    def get_redirect_uris(self) -> Sequence[RedirectUri]:
        """Return every redirect URI this client may be sent back to."""
        return self._redirect_uris

    def set_redirect_uris(self, *redirect_uris: RedirectUri) -> Self:
        """Register ``redirect_uris`` as the ones this client may be sent back to."""
        self._redirect_uris = redirect_uris

        return self

    def get_grants(self) -> Sequence[Grant]:
        """Return the grants this client may use, or nothing for every grant."""
        return self._grants

    def set_grants(self, *grants: Grant) -> Self:
        """Allow this client exactly ``grants``, or every grant when given none."""
        self._grants = grants

        return self

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes this client may ask for, or nothing for any scope."""
        return self._scopes

    def set_scopes(self, *scopes: Scope) -> Self:
        """Allow this client exactly ``scopes``, or any scope when given none."""
        self._scopes = scopes

        return self

    def is_active(self) -> bool:
        """Tell whether this client may authenticate at all."""
        return self._active

    def set_active(self, active: bool) -> Self:
        """Let this client authenticate, or stop it from doing so."""
        self._active = active

        return self

    def is_confidential(self) -> bool:
        """Tell whether this client holds a secret, and so must prove one.

        An empty secret counts as none: a registration that stored one would
        otherwise make a client confidential while leaving it nothing to
        prove, and no secret a caller sent could ever match.
        """
        return self._secret is not None and self._secret != ""

    def is_plain_text_pkce_allowed(self) -> bool:
        """Tell whether this client may send an unhashed code challenge."""
        return self._allow_plain_text_pkce

    def set_allow_plain_text_pkce(self, allow_plain_text_pkce: bool) -> Self:
        """Choose whether this client may send an unhashed code challenge."""
        self._allow_plain_text_pkce = allow_plain_text_pkce

        return self

    @override
    def __repr__(self) -> str:
        """Name the type and the identifier, and nothing else.

        The secret is a hash, and a hash in a log line is an offline guessing
        target; the grants, scopes and redirect URIs are left out for brevity,
        since the client is readable in full wherever it is being handled.
        """
        return f"{type(self).__name__}(identifier={short_identifier(self._identifier)!r})"
