"""A deployment's configuration cannot be turned into an OpenID Connect provider."""

from __future__ import annotations

from .open_id_connect_server_error import OpenIdConnectServerError

__all__ = ["InvalidConfigurationError"]


class InvalidConfigurationError(OpenIdConnectServerError, ValueError):
    """An identity layer cannot be built out of what a deployment configured.

    Some of what signing a user in needs only the application can supply:
    where a signed-in user's claims come from, a login firewall that keeps a
    session to come back to after a re-login. The bundle builds and boots all
    the same, so a fresh application still runs its console; this is what the
    first service needing one of those settings raises, naming the setting and
    the file it belongs in.

    Also raised for a setting that is present but cannot be used, such as an
    authorization server setting the identity layer relies on that the
    application changed back after the bundle made it.

    Deliberately not an ``OAuthServerError``: no client caused this and no
    client is waiting for it. Also a :class:`ValueError`, because a
    configuration this package cannot read is a bad argument — the same reason
    the authorization server's error of this name is one.
    """
