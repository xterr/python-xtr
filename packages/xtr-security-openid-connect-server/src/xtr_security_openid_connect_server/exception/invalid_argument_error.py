"""One of this package's own objects was handed a value it cannot use."""

from __future__ import annotations

from .open_id_connect_server_error import OpenIdConnectServerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(OpenIdConnectServerError, ValueError):
    """A call into this package was malformed, and no client caused it.

    A claim set that names no scope, for one: no grant could ever reveal its
    claims. The mistake is caught where it is made, when the object is built,
    rather than surfacing later as claims that silently never appear.

    Deliberately not an ``OAuthServerError``: that one *is* the answer a
    client gets, and there is no answer to give here, because nothing a client
    sent caused it. Whoever catches one has a wiring mistake to fix.

    Also a :class:`ValueError`, so code guarding a call with ``except
    ValueError`` keeps working — the same reason the authorization server's
    error of this name is one.
    """
