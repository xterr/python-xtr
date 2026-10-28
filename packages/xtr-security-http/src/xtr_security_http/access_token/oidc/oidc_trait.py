"""What the OIDC access-token handlers share: the user, and the endpoints discovery announces."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from xtr_security_core.user.oidc_user import OidcUser

from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["OidcTrait"]


class OidcTrait:
    """The behaviour every OIDC access-token handler shares.

    A mixin rather than a base class: a handler brings it in for the two
    behaviours it owns — building the local user from an issuer's claims, and
    weighing an endpoint a discovery document announces — and keeps its own
    constructor and its own way of failing. Both behaviours answer in terms
    of what the issuer said, so they read the same whatever handler asks.
    """

    __slots__: tuple[str, ...] = ()

    def create_user(self, claims: Mapping[str, object]) -> OidcUser:
        """Build the local OIDC user from the claims an issuer answered with.

        Every claim is mapped — the standard ones onto the user's typed
        fields, the rest onto its additional claims — so only claims an
        issuer was trusted for should ever reach here; see
        :meth:`OidcUser.from_claims
        <xtr_security_core.user.oidc_user.OidcUser.from_claims>`.

        Raises:
            InvalidArgumentError: When the ``sub`` claim is missing or empty.
        """
        return OidcUser.from_claims(claims)

    @staticmethod
    def check_discovered_endpoint(endpoint: object, key: str, discovery_url: str | None) -> str:
        """Return ``endpoint``, refusing one a discovery document must not announce.

        The discovery document is fetched from the issuer, so a tampered or
        misconfigured one must not be able to downgrade a request to plain
        HTTP: an endpoint it announces is refused when it names a scheme
        other than ``https`` while the document itself was served over
        ``https`` — the transport that carried the document is the least an
        endpoint it names may promise. An endpoint that is not a non-empty
        string is refused outright: the document announces no endpoint at
        all. An endpoint naming no scheme is taken as it stands, the way a
        relative announcement would be.

        Args:
            endpoint: The endpoint the discovery document announced.
            key: The document member the endpoint was read from, named in
                the refusal.
            discovery_url: The URL the discovery document was served from,
                or ``None`` when it is not known — the announcement is then
                the only thing enforced, the scheme having been weighed
                where the document was fetched.

        Returns:
            The endpoint, unchanged, when it may be used.

        Raises:
            InvalidAccessTokenError: When the endpoint is missing, or
                downgrades the transport that carried the discovery
                document.
        """
        if not isinstance(endpoint, str) or not endpoint:
            raise InvalidAccessTokenError(
                f'The "{key}" is missing from the OIDC discovery document.',
            )
        scheme = urlsplit(endpoint).scheme
        if (
            scheme
            and scheme.lower() != "https"
            and discovery_url is not None
            and discovery_url.startswith("https://")
        ):
            raise InvalidAccessTokenError(
                f'The "{key}" found in the OIDC discovery document must use the '
                f'"https" scheme, "{scheme}" given.',
            )
        return endpoint
