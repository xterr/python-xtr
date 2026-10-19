"""Fetching and caching an OpenID Connect provider's discovery document."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urlsplit

from xtr_security_core.exception import AuthenticationError, BadMethodCallError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_cache_contracts import CacheInterface, ItemInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface

__all__ = ["OidcDiscovery"]

_LOOPBACK_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1"})
"""The hosts the authorization code and the tokens it is exchanged for stay
confidential on, plain HTTP included, for local development."""


@final
class OidcDiscovery:
    """Fetches and caches the OpenID Connect discovery configuration.

    It lives outside the authenticator namespace on purpose: resolving the
    endpoints of a provider is a protocol concern shared by every OIDC
    authentication mechanism, not something specific to the Authorization
    Code Flow.

    The decoded document is memoized for the lifetime of the instance, so
    repeated endpoint reads within one authentication neither re-read the
    cache nor re-decode, and a zero cache TTL costs a single HTTP request per
    authentication instead of one per read.
    """

    __slots__ = (
        "_cache",
        "_cache_key",
        "_cache_ttl",
        "_checked_endpoints",
        "_checked_mtls_aliases",
        "_configuration",
        "_http_client",
        "_issuer",
        "_open_id_configuration_url",
        "_response",
    )

    MAX_CONFIGURATION_SIZE: Final = 1024 * 1024
    """The most discovery-document bytes an answer may hold before it is
    refused. Discovery documents are small; the bound keeps a provider from
    parking bulk in a cache entry every authentication reads."""

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the client, the cache and the five knobs it takes
        self,
        http_client: HttpClientInterface,
        cache: CacheInterface,
        open_id_configuration_url: str = ".well-known/openid-configuration",
        issuer: str | None = None,
        cache_ttl: int | None = 3600,
        cache_key: str | None = None,
        checked_endpoints: Sequence[str] = (),
        checked_mtls_aliases: Sequence[str] = (),
    ) -> None:
        """Record where the document is read from, where it is kept, and what it must announce.

        Args:
            http_client: The client the discovery document is fetched with.
            cache: Where the raw document is kept between reads.
            open_id_configuration_url: Absolute, or relative to ``issuer``
                when one is given, or to the HTTP client's ``base_uri``.
            issuer: The expected issuer, or ``None`` to skip the check of
                OIDC Discovery 1.0, Section 4.3.
            cache_ttl: The cache entry's lifetime, or ``None`` to leave it to
                the cache pool.
            cache_key: The cache key, or ``None`` to derive it from the
                configuration URL.
            checked_endpoints: Endpoints that must be announced, and must not
                downgrade to plain HTTP the transport that carried the
                discovery document — checked before the document is cached.
            checked_mtls_aliases: Endpoints whose ``mtls_endpoint_aliases``
                entry is checked the same way, when the provider announces
                one.
        """
        # The trailing slash is trimmed here, and the configuration URL built
        # from the issuer, because an issuer coming from an environment
        # variable is an unresolved placeholder while the container compiles:
        # trimming it there leaves the resolved value untouched, and the
        # discovery URL ends up carrying a double slash.
        self._issuer = issuer.rstrip("/") if issuer is not None else None
        # OIDC Discovery 1.0, Section 4.1: the well-known path is appended to
        # the issuer.
        self._open_id_configuration_url = (
            f"{self._issuer}/{open_id_configuration_url.lstrip('/')}"
            if self._issuer is not None and not _is_absolute(open_id_configuration_url)
            else open_id_configuration_url
        )
        self._http_client = http_client
        self._cache = cache
        self._cache_ttl = cache_ttl
        self._cache_key = cache_key
        self._checked_endpoints = tuple(checked_endpoints)
        self._checked_mtls_aliases = tuple(checked_mtls_aliases)
        self._response: HttpResponseInterface | None = None
        self._configuration: dict[str, object] | None = None

    async def get_configuration(self) -> dict[str, object]:
        """Return the raw discovery document, fetched and cached on first read.

        The issuer's scheme is checked outside the cache callback so it also
        applies to warm entries, and here rather than only in the wiring,
        because an issuer coming from an environment variable is unknown until
        runtime.

        Raises:
            AuthenticationError: When the document cannot be fetched, is not
                a JSON object, announces another issuer, or names an endpoint
                it must not.
        """
        if self._issuer is not None and not self.is_secure_url(self._issuer):
            raise AuthenticationError(
                f'The OIDC issuer "{self._issuer}" must use HTTPS: the authorization '
                "code, the PKCE verifier and the tokens it is exchanged for are only "
                "confidential over TLS.",
            )
        if self._configuration is not None:
            return self._configuration
        value = await self._cache.get(self._cache_key_value(), self._compute)
        # A request sent by prefetch() is dropped when another process warmed
        # the entry in between, instead of being consumed the next time the
        # document is read.
        if self._response is not None:
            await self._response.cancel()
        self._response = None
        payload = value["payload"]
        self._configuration = _decode(payload if isinstance(payload, str) else "")
        return self._configuration

    async def prefetch(self) -> None:
        """Send the discovery request without waiting for its response.

        Nothing is sent when a request was already sent, or the document is
        memoized. Calling it on several instances before reading any of them
        lets their requests travel concurrently, since the response is only
        consumed by :meth:`get_configuration`.
        """
        if self._response is not None or self._configuration is not None:
            return
        self._response = await self._request()

    def reset(self) -> None:
        """Forget the memoized document and any prefetched response."""
        self._configuration = None
        self._response = None

    async def get_secure_endpoint(self, endpoint: str) -> str:
        """Return an endpoint the discovery document announces, checked for transport security.

        The document is fetched from the provider, so a tampered or
        misconfigured one must not be able to downgrade a request to plain
        HTTP: enforcing HTTPS on the configured issuer would be pointless if
        the endpoints it announces were used as they are.

        Args:
            endpoint: The document member naming the endpoint.

        Returns:
            The announced endpoint.

        Raises:
            AuthenticationError: When the endpoint is not announced, or does
                not use HTTPS.
        """
        configuration = await self.get_configuration()
        url = configuration.get(endpoint)
        if not isinstance(url, str) or not url:
            raise AuthenticationError(
                f'The OIDC provider does not announce any "{endpoint}".',
            )
        if not self.is_secure_url(url):
            raise AuthenticationError(
                f'The "{endpoint}" announced by the OIDC provider must use HTTPS '
                f'(got "{url}"): the authorization code, the PKCE verifier and the '
                "tokens it is exchanged for are only confidential over TLS.",
            )
        return url

    async def get_issuer(self) -> str:
        """Return the issuer identifier the provider announces.

        It is the value the document itself carries, rather than the
        configured one, because the two are compared ignoring a trailing
        slash: what a provider verifies an audience against is what it
        announces, down to that slash. An expected issuer is required, as RFC
        8414, Section 3.3 has the client validate the announced one —
        otherwise a document could name another provider as the audience of
        an assertion sent to a token endpoint the document controls.

        Returns:
            The announced issuer.

        Raises:
            BadMethodCallError: When no expected issuer was given to the
                constructor.
            AuthenticationError: When the document cannot be fetched, or
                announces no issuer.
        """
        if self._issuer is None:
            raise BadMethodCallError(
                f'The issuer announced at "{self._open_id_configuration_url}" cannot be '
                "trusted since no expected issuer was given to check it against: pass "
                'one to the constructor of "OidcDiscovery".',
            )
        issuer = (await self.get_configuration()).get("issuer")
        if not isinstance(issuer, str) or not issuer:
            raise AuthenticationError('The OIDC provider does not announce any "issuer".')
        return issuer

    @staticmethod
    def is_secure_url(url: str) -> bool:
        """Tell whether a URL provides the transport security the OIDC flow relies on.

        The authorization code, the PKCE verifier and the tokens they are
        exchanged for are only confidential over TLS, so HTTPS is mandatory —
        loopback hosts excepted, for local development, including the
        ``*.localhost`` names RFC 6761, Section 6.3 resolves to the loopback
        address.
        """
        if urlsplit(url).scheme.lower() == "https":
            return True
        host = urlsplit(url).hostname or ""
        host = host.lower().strip("[]")
        return host in _LOOPBACK_HOSTS or host.endswith(".localhost")

    async def _compute(self, item: ItemInterface) -> dict[str, object]:
        """Fetch, decode and weigh the document, returning it for the cache.

        The document is decoded here so a malformed one is refused once,
        before it reaches the cache where it would otherwise fail on every
        read until its entry expires. The issuer match and the endpoint
        schemes are checked before anything is stored, so a document sending
        its clients to plain HTTP is never cached.
        """
        if self._cache_ttl is not None:
            _ = item.expires_after(self._cache_ttl)
        # The request may have been sent by prefetch() already, and is
        # consumed once.
        response = self._response if self._response is not None else await self._request()
        self._response = None
        payload = await self._payload(response)
        configuration = _decode(payload.decode("utf-8", errors="replace"))
        # OIDC Discovery 1.0, Section 4.3: the "issuer" returned MUST be
        # identical to the issuer used to build the discovery URL, which
        # validates it and prevents a tampered document from redefining the
        # expected issuer. A trailing slash is ignored on both sides:
        # providers do announce issuers ending with one, and it carries no
        # security meaning since the origin and the path are otherwise
        # identical.
        if self._issuer is not None:
            announced = configuration.get("issuer")
            announced = announced.rstrip("/") if isinstance(announced, str) else ""
            if announced != self._issuer:
                raise AuthenticationError(
                    f'The OIDC provider announced the issuer "{announced}", which does '
                    f'not match the configured issuer "{self._issuer}".',
                )
        served_by = response.get_info("url")
        served_by = served_by if isinstance(served_by, str) else ""
        for endpoint in self._checked_endpoints:
            _check_endpoint_scheme(configuration.get(endpoint), endpoint, served_by)
        aliases = configuration.get("mtls_endpoint_aliases")
        aliases = cast("dict[str, object]", aliases) if isinstance(aliases, dict) else {}
        for endpoint in self._checked_mtls_aliases:
            if endpoint in aliases:
                _check_endpoint_scheme(
                    aliases[endpoint],
                    f"mtls_endpoint_aliases.{endpoint}",
                    served_by,
                )
        # The raw payload is cached next to the URL that served it, rather
        # than the decoded document, so the whole document survives the round
        # trip unchanged.
        return {"url": served_by, "payload": payload.decode("utf-8", errors="replace")}

    async def _request(self) -> HttpResponseInterface:
        """Send the discovery request, following no redirect.

        The endpoints the document announces are weighed against the URL it
        was requested from, which a redirect would change.
        """
        try:
            return await self._http_client.request(
                "GET",
                self._open_id_configuration_url,
                max_redirects=0,
            )
        except Exception as error:
            raise self._cannot_fetch(error) from error

    async def _payload(self, response: HttpResponseInterface) -> bytes:
        """Read the document's body, refusing one too large to keep."""
        try:
            async with response:
                content = await response.get_content()
        except Exception as error:
            raise self._cannot_fetch(error) from error
        if len(content) > self.MAX_CONFIGURATION_SIZE:
            raise AuthenticationError(
                "The OIDC discovery document exceeds the maximum size of 1 MiB.",
            )
        return content

    def _cannot_fetch(self, error: Exception) -> AuthenticationError:
        """Wrap a fetch failure into the refusal every reader reports."""
        return AuthenticationError(
            "The OIDC discovery document could not be fetched from "
            f'"{self._open_id_configuration_url}": {error}',
        )

    def _cache_key_value(self) -> str:
        """Return the key the document is cached under."""
        return (
            self._cache_key
            if self._cache_key is not None
            else (f"oidc_discovery.{sha256(self._open_id_configuration_url.encode()).hexdigest()}")
        )


def _is_absolute(url: str) -> bool:
    """Tell whether a configuration URL names its own scheme."""
    return urlsplit(url).scheme != ""


def _decode(payload: str) -> dict[str, object]:
    """Decode a JSON payload, refusing anything but a JSON object.

    Raises:
        AuthenticationError: When the payload is not a JSON object.
    """
    try:
        document = cast("object", json.loads(payload))
    except ValueError as error:
        raise AuthenticationError(
            f"The OIDC discovery document could not be decoded: {error}",
        ) from error
    if not isinstance(document, dict):
        raise AuthenticationError("The OIDC discovery document is not a JSON object.")
    return cast("dict[str, object]", document)


def _check_endpoint_scheme(endpoint: object, key: str, discovery_url: str) -> None:
    """Refuse an endpoint that downgrades the transport that carried the document.

    The discovery specification requires the endpoints it advertises to use
    ``https``; an endpoint naming no scheme is taken as it stands, the way a
    relative announcement would be.

    Raises:
        AuthenticationError: When the endpoint is missing, or names a scheme
            other than ``https`` while the document itself was served over
            ``https``.
    """
    if not isinstance(endpoint, str) or not endpoint:
        raise AuthenticationError(
            f'The "{key}" is missing from the OIDC discovery document.',
        )
    scheme = urlsplit(endpoint).scheme
    if scheme and scheme.lower() != "https" and discovery_url.startswith("https://"):
        raise AuthenticationError(
            f'The "{key}" found in the OIDC discovery document must use the '
            f'"https" scheme, "{scheme}" given.',
        )
