"""A key set provider that discovers, fetches and caches an issuer's JWKS."""

from __future__ import annotations

import math
from hashlib import sha256
from typing import TYPE_CHECKING, cast, final

from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from typing_extensions import override
from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError, InvalidArgumentError

from xtr_security_http.authenticator.oidc.oidc_jwks import OidcKeySetProviderInterface

from .oidc_discovery import OidcDiscovery
from .oidc_jwks import OidcJwks

if TYPE_CHECKING:
    from joserfc._keys import KeySetSerialization
    from xtr_cache_contracts import CacheInterface, Callback, ItemInterface
    from xtr_clock import ClockInterface
    from xtr_http_client_contracts import HttpClientInterface

    from xtr_security_http.access_token.oidc.exception.oidc_key_set_error import (
        OidcKeySetError,
    )

__all__ = ["DiscoveryOidcKeySetProvider"]


def _key_set_error(message: str) -> OidcKeySetError:
    """Build the error every key-set failure becomes, imported where it is raised.

    The error lives with the access-token handlers that catch it, and their
    package imports this one; importing it at the top of this module would
    make the two packages import each other.
    """
    from xtr_security_http.access_token.oidc.exception.oidc_key_set_error import (  # noqa: PLC0415 -- imported here to keep the two OIDC packages from importing each other
        OidcKeySetError,
    )

    return OidcKeySetError(message)


@final
class DiscoveryOidcKeySetProvider(OidcKeySetProviderInterface):
    """Fetches an issuer's JWKS through the aligned discovery, and caches it.

    Given an issuer's ``base_uri`` it reads the OpenID discovery document —
    through :class:`~xtr_security_http.oidc.oidc_discovery.OidcDiscovery`, so
    the issuer is checked for ``https`` and for the issuer the document
    itself announces, and the ``jwks_uri`` is weighed before anything is
    cached — to find the ``jwks_uri``; given a ``jwks_uri`` outright it
    fetches that. The keys are kept in the injected cache for what the
    provider's HTTP headers leave (RFC 9111 arithmetic through
    :class:`~xtr_security_http.oidc.oidc_jwks.OidcJwks`), or ``jwks_cache_ttl``
    seconds when the headers name nothing.

    A ``force_refresh`` fetches again — the handler asks for one when a token
    names a ``kid`` the cached set lacks, a rotated key — but no more than
    once every ``ROTATION_COOLDOWN`` seconds, so a burst of tokens with an
    unknown ``kid`` triggers a single fetch.

    Every endpoint must be ``https`` — the loopback hosts local development
    serves on excepted — unless ``allow_insecure_http`` is set, a door left
    only for a development or test issuer served over plain HTTP.
    """

    __slots__ = (
        "_allow_insecure_http",
        "_base_uri",
        "_cache",
        "_clock",
        "_discovery",
        "_enforce_key_usage_verification",
        "_http_client",
        "_jwks_cache_ttl",
        "_jwks_uri",
    )

    ROTATION_COOLDOWN: int = 60
    """How long a fetched JWKS is kept before a forced refresh may refetch."""

    def __init__(  # noqa: PLR0913 -- the endpoints, the client and the cache, each with its own knob
        self,
        http_client: HttpClientInterface,
        cache: CacheInterface,
        *,
        base_uri: str | None = None,
        jwks_uri: str | None = None,
        allow_insecure_http: bool = False,
        jwks_cache_ttl: int = 3600,
        enforce_key_usage_verification: bool = True,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the endpoints, the client, the cache and the cache timings.

        Args:
            http_client: The client the discovery document and the JWKS are
                fetched with.
            cache: Where the discovery document and the keys are kept.
            base_uri: The issuer whose discovery document names the
                ``jwks_uri``; exactly one of this and ``jwks_uri``.
            jwks_uri: The JWKS endpoint outright, with no discovery read.
            allow_insecure_http: The development door: plain-HTTP endpoints
                are weighed against the loopback rule instead of refused.
            jwks_cache_ttl: How long the keys are kept when the provider's
                headers name no lifetime.
            enforce_key_usage_verification: Whether only keys explicitly
                designated for signatures are kept — see
                :meth:`OidcJwks.from_response
                <xtr_security_http.oidc.oidc_jwks.OidcJwks.from_response>`.
            clock: What the rotation cooldown is counted on.

        Raises:
            InvalidArgumentError: When neither or both of ``base_uri`` and
                ``jwks_uri`` are given.
        """
        if (base_uri is None) == (jwks_uri is None):
            raise InvalidArgumentError(
                "A discovery key set provider needs exactly one of base_uri or jwks_uri.",
            )
        self._allow_insecure_http = allow_insecure_http
        self._base_uri = base_uri
        self._jwks_uri = jwks_uri
        self._http_client = http_client
        self._cache = cache
        self._jwks_cache_ttl = jwks_cache_ttl
        self._enforce_key_usage_verification = enforce_key_usage_verification
        self._clock = clock if clock is not None else SystemClock()
        self._discovery = (
            None
            if base_uri is None
            else OidcDiscovery(
                http_client,
                cache,
                issuer=None if allow_insecure_http else base_uri,
                checked_endpoints=("jwks_uri",),
            )
        )

    @override
    async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
        """Return the cached key set, fetching a fresh one when forced past the cooldown.

        Raises:
            OidcKeySetError: When the key set cannot be fetched, discovered or
                read.
        """
        try:
            jwks_uri = await self._resolve_jwks_uri()
            entry: dict[str, object] = await self._cache.get(
                self._cache_key(jwks_uri),
                self._compute(jwks_uri),
            )
            if force_refresh and self._past_cooldown(entry):
                entry = await self._cache.get(
                    self._cache_key(jwks_uri),
                    self._compute(jwks_uri),
                    beta=math.inf,
                )
        except AuthenticationError as error:
            raise _key_set_error(str(error)) from error
        try:
            serialization = cast("KeySetSerialization", cast("object", {"keys": entry["keys"]}))
            return KeySet.import_key_set(serialization)
        except (JoseError, ValueError) as error:
            raise _key_set_error(
                f"The JWKS document at {jwks_uri} could not be read: {error}",
            ) from error

    async def aclose(self) -> None:
        """Close nothing: the HTTP client is the application's, not this provider's.

        The wiring collects providers as closeable so a shutdown releases
        whatever one holds; this one holds nothing since the client and the
        cache were injected, and the method stays so the collection needs no
        special case.
        """

    async def _resolve_jwks_uri(self) -> str:
        """Return the JWKS endpoint, discovered when no outright one was given.

        With the insecure-HTTP door open the discovery document is read with
        no expected issuer, so nothing about it is enforced but the
        announcement of the endpoint; with the door closed the endpoint comes
        from :meth:`OidcDiscovery.get_secure_endpoint
        <xtr_security_http.oidc.oidc_discovery.OidcDiscovery.get_secure_endpoint>`,
        which weighs its scheme.
        """
        if self._jwks_uri is not None:
            self._require_secure(self._jwks_uri)
            return self._jwks_uri
        discovery = self._discovery
        # The constructor enforces one of the two.
        if discovery is None:  # pragma: no cover
            raise _key_set_error(
                "A discovery key set provider has no base URI to discover.",
            )
        if self._allow_insecure_http:
            jwks_uri = (await discovery.get_configuration()).get("jwks_uri")
            if not isinstance(jwks_uri, str) or not jwks_uri:
                raise AuthenticationError(
                    "The discovery document names no jwks_uri.",
                )
            return jwks_uri
        return await discovery.get_secure_endpoint("jwks_uri")

    def _compute(self, jwks_uri: str) -> Callback[dict[str, object]]:
        """Return the callback that fetches the keys and stamps the fetch.

        The JWKS is stored with the time it was fetched, so the rotation
        cooldown below can be throttled without a second cache entry.
        """

        async def compute(item: ItemInterface) -> dict[str, object]:
            keys = await OidcJwks.fetch_keys(
                self._http_client,
                jwks_uri,
                item,
                default_ttl=self._jwks_cache_ttl,
                enforce_key_usage_verification=self._enforce_key_usage_verification,
                clock=self._clock,
            )
            return {"keys": keys, "fetched_at": int(self._clock.now().timestamp())}

        return compute

    def _past_cooldown(self, entry: dict[str, object]) -> bool:
        """Tell whether the entry was fetched before the rotation cooldown began."""
        fetched_at = entry.get("fetched_at")
        if not isinstance(fetched_at, int):
            return True
        return fetched_at <= int(self._clock.now().timestamp()) - self.ROTATION_COOLDOWN

    def _cache_key(self, jwks_uri: str) -> str:
        """Return the key the keys are cached under.

        The strictness is kept out of the hash, where a ``jwks_uri`` ending
        with the marker would collide with the other strictness of the same
        endpoint.
        """
        marker = "" if self._enforce_key_usage_verification else "lax."
        return f"oidc_jwks.{marker}{sha256(jwks_uri.encode()).hexdigest()}"

    def _require_secure(self, uri: str) -> None:
        """Refuse a non-``https`` endpoint unless the development door is open.

        The loopback rule of :meth:`OidcDiscovery.is_secure_url
        <xtr_security_http.oidc.oidc_discovery.OidcDiscovery.is_secure_url>`
        applies, so a local issuer is served over plain HTTP without the door.
        """
        if not self._allow_insecure_http and not OidcDiscovery.is_secure_url(uri):
            raise _key_set_error(
                f"The endpoint {uri} must be https; set allow_insecure_http for a dev issuer.",
            )
