"""Authenticates the client with an assertion signed by its private key.

Constructing one needs joserfc, which the ``oidc`` extra of xtr-security-http
carries: the signing happens in :class:`AbstractClientAssertion`, whose module
carries the requirement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2.jws_algorithms import JwsAlgorithms

from .abstract_client_assertion import AbstractClientAssertion

if TYPE_CHECKING:
    from joserfc.jwk import Key
    from xtr_clock import ClockInterface

__all__ = ["PrivateKeyJwt"]


@final
class PrivateKeyJwt(AbstractClientAssertion):
    """Authenticates the client with an assertion signed by its private key.

    This is the "private_key_jwt" method of OIDC Core 1.0, Section 9, the one
    FAPI 2.0 asks for: the provider only ever holds the public half of the
    key, registered as the client "jwks" or fetched from its "jwks_uri", so a
    provider that is compromised, or one the client was tricked into talking
    to, learns nothing it could authenticate as the client with.

    """

    def __init__(
        self,
        signing_key: Key,
        algorithm: str = "RS256",
        lifetime: int = 60,
        clock: ClockInterface | None = None,
        issuer: str | None = None,
    ) -> None:
        """Record the key, the algorithm and what every assertion carries.

        Args:
            signing_key: The private key of the client, whose public half is
                registered at the provider.
            algorithm: The JWA name of the signature algorithm, which must be
                one the provider lists in the
                "token_endpoint_auth_signing_alg_values_supported" of its
                metadata.
            lifetime: How long the assertion is valid, in seconds.
            clock: What the assertion is dated with, or ``None`` for the
                system clock.
            issuer: The issuer identifier of the provider, which the assertion
                names as its audience, or ``None`` to name the endpoint the
                request is made to.

        Raises:
            InvalidArgumentError: When the algorithm is not an asymmetric one,
                the key cannot make the signatures it is named for, or the key
                is the public half.
        """
        signature_algorithm = self.create_algorithm(
            algorithm, JwsAlgorithms.ASYMMETRIC, "private_key_jwt"
        )
        JwsAlgorithms.check_key(signing_key, signature_algorithm)
        if signing_key.get("d") is None:
            raise InvalidArgumentError(
                'The "private_key_jwt" client assertion must be signed with the private '
                'key of the client, and the given JWK has no "d" parameter: it is the '
                "public key. Register that public key at the provider, and sign with "
                "the private one.",
            )
        super().__init__(signing_key, signature_algorithm, lifetime, clock, issuer)

    @override
    def get_method(self) -> str:
        """Return the RFC 7591, Section 2 name: "private_key_jwt"."""
        return "private_key_jwt"
