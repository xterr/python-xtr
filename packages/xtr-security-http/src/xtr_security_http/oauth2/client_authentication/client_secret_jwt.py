"""Authenticates the client with an assertion signed with its secret.

Importing this module needs joserfc, which the ``oidc`` extra of
xtr-security-http carries — the assertion is signed with the secret as an HMAC
key, and signing is the JOSE library's business.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

try:
    from joserfc.jwk import OctKey
except ImportError as _error:  # pragma: no cover -- the oidc extra carries joserfc
    raise ImportError(
        "The OAuth2 client-assertion pieces need joserfc; install the 'oidc' extra: "
        'uv add "xtr-security-http[oidc]".',
    ) from _error

from xtr_security_http.oauth2.jws_algorithms import JwsAlgorithms

from .abstract_client_assertion import AbstractClientAssertion

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

__all__ = ["ClientSecretJwt"]

_MINIMUM_KEY_BYTES: Final[dict[str, int]] = {"HS256": 32, "HS384": 48, "HS512": 64}
"""RFC 7518, Section 3.2: a MAC key must be at least as many bytes as the
hash it feeds produces. The JOSE library only warns where the upstream one
refuses, so the length is measured here, where the upstream suite exercises
the algorithm once on the key."""


@final
class ClientSecretJwt(AbstractClientAssertion):
    """Authenticates the client with an assertion signed with its secret.

    This is the "client_secret_jwt" method of OIDC Core 1.0, Section 9, which
    the same section defines as an HMAC keyed with "the octets of the UTF-8
    representation of the client_secret". The secret itself never leaves the
    client, unlike in "client_secret_post" and "client_secret_basic", but the
    provider still holds it and could sign an assertion in the name of the
    client: prefer :class:`PrivateKeyJwt`, which nobody but the client can
    sign.

    """

    def __init__(
        self,
        client_secret: str,
        algorithm: str = "HS256",
        lifetime: int = 60,
        clock: ClockInterface | None = None,
        issuer: str | None = None,
    ) -> None:
        """Record the secret, the algorithm and what every assertion carries.

        The secret is not measured by the algorithm here alone: RFC 7518,
        Section 3.2 gives a MAC key at least as many bytes as the digest it
        produces, and a secret it refuses fails on the service rather than on
        the first token request made with it.

        Args:
            client_secret: The secret shared with the provider, used as the
                HMAC key.
            algorithm: The JWA name of the MAC algorithm, which must be one
                the provider lists in the
                "token_endpoint_auth_signing_alg_values_supported" of its
                metadata.
            lifetime: How long the assertion is valid, in seconds.
            clock: What the assertion is dated with, or ``None`` for the
                system clock.
            issuer: The issuer identifier of the provider, which the assertion
                names as its audience, or ``None`` to name the endpoint the
                request is made to.

        Raises:
            InvalidArgumentError: When the secret is empty, the algorithm is
                not a MAC one, or the secret is too short to key it.
        """
        if not client_secret:
            raise InvalidArgumentError(
                "The OAuth2 client secret cannot be empty. Use NoClientAuthentication "
                "to declare a public client, which holds no secret.",
            )
        mac_algorithm = self.create_algorithm(algorithm, JwsAlgorithms.MAC, "client_secret_jwt")
        signing_key = OctKey.import_key(client_secret)
        required = _MINIMUM_KEY_BYTES[algorithm]
        raw_key = signing_key.raw_value
        if len(raw_key) < required:
            raise InvalidArgumentError(
                f'The OAuth2 client secret cannot key a "client_secret_jwt" assertion '
                f'signed with "{algorithm}", which asks for at least {required} bytes '
                "(RFC 7518, Section 3.2). Ask the provider for a longer secret, or "
                'authenticate the client with "PrivateKeyJwt".',
            )
        super().__init__(signing_key, mac_algorithm, lifetime, clock, issuer)

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "client_secret_jwt"."""
        return "client_secret_jwt"
