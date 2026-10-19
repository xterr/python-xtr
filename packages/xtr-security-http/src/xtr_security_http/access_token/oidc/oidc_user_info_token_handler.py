"""Reading the user a bearer token names off an OIDC server's userinfo endpoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, cast, final

from xtr_logging_contracts import EXCEPTION_KEY, NullLogger

from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

from .exception.missing_claim_error import MissingClaimError
from .oidc_trait import OidcTrait

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_cache_contracts import CacheInterface, ItemInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.user.oidc_user import OidcUser

__all__ = ["OidcUserInfoTokenHandler"]

_CONFIGURATION_PATH: Final = ".well-known/openid-configuration"
"""Where an issuer's OpenID discovery document is read from, relative to the client's base URI."""

_MAX_DOCUMENT_SIZE: Final = 1024 * 1024
"""The most discovery-document bytes an answer may hold before it is refused.

Discovery documents are small; the bound keeps an issuer from parking bulk
in a cache entry every request reads."""

_DOCUMENT_SUFFIX: Final = ".document"
"""What the discovery-document cache key ends with.

It keeps the document clear of the entries other OIDC pieces write under the
bare key, in formats of their own: they expire with the pool, unread."""


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
        "_cache_key",
        "_claim",
        "_client",
        "_discovery_cache",
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
        self._discovery_cache = None
        self._cache_key = ""

    def enable_discovery(self, cache: CacheInterface, cache_key: str) -> None:
        """Read the userinfo endpoint off the issuer's discovery document, cached.

        The document is fetched through the handler's own client, from the
        well-known path relative to its base URI, and kept under
        ``cache_key`` suffixed with ``.document``. No lifetime is set on the
        entry: the cache pool decides how long the document is kept, as it
        did before this delegated to a discovery reader. The endpoint the
        document announces is weighed before anything is cached — see
        :meth:`OidcTrait.check_discovered_endpoint
        <xtr_security_http.access_token.oidc.oidc_trait.OidcTrait.check_discovered_endpoint>`
        — so a document that sends its clients to plain HTTP is never stored.

        Args:
            cache: The cache the discovery document is kept in.
            cache_key: What the document's cache key starts with, so one
                pool can serve several handlers.
        """
        self._discovery_cache = cache
        self._cache_key = cache_key

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
        cache = self._discovery_cache
        if cache is not None:
            try:
                document = await cache.get(
                    f"{self._cache_key}{_DOCUMENT_SUFFIX}",
                    self._fetch_document,
                )
                endpoint = self.check_discovered_endpoint(
                    document.get("userinfo_endpoint"),
                    "userinfo_endpoint",
                    None,
                )
            except InvalidAccessTokenError as error:
                self._log_configuration_failure(error)
                raise
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

    async def _fetch_document(self, item: ItemInterface) -> dict[str, object]:
        """Fetch the discovery document and weigh the endpoint it announces.

        The endpoint's scheme is weighed against the URL that served the
        document — read off the response, since no redirect was followed —
        before anything is cached, so a document that sends its clients to
        plain HTTP is never stored, and a cached document needs no URL of
        its own to be trusted. The document is decoded here rather than on
        read, so a malformed one is refused once instead of failing every
        request until its entry expires.

        Raises:
            InvalidAccessTokenError: When the document cannot be read, is
            not a JSON object, is too large to keep, or announces an
            endpoint that must not be used.
        """
        del item  # no lifetime is set: the cache pool decides how long the document is kept
        response = await self._client.request("GET", _CONFIGURATION_PATH, max_redirects=0)
        async with response:
            served_by = response.get_info("url")
            content = await response.get_content()
        if len(content) > _MAX_DOCUMENT_SIZE:
            raise InvalidAccessTokenError(
                "The OIDC discovery document exceeds the maximum size of 1 MiB.",
            )
        try:
            document = cast("object", json.loads(content))
        except ValueError as error:
            raise InvalidAccessTokenError(
                f"The OIDC discovery document could not be decoded: {error}",
            ) from error
        if not isinstance(document, dict):
            raise InvalidAccessTokenError("The OIDC discovery document is not a JSON object.")
        members = cast("dict[str, object]", document)
        _ = self.check_discovered_endpoint(
            members.get("userinfo_endpoint"),
            "userinfo_endpoint",
            served_by if isinstance(served_by, str) else None,
        )
        return members

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
