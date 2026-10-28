"""The guard a public OIDC client must pass before its flow runs.

A public client — one registered to authenticate with "none" — sends no
secret: PKCE is then the only thing binding the authorization code to it,
and the ID token signature the only thing tying the token endpoint response
to the provider beyond the TLS verification. The guard is a policy of the
flow rather than a step of it — every entry point that starts or consumes
a login runs it — so it lives apart from the authenticator that calls it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface
    from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier

    from ._oidc_login_options import OidcLoginOptions

__all__ = ["check_public_client"]


def check_public_client(
    oidc_client: OidcClientInterface,
    options: OidcLoginOptions,
    signature_verifier: OidcSignatureVerifier | None,
) -> None:
    """Refuse a public client that turns PKCE or the ID token signature check off.

    This is checked when the flow runs rather than when the authenticator is
    created, so that the client can be a lazy service.

    Raises:
        InvalidArgumentError: When the configuration a public client cannot
            afford was given one.
    """
    if oidc_client.get_client_authentication_method() != "none":
        return
    if not options.pkce_enabled:
        raise InvalidArgumentError(
            "PKCE cannot be disabled for a public OIDC client, which authenticates "
            'with "none": it is the only thing binding the authorization code to '
            "this client.",
        )
    if signature_verifier is None:
        raise InvalidArgumentError(
            "The ID token signature must be verified for a public OIDC client, which "
            'authenticates with "none": without the check, only the TLS verification '
            "of the token request ties the ID token to the provider, which is too "
            "little for a client that has nothing but PKCE protecting its code "
            "exchange.",
        )
