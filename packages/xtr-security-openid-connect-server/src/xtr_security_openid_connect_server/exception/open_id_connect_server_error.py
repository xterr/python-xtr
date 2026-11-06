"""The root every error in this package derives from."""

from __future__ import annotations

from xtr_security_oauth2_server_core.exception import OAuth2Error

__all__ = ["OpenIdConnectServerError"]


class OpenIdConnectServerError(OAuth2Error):
    """Base class for every error raised by this package.

    Catch this to handle anything the identity layer can go wrong with; catch
    a subclass to handle one cause.

    It derives from the authorization server's own root,
    :class:`~xtr_security_oauth2_server_core.exception.OAuth2Error`, because
    this package is a layer on that server, not a server of its own: one
    ``except OAuth2Error`` keeps catching everything a deployment's
    authorization server raises, the identity layer included.
    """
