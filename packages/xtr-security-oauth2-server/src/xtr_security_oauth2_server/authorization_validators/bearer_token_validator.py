"""Reading the bearer token a request presents, and judging it claim by claim."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_security_core.exception.invalid_argument_error import (
    InvalidArgumentError as UnreadableTokenError,
)

from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError

from .authorization_validator_interface import AuthorizationValidatorInterface
from .bearer_token_validator_interface import BearerTokenValidatorInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_jwt.services.jws_provider import JwsProviderInterface
    from xtr_security_jwt.signature.loaded_jws import LoadedJws

    from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )

__all__ = ["BearerTokenValidator"]

#: The scheme and the space after it, however the client cased the name.
_BEARER: Final[re.Pattern[str]] = re.compile(r"^\s*Bearer\s", re.IGNORECASE)

#: What the header of an access token says it is, so an identity token
#: presented as one is refused before its claims are read (RFC 9068, §2.1).
_TYPE_HEADER: Final[str] = "at+jwt"

#: What separates the scopes a token carries, in the one ``scope`` claim.
_SCOPE_DELIMITER: Final[str] = " "


@final
class BearerTokenValidator(AuthorizationValidatorInterface, BearerTokenValidatorInterface):
    """Accepts the signed access tokens this deployment issued, and nothing else.

    A token arrives in the ``Authorization`` header under RFC 6750's ``Bearer``
    scheme and is judged against RFC 9068's access-token profile, in the order
    a reader can stop at the first failure: the signature, because nothing a
    token says means anything until it is known to be ours; the ``typ`` header,
    so an identity token cannot be spent as an access token; the window it is
    good for; the issuer and the audience it names; and last, because it is the
    only question storage has to be asked, whether it was revoked.

    Two of those are the deployment's to decide. The leeway widens the expiry
    and not-before windows for clocks that disagree, and the audience is only
    judged when one is configured — with none, a token keeps the client it was
    issued to as its audience, as the flows stamp it, and saying that any
    audience will do is the honest reading of a deployment that named none.

    What it works out is written onto the request rather than returned beside
    it, so whatever handles the request next — a firewall, a route — reads one
    object that already knows the token's identifier, the client, the resource
    owner and the scopes.

    The judging itself is a second method, so whoever already has the token —
    a revocation or introspection handler, which reads it out of the request
    body — asks the same question without an ``Authorization`` header to take
    it out of.
    """

    __slots__ = (
        "_access_token_repository",
        "_audience",
        "_clock",
        "_issuer",
        "_jws_provider",
        "_leeway",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- these six together are one reading of one token
        self,
        access_token_repository: AccessTokenRepositoryInterface,
        jws_provider: JwsProviderInterface,
        issuer: str,
        clock: ClockInterface,
        audience: str | None = None,
        leeway: timedelta | None = None,
    ) -> None:
        """Accept tokens ``jws_provider`` verifies and ``issuer`` issued.

        Args:
            access_token_repository: Asked whether a token was revoked.
            jws_provider: Holds the keys a token's signature is checked against.
            issuer: The origin a token must claim to come from.
            clock: Where the instant a token is judged against is read from.
            audience: Who a token must be addressed to, or ``None`` to accept
                whatever audience it names.
            leeway: How far the expiry and not-before windows are widened for
                clocks that disagree, or ``None`` for not at all.
        """
        self._access_token_repository: AccessTokenRepositoryInterface = access_token_repository
        self._jws_provider: JwsProviderInterface = jws_provider
        self._issuer: str = issuer
        self._clock: ClockInterface = clock
        self._audience: str | None = audience
        self._leeway: timedelta | None = leeway

    @override
    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        """Return ``request`` annotated with what the token it carries says.

        Raises:
            OAuthServerError: ``access_denied`` when the request carries no
                bearer token, or one that is unreadable, unsigned by a key this
                deployment trusts, not an access token, outside its window,
                issued elsewhere, addressed elsewhere, or revoked.
        """
        claims = await self.validate_bearer_token(request, _bearer_token(request))

        return (
            request.with_attribute("oauth_access_token_id", _text(claims, "jti"))
            .with_attribute("oauth_client_id", _text(claims, "client_id"))
            .with_attribute("oauth_user_id", _text(claims, "sub"))
            .with_attribute("oauth_scopes", list(_scopes(claims)))
        )

    @override
    async def validate_bearer_token(
        self,
        request: ServerRequestInterface,
        token: str,
    ) -> Mapping[str, object]:
        """Return what ``token`` claims, having refused every reason not to.

        Raises:
            OAuthServerError: ``access_denied`` when the token is unreadable,
                unsigned by a key this deployment trusts, not an access token,
                outside its window, issued elsewhere, addressed elsewhere,
                nameless, or revoked.
        """
        del request

        loaded = self._load(token)
        self._refuse_unless_an_access_token(loaded.get_header())
        claims = loaded.get_payload()
        self._refuse_outside_its_window(claims)
        self._refuse_unless_addressed_to_us(claims)
        identifier = _text(claims, "jti")
        if identifier is None:
            raise OAuthServerError.access_denied("Access token carries no identifier")
        if await self._access_token_repository.is_access_token_revoked(identifier):
            raise OAuthServerError.access_denied("Access token has been revoked")

        return claims

    def _load(self, token: str) -> LoadedJws:
        """Read ``token`` back and refuse it unless a trusted key signed it.

        Raises:
            OAuthServerError: ``access_denied`` when the token is not a
                readable signed token, or its signature does not verify.
        """
        try:
            loaded = self._jws_provider.load(token)
        except UnreadableTokenError as error:
            raise OAuthServerError.access_denied("Access token could not be parsed") from error
        if not loaded.is_verified():
            raise OAuthServerError.access_denied("Access token could not be verified")

        return loaded

    def _refuse_unless_an_access_token(self, header: Mapping[str, object]) -> None:
        """Refuse unless the header says the token is an access token.

        Raises:
            OAuthServerError: ``access_denied`` when it says anything else, or
                nothing at all.
        """
        if header.get("typ") != _TYPE_HEADER:
            raise OAuthServerError.access_denied(
                f'Access token does not declare the type "{_TYPE_HEADER}"',
            )

    def _refuse_outside_its_window(self, claims: Mapping[str, object]) -> None:
        """Refuse unless the instant this is judged at falls inside the token's window.

        A token carrying no expiry is refused rather than accepted for ever: a
        bearer token nobody can wait out is a credential, and this profile
        mints none.

        Raises:
            OAuthServerError: ``access_denied`` when the token has expired or
                is not usable yet.
        """
        now = self._clock.now().timestamp()
        leeway = 0.0 if self._leeway is None else self._leeway.total_seconds()
        expires_at = _number(claims, "exp")
        if expires_at is None or now - leeway >= expires_at:
            raise OAuthServerError.access_denied("Access token has expired")
        not_before = _number(claims, "nbf")
        if not_before is not None and not_before - leeway > now:
            raise OAuthServerError.access_denied("Access token is not usable yet")

    def _refuse_unless_addressed_to_us(self, claims: Mapping[str, object]) -> None:
        """Refuse unless the token was issued here and addressed where it is read.

        Raises:
            OAuthServerError: ``access_denied`` when the token names another
                issuer, or another audience than the configured one.
        """
        if claims.get("iss") != self._issuer:
            raise OAuthServerError.access_denied("Access token names another issuer")
        if self._audience is not None and self._audience not in _audiences(claims):
            raise OAuthServerError.access_denied("Access token names another audience")

    @override
    def __repr__(self) -> str:
        """Name what it accepts, and nothing a request carried.

        The issuer and the audience are configuration a deployment publishes
        anyway; the keys and the tokens are not, so neither is named.
        """
        return f"{type(self).__name__}(issuer={self._issuer!r}, audience={self._audience!r})"


def _bearer_token(request: ServerRequestInterface) -> str:
    """Return the token ``request`` presents under the bearer scheme.

    Raises:
        OAuthServerError: ``access_denied`` when there is no ``Authorization``
            header, or it carries no bearer token — another scheme, or the
            scheme's name and nothing after it.
    """
    if not request.has_header("Authorization"):
        raise OAuthServerError.access_denied('Missing "Authorization" header')
    header = request.get_header_line("Authorization")
    token = _BEARER.sub("", header, count=1).strip()
    if token == "" or token == header.strip():
        raise OAuthServerError.access_denied('Missing "Bearer" token')

    return token


def _text(claims: Mapping[str, object], name: str) -> str | None:
    """Read ``name`` out of the claims as text, or ``None``."""
    value = claims.get(name)

    return value if isinstance(value, str) else None


def _number(claims: Mapping[str, object], name: str) -> float | None:
    """Read ``name`` out of the claims as an instant, or ``None``.

    A boolean is refused although it is a number in Python: an expiry of
    ``True`` is a token saying something other than an instant.
    """
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value)


def _audiences(claims: Mapping[str, object]) -> Sequence[str]:
    """Read who the token is addressed to, one name or several."""
    value = claims.get("aud")
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        # The cast says what narrowing cannot: a list of anything is a list of
        # objects, and every item is then asked what it is.
        return tuple(item for item in cast("list[object]", value) if isinstance(item, str))

    return ()


def _scopes(claims: Mapping[str, object]) -> Sequence[str]:
    """Read what the token may do, as the names it carries."""
    scope = _text(claims, "scope")
    if scope is None:
        return ()

    return tuple(name for name in scope.strip().split(_SCOPE_DELIMITER) if name != "")
