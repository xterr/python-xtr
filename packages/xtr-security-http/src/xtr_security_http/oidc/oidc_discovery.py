"""A key set provider that fetches and caches an issuer's JWKS."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast, final

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
    """

    __slots__ = (
        "_allow_insecure_http",
        "_base_uri",
        "_cooldown",
        "_http_client_factory",
        "_jwks_uri",
        "_key_set",
        "_last_error",
        "_last_fetch",
        "_lock",
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
        self._monotonic = monotonic
        self._lock = anyio.Lock()
        self._key_set: KeySet | None = None
        self._resolved_jwks_uri: str | None = jwks_uri
        self._last_fetch = 0.0
        self._last_error: OidcKeySetError | None = None

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
            return await self._refresh(now)

    async def _refresh(self, now: float) -> KeySet:
        """Fetch a fresh key set, recording the attempt even when it fails.

        The attempt time is recorded whether the fetch succeeds or fails, so the
        cooldown applies to failures too and a burst of forced refreshes during
        an outage makes one fetch, not one per call. When a fetch fails but a set
        was cached before, that cached set keeps being served rather than the
        request failing outright; when none was ever cached, the failure is
        remembered so a burst during a cold-start outage re-raises it within the
        cooldown rather than fetching again — see :meth:`_held_failure`.

        Raises:
            OidcKeySetError: When the fetch fails and no set was ever cached.
        """
        try:
            key_set = await self._fetch()
        except OidcKeySetError as error:
            self._last_fetch = now
            if self._key_set is not None:
                return self._key_set
            self._last_error = error
            raise
        self._key_set = key_set
        self._last_fetch = now
        self._last_error = None
        return key_set

    def _held_failure(self, now: float) -> OidcKeySetError | None:
        """Return the remembered cold-start failure while its cooldown holds.

        Only a provider that has never cached a set remembers one; within the
        cooldown of that failure it is re-raised without a fetch, so a burst of
        requests during a cold-start outage costs one fetch, not one each.
        """
        if self._key_set is not None or self._last_error is None:
            return None
        if now - self._last_fetch < self._cooldown:
            return self._last_error
        return None

    def _fresh_cached(self, now: float, *, force_refresh: bool) -> KeySet | None:
        """Return the cached set when it still answers this call, else ``None``."""
        if self._key_set is None:
            return None
        window = self._cooldown if force_refresh else self._ttl
        if now - self._last_fetch < window:
            return self._key_set
        return None

    async def _fetch(self) -> KeySet:
        """Discover the ``jwks_uri`` when needed, then fetch and read the set.

        Raises:
            OidcKeySetError: When discovery is needed but no base URI was given —
                an impossible state the constructor forbids, guarded explicitly
                in place of a bare assertion.
        """
        jwks_uri = self._resolved_jwks_uri
        if jwks_uri is None:
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
                usable ``jwks_uri``.
        """
        document = await self._get_json(base_uri.rstrip("/") + _DISCOVERY_PATH)
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise OidcKeySetError(
                f"The discovery document at {base_uri} names no jwks_uri.",
            )
        return jwks_uri

    async def _get_json(self, uri: str) -> dict[str, object]:
        """Fetch ``uri`` and return its JSON body as a mapping.

        Raises:
            OidcKeySetError: When the request fails or the body is not a JSON
                object.
        """
        import httpx  # noqa: PLC0415 -- guarded behind the oidc extra

        try:
            async with self._http_client_factory() as client:
                response = await client.get(uri)
                _ = response.raise_for_status()
                body = cast("object", response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise OidcKeySetError(f"The request to {uri} failed: {error}") from error
        if not isinstance(body, dict):
            raise OidcKeySetError(f"The answer from {uri} is not a JSON object.")
        return cast("dict[str, object]", body)

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
