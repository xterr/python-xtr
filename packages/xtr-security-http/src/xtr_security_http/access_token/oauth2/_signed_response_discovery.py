"""Reading the verifying keys of a signed introspection response off the issuer's metadata.

The discovery machinery — the RFC 8414 metadata URL, the document the
``jwks_uri`` is read from, the keys that URI serves, and the cache and
freshness arithmetic that keep them — is a concern of its own beside the
introspection handler: the handler decides when a response must be signed
and which algorithms may verify it, and everything the keys are read
through lives here.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING, Final, cast, final
from urllib.parse import urlsplit

from xtr_security_core.exception import BadMethodCallError

if TYPE_CHECKING:
    from joserfc._keys import KeySetSerialization
    from joserfc.jwk import KeySet
    from xtr_cache_contracts import CacheInterface, ItemInterface
    from xtr_clock import ClockInterface
    from xtr_http_client_contracts import HttpClientInterface

__all__ = [
    "SignedResponseDiscovery",
    "metadata_url",
]

_METADATA_PATH: Final = "/.well-known/oauth-authorization-server"
"""RFC 8414 Section 3: the well-known path of the authorization server metadata."""


def metadata_url(issuer: str) -> str:
    """Build the RFC 8414 Section 3 metadata URL of an issuer.

    The well-known path is inserted between the host component and the path
    of the issuer identifier, so one host can serve the metadata of several
    authorization servers.
    """
    parts = urlsplit(issuer.rstrip("/"))
    if not parts.scheme or not parts.hostname:
        raise BadMethodCallError(
            'The "issuer" of the authorization server must be an absolute URL to '
            f'read its metadata, "{issuer}" given.',
        )
    return f"{parts.scheme}://{parts.netloc}{_METADATA_PATH}{parts.path}"


def _key_set(keys: object) -> KeySet:
    """Turn the cached key dictionaries into the key set the verifier reads."""
    from joserfc.jwk import (  # noqa: PLC0415 -- guarded behind the oidc extra
        KeySet as JoserfcKeySet,
    )

    serialization = cast("KeySetSerialization", cast("object", {"keys": keys}))
    return JoserfcKeySet.import_key_set(serialization)


@final
class SignedResponseDiscovery:
    """Reads the verifying keys of a signed introspection response.

    The keys are the ones the ``jwks_uri`` of the issuer's metadata document
    names, kept in the cache for as long as the response headers' freshness
    arithmetic leaves, capped at what the JWKS reader allows. Which
    algorithms this resource server accepts stays its own decision, so that
    an authorization server cannot widen it by announcing more.
    """

    __slots__ = ("_cache", "_cache_key", "_client", "_clock", "_discovery")

    def __init__(
        self,
        issuer: str | None,
        client: HttpClientInterface,
        cache: CacheInterface,
        cache_key: str,
        clock: ClockInterface,
    ) -> None:
        """Record where the issuer's metadata is read from and what reads the keys.

        Raises:
            BadMethodCallError: When no ``issuer`` was given, since RFC 8414
                Section 3 derives the metadata URL from it, or when it is
                not an absolute URL.
            ImportError: When joserfc, which verifies the responses, is not
                installed — the ``oidc`` extra carries it.
        """
        from xtr_security_http.oidc.oidc_discovery import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcDiscovery,
        )

        if issuer is None:
            raise BadMethodCallError(
                'The "issuer" of the authorization server is required to read its '
                "metadata, since RFC 8414 Section 3 derives the metadata URL from it.",
            )
        if find_spec("joserfc") is None:  # pragma: no cover -- the extra carries it
            raise ImportError(
                "Verifying signed introspection responses needs joserfc; install the "
                "'oidc' extra: uv add \"xtr-security-http[oidc]\".",
            )
        self._client = client
        self._cache = cache
        self._cache_key = cache_key
        self._clock = clock
        self._discovery = OidcDiscovery(
            client,
            cache,
            metadata_url(issuer),
            issuer,
            cache_key=f"{cache_key}.document",
            checked_endpoints=("jwks_uri",),
        )

    async def resolve_keyset(self) -> KeySet:
        """Return the keys a signed response is verified against.

        The keys come from the cache when it holds them, and are read off the
        ``jwks_uri`` the metadata announces otherwise.
        """
        keys = await self._cache.get(self._cache_key, self._compute_keys)
        return _key_set(keys)

    async def _compute_keys(self, item: ItemInterface) -> list[dict[str, object]]:
        """Fetch the verifying keys off the ``jwks_uri`` the metadata announces.

        The entry lives for what the response headers' freshness arithmetic
        leaves, capped at what the JWKS reader allows, or the default when the
        headers name nothing.
        """
        from xtr_security_http.oidc.oidc_jwks import (  # noqa: PLC0415 -- guarded behind the oidc extra
            OidcJwks,
        )

        jwks_uri = (await self._discovery.get_configuration()).get("jwks_uri")
        keys, ttl = await OidcJwks.from_response(
            await self._client.request(
                "GET",
                jwks_uri if isinstance(jwks_uri, str) else "",
                max_redirects=0,
            ),
            enforce_key_usage_verification=True,
            clock=self._clock,
        )
        _ = item.expires_after(min(ttl if ttl is not None else 3600, OidcJwks.MAX_TTL))
        return keys
