"""A key set provider that fetches and caches an issuer's JWKS."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast, final
from urllib.parse import SplitResult, urlsplit

import anyio
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.access_token.oidc.exception.oidc_key_set_error import (
    OidcKeySetError,
)
from xtr_security_http.authenticator.oidc.oidc_jwks import OidcKeySetProviderInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx
    from joserfc._keys import KeySetSerialization

__all__ = ["DiscoveryOidcKeySetProvider"]

_DISCOVERY_PATH = "/.well-known/openid-configuration"

#: The port a scheme speaks on when a URL names none, so an explicit ``:443`` on
#: an ``https`` URL compares equal to the same URL without a port.
_DEFAULT_PORTS: dict[str, int] = {"https": 443, "http": 80}


@final
class DiscoveryOidcKeySetProvider(OidcKeySetProviderInterface):
    """Fetches an issuer's JWKS, caches it, and refetches when a key is unknown.

    Given an issuer's ``base_uri`` it reads the OpenID discovery document to
    find the ``jwks_uri``; given a ``jwks_uri`` outright it fetches that. The
    set is cached for ``ttl`` seconds. A ``force_refresh`` fetches again — the
    handler asks for one when a token names a ``kid`` the cached set lacks, a
    rotated key — but no more than once every ``refresh_cooldown`` seconds, so a
    burst of tokens with an unknown ``kid`` triggers a single fetch. A lock
    serialises fetches, so concurrent callers that all find the set stale share
    the one fetch rather than each making their own.

    Every endpoint must be ``https`` unless ``allow_insecure_http`` is set, a
    door left only for a development or test issuer served over plain HTTP.

    A fetch that fails while a set is cached keeps serving that set rather than
    failing the request — but only until ``max_stale`` seconds past the last
    successful fetch, after which a failed refresh drops the stale set and
    fails, so an issuer that has been unreachable for a day no longer validates
    tokens against keys that may since have rotated.
    """

    __slots__ = (
        "_allow_insecure_http",
        "_base_uri",
        "_client",
        "_cooldown",
        "_http_client_factory",
        "_jwks_uri",
        "_key_set",
        "_last_error",
        "_last_fetch",
        "_last_success",
        "_lock",
        "_max_stale",
        "_monotonic",
        "_resolved_jwks_uri",
        "_ttl",
    )

    def __init__(  # noqa: PLR0913 -- a wiring constructor; every knob has a default
        self,
        *,
        base_uri: str | None = None,
        jwks_uri: str | None = None,
        http_client_factory: Callable[[], httpx.AsyncClient],
        ttl: float = 600,
        refresh_cooldown: float = 60,
        max_stale: float = 24 * 60 * 60,
        allow_insecure_http: bool = False,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Record the endpoints, the client factory and the cache timings.

        Raises:
            InvalidArgumentError: When neither or both of ``base_uri`` and
                ``jwks_uri`` are given, or a given endpoint is not ``https`` and
                insecure HTTP is not allowed.
        """
        if (base_uri is None) == (jwks_uri is None):
            raise InvalidArgumentError(
                "A discovery key set provider needs exactly one of base_uri or jwks_uri.",
            )
        self._allow_insecure_http = allow_insecure_http
        if base_uri is not None:
            self._require_secure(base_uri)
        if jwks_uri is not None:
            self._require_secure(jwks_uri)
        self._base_uri = base_uri
        self._jwks_uri = jwks_uri
        self._http_client_factory = http_client_factory
        self._ttl = ttl
        self._cooldown = refresh_cooldown
        self._max_stale = max_stale
        self._monotonic = monotonic
        self._lock = anyio.Lock()
        self._key_set: KeySet | None = None
        self._resolved_jwks_uri: str | None = jwks_uri
        self._last_fetch = 0.0
        self._last_success = 0.0
        self._last_error: str | None = None
        self._client: httpx.AsyncClient | None = None

    @override
    async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
        """Return the cached key set, fetching a fresh one when stale or forced.

        Raises:
            OidcKeySetError: When the key set cannot be fetched, discovered or
                read.
        """
        async with self._lock:
            now = self._monotonic()
            cached = self._fresh_cached(now, force_refresh=force_refresh)
            if cached is not None:
                return cached
            held = self._held_failure(now)
            if held is not None:
                raise held
            return await self._refresh(now, force_refresh=force_refresh)

    async def aclose(self) -> None:
        """Close the HTTP client this provider lazily built, if any.

        The bundle calls this on shutdown; a provider that never fetched built
        no client and this is a no-op.
        """
        client = self._client
        if client is not None:
            self._client = None
            await client.aclose()

    async def _refresh(self, now: float, *, force_refresh: bool) -> KeySet:
        """Fetch a fresh key set, recording the attempt even when it fails.

        The attempt time is recorded whether the fetch succeeds or fails, so the
        cooldown applies to failures too and a burst of forced refreshes during
        an outage makes one fetch, not one per call. When a fetch fails but a set
        was cached before, that cached set keeps being served rather than the
        request failing outright — but only while it is less than ``max_stale``
        seconds past the last successful fetch; once that ceiling is crossed the
        stale set is dropped and the failure raised, so a long outage does not
        pin validation to keys that may have rotated. When none was ever cached,
        the failure is remembered so a burst during a cold-start outage re-raises
        it within the cooldown rather than fetching again — see
        :meth:`_held_failure`.

        Raises:
            OidcKeySetError: When the fetch fails and either no set was ever
                cached or the cached set is past the ``max_stale`` ceiling.
        """
        try:
            key_set = await self._fetch(force_refresh=force_refresh)
        except OidcKeySetError as error:
            self._last_fetch = now
            if self._key_set is not None and now - self._last_success < self._max_stale:
                return self._key_set
            self._key_set = None
            self._last_error = str(error)
            raise
        self._key_set = key_set
        self._last_fetch = now
        self._last_success = now
        self._last_error = None
        return key_set

    def _held_failure(self, now: float) -> OidcKeySetError | None:
        """Return the remembered cold-start failure while its cooldown holds.

        Only a provider that has never cached a set remembers one; within the
        cooldown of that failure its message is re-raised as a fresh error
        without a fetch, so a burst of requests during a cold-start outage costs
        one fetch, not one each, and no single exception instance accumulates a
        chain of contexts.
        """
        if self._key_set is not None or self._last_error is None:
            return None
        if now - self._last_fetch < self._cooldown:
            return OidcKeySetError(self._last_error)
        return None

    def _fresh_cached(self, now: float, *, force_refresh: bool) -> KeySet | None:
        """Return the cached set when it still answers this call, else ``None``."""
        if self._key_set is None:
            return None
        window = self._cooldown if force_refresh else self._ttl
        if now - self._last_fetch < window:
            return self._key_set
        return None

    async def _fetch(self, *, force_refresh: bool) -> KeySet:
        """Discover the ``jwks_uri`` when needed, then fetch and read the set.

        When a ``base_uri`` was configured, a forced refresh re-runs discovery
        too, so a provider follows an issuer that moved its ``jwks_uri`` rather
        than refetching a stale one. A provider given a ``jwks_uri`` outright has
        nothing to discover and refetches that URI.

        Raises:
            OidcKeySetError: When discovery is needed but no base URI was given —
                an impossible state the constructor forbids, guarded explicitly
                in place of a bare assertion.
        """
        jwks_uri = self._resolved_jwks_uri
        if jwks_uri is None or (force_refresh and self._base_uri is not None):
            base_uri = self._base_uri
            if base_uri is None:  # pragma: no cover -- the constructor enforces one of the two
                raise OidcKeySetError("A discovery key set provider has no base URI to discover.")
            jwks_uri = await self._discover(base_uri)
            self._require_secure(jwks_uri)
            self._resolved_jwks_uri = jwks_uri
        document = await self._get_json(jwks_uri)
        try:
            serialization = cast("KeySetSerialization", cast("object", document))
            return KeySet.import_key_set(serialization)
        except (JoseError, ValueError) as error:
            raise OidcKeySetError(
                f"The JWKS document at {jwks_uri} could not be read: {error}",
            ) from error

    async def _discover(self, base_uri: str) -> str:
        """Read the discovery document at ``base_uri`` and return the ``jwks_uri`` it names.

        Raises:
            OidcKeySetError: When the document cannot be read or names no
                usable ``jwks_uri``, or when the ``jwks_uri`` it names is served
                from a different host than the issuer.
        """
        document = await self._get_json(base_uri.rstrip("/") + _DISCOVERY_PATH)
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise OidcKeySetError(
                f"The discovery document at {base_uri} names no jwks_uri.",
            )
        self._require_same_host(base_uri, jwks_uri)
        return jwks_uri

    async def _get_json(self, uri: str) -> dict[str, object]:
        """Fetch ``uri`` and return its JSON body as a mapping.

        Raises:
            OidcKeySetError: When the request fails or the body is not a JSON
                object.
        """
        import httpx  # noqa: PLC0415 -- guarded behind the oidc extra

        client = self._get_client()
        try:
            response = await client.get(uri)
            _ = response.raise_for_status()
            body = cast("object", response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise OidcKeySetError(f"The request to {uri} failed: {error}") from error
        if not isinstance(body, dict):
            raise OidcKeySetError(f"The answer from {uri} is not a JSON object.")
        return cast("dict[str, object]", body)

    def _get_client(self) -> httpx.AsyncClient:
        """Return the provider's one HTTP client, building it on first use."""
        if self._client is None:
            self._client = self._http_client_factory()
        return self._client

    def _require_same_host(self, base_uri: str, jwks_uri: str) -> None:
        """Refuse a discovered ``jwks_uri`` whose origin differs from the issuer's.

        The origin is the scheme, host and effective port — a URL naming no port
        takes its scheme's default (443 for ``https``, 80 for ``http``), so an
        explicit ``:443`` compares equal to none. Comparing the host alone would
        wave through a ``jwks_uri`` on the issuer's host but another port, an
        endpoint the issuer never meant to serve keys from.

        Raises:
            OidcKeySetError: When the ``jwks_uri`` origin differs from the issuer
                origin, a discovery document pointing keys at an attacker's host
                or port.
        """
        base_origin = _origin(urlsplit(base_uri))
        jwks_origin = _origin(urlsplit(jwks_uri))
        if jwks_origin != base_origin:
            raise OidcKeySetError(
                f"The discovery document names a jwks_uri on origin {jwks_origin!r}, "
                f"not the issuer origin {base_origin!r}.",
            )

    def _require_secure(self, uri: str) -> None:
        """Refuse a non-``https`` endpoint unless insecure HTTP is allowed.

        Raises:
            InvalidArgumentError: When ``uri`` is not ``https`` and insecure
                HTTP is not allowed.
        """
        if not self._allow_insecure_http and not uri.lower().startswith("https://"):
            raise InvalidArgumentError(
                f"The endpoint {uri} must be https; set allow_insecure_http for a dev issuer.",
            )


def _origin(split: SplitResult) -> tuple[str, str | None, int | None]:
    """Return the comparable origin of ``split``: scheme, host and effective port."""
    scheme = split.scheme.lower()
    port = split.port if split.port is not None else _DEFAULT_PORTS.get(scheme)
    return (scheme, split.hostname, port)
