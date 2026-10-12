"""One of this library's own objects was used in a way it cannot answer for."""

from __future__ import annotations

from .oauth2_error import OAuth2Error

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(OAuth2Error, ValueError):
    """A call into this library was malformed, and no client caused it.

    An access token asked for its string form before it was handed a signer, an
    extra claim taking a name the token mints itself, an authorization request
    read before the server had understood it, an encryption key that is not a
    key — mistakes caught where they are made.

    Deliberately not an ``OAuthServerError``: that one *is* the answer a client
    gets, and there is no answer to give here, because nothing a client sent
    caused it. Whoever catches one has a wiring or an ordering mistake to fix,
    so it derives from :class:`OAuth2Error` — one ``except OAuth2Error`` still
    catches everything this library raises — and from nothing of the security
    family, which only answers failed authentication.

    Also a :class:`ValueError`, so code guarding a call with ``except
    ValueError`` keeps working, the same reason the security family's error of
    this name is one.
    """
