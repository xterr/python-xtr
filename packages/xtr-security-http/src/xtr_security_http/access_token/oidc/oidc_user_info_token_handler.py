"""Reading the user a bearer token names off an OIDC server's userinfo endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging_contracts import EXCEPTION_KEY, NullLogger

from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

from .exception.missing_claim_error import MissingClaimError
from .oidc_trait import OidcTrait

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_cache_contracts import CacheInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.user.oidc_user import OidcUser

__all__ = ["OidcUserInfoTokenHandler"]


@final
class OidcUserInfoTokenHandler(OidcTrait):
    """Turns a bearer token into a user badge by asking the OIDC server who it is for.

    The token is not verified here at all: it is presented to the issuer's
    userinfo endpoint as a bearer credential, and the claims the endpoint
    answers with are the user — the one resource-server arrangement where
    the issuer's own answer, over the transport the client carries, is the
    whole of the validation. The endpoint is the client's base URI, or the
    one the issuer's discovery document announces when discovery is enabled
    — see :meth:`enable_discovery`.

    The identifier is read from ``claim`` — ``sub`` by default. The badge's
    loader is wrapped in a
    :class:`~xtr_security_http.authenticator.fallback_user_loader.FallbackUserLoader`,
    the marker that tells the wiring this handler knows how to load its own
    user: the access-token authenticator replaces a marked loader with the
    firewall's user provider when one is configured, so an application that
    keeps its own users decides who the claims describe. Called without a
    provider, the loader builds the
    :class:`~xtr_security_core.user.oidc_user.OidcUser` the claims describe,
    the identifier claim read onto its ``user_identifier``. Every failure
    becomes an :class:`~xtr_security_http.exception.InvalidAccessTokenError`.
    """

    __slots__: tuple[str, ...] = (
        "_claim",
        "_client",
        "_discovery",
        "_logger",
    )

    def __init__(
        self,
        client: HttpClientInterface,
        logger: LoggerInterface | None = None,
        claim: str = "sub",
    ) -> None:
        """Record the client the userinfo endpoint is reached with, and the claim naming the user.

        Args:
            client: The client the userinfo endpoint is reached with; its
                base URI is that endpoint until discovery is enabled, and
                the issuer's own base URI once it is.
            logger: Writes the failures the OIDC server's answers explain,
                when given.
            claim: The claim holding the user identifier.
        """
        self._client = client
        self._logger = logger or NullLogger()
        self._claim = claim
        self._discovery: OidcDiscovery | None = None

    def enable_discovery(self, cache: CacheInterface, cache_key: str) -> None:
        """Read the userinfo endpoint off the issuer's discovery document, cached.

        The document is fetched through the handler's own client, from the
        well-known path relative to its base URI, and kept under
        ``cache_key`` suffixed with ``.document``. No lifetime is set on the
        entry: the cache pool decides how long the document is kept, as it
        did before this delegated to a discovery reader. The endpoint the
        document announces is weighed before anything is cached — the
        discovery reader's ``userinfo_endpoint`` check — so a document that
        sends its clients to plain HTTP is never stored.

        Args:
            cache: The cache the discovery document is kept in.
            cache_key: What the document's cache key starts with, so one
                pool can serve several handlers.
        """
        self._discovery = OidcDiscovery(
            self._client,
            cache,
            cache_ttl=None,
            cache_key=f"{cache_key}.document",
            checked_endpoints=("userinfo_endpoint",),
        )

    def reset(self) -> None:
        """Forget the memoized discovery document, if one was read."""
        if self._discovery is not None:
            self._discovery.reset()

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Ask the userinfo endpoint who ``access_token`` is for, and return the badge naming them.

        Anything the discovery read or the endpoint answers with that cannot
        be turned into a user is an answer the resource server could not
        read, so it turns into the bad credentials the firewall reports as a
        401: an issuer that is unreachable, that refuses the token, or that
        answers something other than the JSON object a userinfo answer is
        says nothing about the token, and never that it is usable.

        Raises:
            InvalidAccessTokenError: When the OIDC server does not vouch for
                the token, or its answer cannot be read.
        """
        endpoint = ""
        discovery = self._discovery
        if discovery is not None:
            try:
                document = await discovery.get_configuration()
                endpoint = self.check_discovered_endpoint(
                    document.get("userinfo_endpoint"),
                    "userinfo_endpoint",
                    None,
                )
            except Exception as error:
                self._log_configuration_failure(error)
                raise InvalidAccessTokenError(
                    f"An error occurred while requesting the OIDC configuration: {error}",
                ) from error
        try:
            claims = await self._claims(access_token, endpoint)
            identifier = self._identifier(claims)
            return UserBadge(
                identifier,
                user_loader=FallbackUserLoader(self._loader(claims, identifier)),
                attributes=dict(claims),
            )
        except Exception as error:
            self._log_server_failure(error)
            raise InvalidAccessTokenError(
                f"An error occurred on the OIDC server: {error}",
            ) from error

    async def _claims(self, access_token: str, endpoint: str) -> dict[str, object]:
        """GET the userinfo endpoint with the token as its bearer credential.

        No redirect is followed: the endpoint was weighed where it was read
        from, and a redirect would change where the token is presented. The
        answer is read as a JSON object — a 4xx or a 5xx raises before its
        payload can be mistaken for one.
        """
        response = await self._client.request(
            "GET",
            endpoint,
            auth_bearer=access_token,
            max_redirects=0,
        )
        async with response:
            return await response.to_array()

    def _identifier(self, claims: Mapping[str, object]) -> str:
        """Read the user identifier off the userinfo answer.

        Raises:
            MissingClaimError: When the claim is missing, or holds nothing a
                badge can name a user by.
        """
        value = claims.get(self._claim)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        raise MissingClaimError(
            f'"{self._claim}" claim not found on OIDC server response.',
        )

    def _loader(self, claims: Mapping[str, object], identifier: str) -> Callable[..., OidcUser]:
        """Return the loader that builds the user the userinfo answer describes.

        The identifier claim is read onto the claims as the user's
        ``user_identifier``, so the user the claims build is named by what
        the issuer said rather than by what the badge was asked to load. The
        badge hands the wrapper whatever it calls a loader with — the
        identifier, the attributes — none of which changes who the claims
        already name.
        """

        def load(*arguments: object) -> OidcUser:
            del arguments
            with_identifier = dict(claims)
            with_identifier["user_identifier"] = identifier
            return self.create_user(with_identifier)

        return load

    def _log_configuration_failure(self, error: Exception) -> None:
        """Write the failure the discovery read explains."""
        self._logger.error(
            "An error occurred while requesting the OIDC configuration.",
            {"error": str(error), EXCEPTION_KEY: error},
        )

    def _log_server_failure(self, error: Exception) -> None:
        """Write the failure the OIDC server's answer explains."""
        self._logger.error(
            "An error occurred on the OIDC server.",
            {"error": str(error), EXCEPTION_KEY: error},
        )
