"""Authenticates the client with a JWT it signs itself, the assertion of RFC 7523, Section 2.2.

Importing this module needs joserfc, which the ``oidc`` extra of
xtr-security-http carries: the assertion is signed here, and signing is the
JOSE library's business. The methods that hold no key of their own — the
secret sent as Basic credentials or in the body, the public client, the TLS
pair — live in modules that import nothing of the sort.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_security_core.exception import InvalidArgumentError

try:
    from joserfc import jwt
except ImportError as _error:  # pragma: no cover -- the oidc extra carries joserfc
    raise ImportError(
        "The OAuth2 client-assertion pieces need joserfc; install the 'oidc' extra: "
        'uv add "xtr-security-http[oidc]".',
    ) from _error

from .client_authentication_interface import ClientAuthenticationInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from joserfc.jwk import Key
    from xtr_clock import ClockInterface

__all__ = ["AbstractClientAssertion"]

_ASSERTION_TYPE: Final = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
"""The assertion format RFC 7523, Section 2.2 registers.

It is the only value the "client_assertion_type" parameter takes when the
assertion is a JWT."""

_EXPLICIT_TYPE: Final = "client-authentication+jwt"
"""The explicit type of a client-authentication JWT, which the revision of
RFC 7523 adds to its Section 3.2.

It is the "application/client-authentication+jwt" media type that draft
registers, without the "application/" prefix, as RFC 8725, Section 3.11
recommends."""


class AbstractClientAssertion(  # pyright: ignore[reportImplicitAbstractClass]  -- subclasses implement get_method
    ClientAuthenticationInterface,
):
    """Authenticates the client with a JWT it signs itself, the assertion of RFC 7523, Section 2.2.

    Nothing secret is then sent to the provider: the request carries a
    short-lived assertion naming the client as both its issuer and its
    subject, and the provider as its audience, so that an assertion captured
    at one provider cannot be replayed at another. What signs it is what
    tells the two methods built on this apart: :class:`PrivateKeyJwt` holds a
    key the provider only knows the public half of, :class:`ClientSecretJwt`
    the shared secret itself.

    The provider is named by the issuer identifier it announces when the
    constructor is given one, and by the token endpoint otherwise. The
    default is the token endpoint because nothing here can resolve an issuer
    on its own; the discovery reader that will is the caller's to build, and
    hands its ``issuer`` over.

    The assertion is single use: it carries a "jti" and a lifetime of a
    minute by default, which is what RFC 7523, Section 3, item 7 lets the
    provider reject a replay against.

    RFC 7523, Section 2.2 is the JWT client authentication; OIDC Core 1.0,
    Section 9 is the profile of it.
    """

    __slots__: tuple[str, ...] = (
        "_algorithm",
        "_clock",
        "_issuer",
        "_lifetime",
        "_signing_key",
    )

    _signing_key: Key
    _algorithm: str
    _lifetime: int
    _clock: ClockInterface
    _issuer: str | None

    def __init__(
        self,
        signing_key: Key,
        algorithm: str,
        lifetime: int,
        clock: ClockInterface | None = None,
        issuer: str | None = None,
    ) -> None:
        """Record the signing material, the lifetime and what names the provider.

        Args:
            signing_key: The key the assertion is signed with.
            algorithm: The JWA name of the algorithm it is signed with, which
                the subclass picked from the ones its method allows — see
                :meth:`create_algorithm`.
            lifetime: How long the assertion is valid, in seconds; it is
                built for one request and sent right away, so it is short by
                design.
            clock: What the assertion is dated with, or ``None`` for the
                system clock.
            issuer: The issuer identifier of the provider, which the
                assertion names as its audience, typed
                :data:`_EXPLICIT_TYPE`, or ``None`` to name the endpoint the
                request is made to, untyped.

        Raises:
            InvalidArgumentError: When ``lifetime`` is not a positive number
                of seconds.
        """
        if lifetime <= 0:
            raise InvalidArgumentError(
                f"The lifetime of an OAuth2 client assertion must be a positive number "
                f"of seconds, {lifetime} given.",
            )
        self._signing_key = signing_key
        self._algorithm = algorithm
        self._lifetime = lifetime
        self._clock = clock if clock is not None else SystemClock()
        self._issuer = issuer

    @final
    @override
    def authenticate(
        self,
        client_id: str,
        token_endpoint: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        """Add the assertion to the token request body, per RFC 7523, Section 2.2.

        It goes next to the "client_assertion_type" naming its format, and
        nothing else the request already carries is touched, the "client_id"
        of RFC 7521, Section 4.2 among it.

        Args:
            client_id: The client the request is made for.
            token_endpoint: The endpoint the request is made to.
            options: The request options the request is about to be made
                with, carrying the token request body under the "body" key.

        Returns:
            The request options, with "client_assertion_type" and
            "client_assertion" added to the body.
        """
        body = options.get("body")
        if not isinstance(body, dict):
            body = {}
            options["body"] = body
        body["client_assertion_type"] = _ASSERTION_TYPE
        body["client_assertion"] = self._create_assertion(client_id, token_endpoint)
        return options

    @staticmethod
    def create_algorithm(
        algorithm: str,
        allowed_algorithms: Mapping[str, str],
        method: str,
    ) -> str:
        """Resolve a JWA name to the algorithm it names, refusing the rest.

        The algorithm decides what the key may be, so this allow-list is what
        keeps a shared secret out of "private_key_jwt" and an asymmetric key
        out of "client_secret_jwt": either confusion turns a value one party
        holds into a signature the other party is supposed to be the only one
        able to make.

        Args:
            algorithm: The JWA name the caller chose.
            allowed_algorithms: The algorithms the method allows, indexed by
                their JWA name.
            method: The RFC 7591, Section 2 name of the method, quoted in the
                error messages.

        Returns:
            The same JWA name, once it is known to be allowed — the JOSE
            library selects the algorithm by it.

        Raises:
            InvalidArgumentError: When the algorithm is not one the method
                allows.
        """
        if algorithm not in allowed_algorithms:
            raise InvalidArgumentError(
                f'The "{algorithm}" algorithm cannot sign a "{method}" client assertion. '
                f'Use one of "{_joined(allowed_algorithms)}".',
            )
        return algorithm

    def _create_assertion(self, client_id: str, token_endpoint: str) -> str:
        """Build the assertion of RFC 7523, Section 3, and return it compact.

        The client is both the issuer and the subject, as Section 3, items 1
        and 2 require from a client authenticating itself. The audience is
        the issuer identifier of the provider when one was given to the
        constructor, which the revision of RFC 7523 makes the sole accepted
        value and FAPI 2.0 Security Profile, Section 5.3.3.1 already requires,
        because an assertion made for one endpoint of a provider is otherwise
        an assertion for every other endpoint of that same provider. Without
        one it is the endpoint the request is about to be made to, the value
        Section 3, item 3 and OIDC Core 1.0, Section 9 allowed a provider to
        expect: nothing here can resolve an issuer on its own, so the
        default of an application lives in its configuration rather than
        here.

        The "kid" header is set whenever the key carries one, so that a
        provider holding several public keys for the client knows which one
        verifies the signature without trying them all, as OIDC Core 1.0,
        Section 10.1 asks of a rotating client.

        The assertion is explicitly typed only when it names the issuer: the
        RFC 7523 revision makes the type the signal that an assertion
        follows its rules, the issuer audience among them, and asks servers
        not to reject an untyped assertion.
        """
        now = int(self._clock.now().timestamp())
        claims: dict[str, object] = {
            "iss": client_id,
            "sub": client_id,
            "aud": self._issuer if self._issuer is not None else token_endpoint,
            "jti": secrets.token_hex(16),
            "iat": now,
            "exp": now + self._lifetime,
        }
        header: dict[str, object] = {"alg": self._algorithm}
        if self._issuer is not None:
            header["typ"] = _EXPLICIT_TYPE
        kid = self._signing_key.kid
        if kid is not None:
            header["kid"] = kid
        # The chosen algorithm is named as allowed: the JOSE library refuses to
        # sign with one outside its recommended set unless it is told the
        # caller chose it.
        # The default "typ" the JOSE library adds is suppressed: the assertion
        # is typed only when it names the issuer, and nothing else types it.
        return jwt.encode(
            header,
            claims,
            self._signing_key,
            algorithms=[self._algorithm],
            default_type=None,
        )


def _joined(algorithms: Mapping[str, str]) -> str:
    """Join the algorithm names the way a refusal lists them: quoted, comma-separated."""
    return '", "'.join(algorithms)
