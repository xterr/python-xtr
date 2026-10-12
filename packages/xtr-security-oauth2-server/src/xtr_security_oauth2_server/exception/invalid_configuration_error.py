"""A deployment's configuration cannot be turned into an authorization server."""

from __future__ import annotations

from .oauth2_error import OAuth2Error

__all__ = ["InvalidConfigurationError"]


class InvalidConfigurationError(OAuth2Error, ValueError):
    """A server cannot be built out of what a deployment configured.

    An authorization server cannot be assembled out of defaults. It signs with
    a key only the deployment holds, seals its own payloads with another, says
    who it is in every token it mints, and reads its clients from a store
    somebody chose — and there is no safe stand-in for any of them. The bundle
    builds all the same, so a fresh application still runs its console; this
    is what the first service needing one of those settings raises, naming the
    setting and the file it belongs in.

    Also raised for a setting that is present but cannot be used: an encryption
    key of an unknown kind, a default scope that is not among the available
    ones, a grant registered twice under one identifier, a store named under
    ``persistence.custom`` that nothing registered.

    Deliberately not an ``OAuthServerError``: no client caused this and no
    client is waiting for it. It derives from :class:`OAuth2Error` — one
    ``except OAuth2Error`` still catches everything this library raises — and
    from :class:`ValueError`, because a configuration this server cannot read
    is a bad argument, the same reason the security family's error of this name
    is one.
    """
