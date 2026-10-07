"""Verifies a bearer token from a third-party OIDC issuer into a user badge."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from joserfc import jwt
from joserfc.errors import InvalidKeyIdError, JoseError
from joserfc.jwt import JWTClaimsRegistry
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_security_core.user.oidc_user import OidcUser

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

from .exception.oidc_key_set_error import OidcKeySetError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from joserfc.jwt import ClaimsOption, Token
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.authenticator.oidc.oidc_jwks import OidcKeySetProviderInterface

    UserLoader = Callable[[str], UserInterface | Awaitable[UserInterface]]

__all__ = ["OidcTokenHandler"]

_AT_JWT_TYPES = frozenset({"at+jwt", "application/at+jwt"})


@final
class OidcTokenHandler:
    """Turns a third-party OIDC access token into the badge naming its user.

    Verifies a token issued by an OIDC provider — not one this application
    signs: its signature against the provider's keys, its ``iss`` among the
    trusted issuers, its ``aud`` against the expected audience, and its
    ``exp`` / ``nbf`` / ``iat`` against the clock with a leeway. An ``exp`` is
    required — a token that never expires is refused. The algorithms
    are an explicit allow-list refusing ``none`` and any symmetric ``HS*`` (a
    third-party token is signed with the issuer's private key, verified with its
    public one). When ``enforce_at_jwt_type`` is set the header's ``typ`` must be
    ``at+jwt`` (RFC 9068).

    The identifier is read from ``claim`` (``sub`` by default). With no provider
    the claims are the user — an
    :class:`~xtr_security_core.user.oidc_user.OidcUser`; with one, its
    identifier loads the user, the claims handed alongside to a provider that
    reads them. The badge carries the granted ``scope`` (from the ``scope``
    string or the ``scp`` list), the ``client_id``, the ``jti`` and every claim.
    Every failure becomes an
    :class:`~xtr_security_http.exception.InvalidAccessTokenError`.
    """

    __slots__ = (
        "_algorithms",
        "_audience",
        "_claim",
        "_clock",
        "_enforce_at_jwt_type",
        "_issuers",
        "_key_set_provider",
        "_leeway",
        "_user_provider",
    )

    def __init__(  # noqa: PLR0913 -- a wiring constructor; the verification knobs default
        self,
        key_set_provider: OidcKeySetProviderInterface,
        *,
        issuers: Sequence[str],
        audience: str,
        algorithms: Sequence[str] = ("RS256",),
        claim: str = "sub",
        leeway: int = 0,
        enforce_at_jwt_type: bool = False,
        clock: Callable[[], int],
        user_provider: UserProviderInterface | None = None,
    ) -> None:
        """Record the provider, the trusted issuers, the audience and the knobs.

        Raises:
            InvalidArgumentError: When no issuer is given, or the algorithm
                allow-list is empty or holds ``none`` or a symmetric ``HS*``.
        """
        algorithm_list = tuple(algorithms)
        _check_algorithms(algorithm_list)
        if not issuers:
            raise InvalidArgumentError("An OIDC token handler needs at least one trusted issuer.")
        self._key_set_provider = key_set_provider
        self._issuers = tuple(issuers)
        self._audience = audience
        self._algorithms = algorithm_list
        self._claim = claim
        self._leeway = leeway
        self._enforce_at_jwt_type = enforce_at_jwt_type
        self._clock = clock
        self._user_provider = user_provider

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Verify ``access_token`` and return the badge naming its user.

        Raises:
            InvalidAccessTokenError: When the token is malformed, wrongly
                signed, from an untrusted issuer, for another audience, expired,
                not yet valid, of the wrong ``typ``, or missing its identifier.
        """
        decoded = await self._decode(access_token)
        claims = cast("Mapping[str, object]", decoded.claims)
        self._validate(decoded, claims)
        return self._badge_for(claims)

    async def _decode(self, access_token: str) -> Token:
        """Verify the signature, refetching the key set once on an unknown ``kid``.

        Raises:
            InvalidAccessTokenError: When the token cannot be verified.
        """
        try:
            key_set = await self._key_set_provider.get_key_set()
            return jwt.decode(access_token, key_set, algorithms=list(self._algorithms))
        except InvalidKeyIdError as error:
            return await self._decode_after_refresh(access_token, error)
        except (JoseError, OidcKeySetError, ValueError) as error:
            raise InvalidAccessTokenError(f"The token could not be verified: {error}") from error

    async def _decode_after_refresh(self, access_token: str, cause: InvalidKeyIdError) -> Token:
        """Refetch the key set once for a rotated key, then verify again.

        Raises:
            InvalidAccessTokenError: When the token still cannot be verified.
        """
        try:
            key_set = await self._key_set_provider.get_key_set(force_refresh=True)
            return jwt.decode(access_token, key_set, algorithms=list(self._algorithms))
        except (JoseError, OidcKeySetError, ValueError) as error:
            raise InvalidAccessTokenError(
                f"The token names an unknown key: {cause}",
            ) from error

    def _validate(self, decoded: Token, claims: Mapping[str, object]) -> None:
        """Check the ``typ`` header and the registered claims.

        Raises:
            InvalidAccessTokenError: When the type or a claim does not hold.
        """
        if self._enforce_at_jwt_type:
            typ = decoded.header.get("typ")
            if not isinstance(typ, str) or typ.lower() not in _AT_JWT_TYPES:
                raise InvalidAccessTokenError("The token is not an at+jwt access token.")
        options: dict[str, ClaimsOption] = {
            "iss": {"essential": True, "values": list(self._issuers)},
            "aud": {"essential": True, "value": self._audience},
            "exp": {"essential": True},
        }
        options[self._claim] = {**options.get(self._claim, {}), "essential": True}
        registry = JWTClaimsRegistry(now=self._clock(), leeway=self._leeway, **options)
        try:
            registry.validate(dict(claims))
        except (JoseError, ValueError) as error:
            raise InvalidAccessTokenError(f"The token's claims are not valid: {error}") from error

    def _badge_for(self, claims: Mapping[str, object]) -> UserBadge:
        """Build the badge for a verified token's claims.

        Raises:
            InvalidAccessTokenError: When the identifier claim is missing.
        """
        identifier = claims.get(self._claim)
        if not isinstance(identifier, str) or not identifier:
            raise InvalidAccessTokenError(
                f'The token carries no usable "{self._claim}" claim.',
            )
        attributes: dict[str, object] = {
            "scope": _scopes(claims),
            "client_id": claims.get("client_id"),
            "jti": claims.get("jti"),
            "claims": dict(claims),
        }
        return UserBadge(identifier, user_loader=self._loader(claims), attributes=attributes)

    def _loader(self, claims: Mapping[str, object]) -> UserLoader:
        """Return the loader that turns the identifier into a user.

        With no provider the claims are the user; with an attributes-based one
        the claims travel to it; with a plain one only the identifier does.
        """
        provider = self._user_provider
        claim = self._claim
        if provider is None:

            def load_from_claims(identifier: str) -> UserInterface:
                del identifier
                return OidcUser(claims, identifier_claim=claim)

            return load_from_claims
        if AttributesBasedUserProviderInterface in type(provider).__mro__:
            attributed = cast("AttributesBasedUserProviderInterface", provider)

            async def load_with_attributes(identifier: str) -> UserInterface:
                return await attributed.load_user_by_identifier(identifier, claims)

            return load_with_attributes

        plain = provider

        async def load_by_identifier(identifier: str) -> UserInterface:
            return await plain.load_user_by_identifier(identifier)

        return load_by_identifier


def _check_algorithms(algorithms: tuple[str, ...]) -> None:
    """Refuse an empty allow-list, ``none`` or a symmetric ``HS*``.

    Raises:
        InvalidArgumentError: When the allow-list is empty or holds a refused
            algorithm.
    """
    if not algorithms:
        raise InvalidArgumentError("An OIDC token handler needs at least one allowed algorithm.")
    for algorithm in algorithms:
        lowered = algorithm.lower()
        if lowered == "none":
            raise InvalidArgumentError('The algorithm "none" is never allowed.')
        if lowered.startswith("hs"):
            raise InvalidArgumentError(
                f"The symmetric algorithm {algorithm!r} is not allowed for third-party tokens.",
            )


def _scopes(claims: Mapping[str, object]) -> list[str]:
    """Read the granted scopes from the ``scope`` string or the ``scp`` list."""
    scope = claims.get("scope")
    if isinstance(scope, str):
        return scope.split()
    scp = claims.get("scp")
    if isinstance(scp, (list, tuple)):
        return [str(one) for one in cast("Sequence[object]", scp)]
    return []
