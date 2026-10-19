"""Verifying an OIDC ID token's signature against the provider's JWKS."""

from __future__ import annotations

import hmac
import math
from hashlib import sha256
from typing import TYPE_CHECKING, Final, cast, final

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oauth2.jws_algorithms import JwsAlgorithms

from .oidc_jwks import OidcJwks

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from joserfc._keys import KeySetSerialization
    from xtr_cache_contracts import CacheInterface, ItemInterface
    from xtr_clock import ClockInterface
    from xtr_http_client_contracts import HttpClientInterface

    from .oidc_discovery import OidcDiscovery

__all__ = ["OidcSignatureVerifier"]

_ASYMMETRIC: Final = JwsAlgorithms.ASYMMETRIC
"""The asymmetric algorithms a provider's public key may verify — never a MAC one."""


@final
class OidcSignatureVerifier:
    """Verifies the signature of an OIDC ID token against the provider's JWKS.

    The signing keys are discovered from the ``jwks_uri`` of the discovery
    document and cached, as the ``oidc`` access-token handler does. Verifying
    the signature is what OIDC Core 1.0, Section 3.1.3.7, item 6 allows to
    replace with the transport security of the token endpoint request: doing
    it anyway keeps the guarantee independent of the TLS configuration of the
    HTTP client in use.
    """

    __slots__ = (
        "_algorithms",
        "_clock",
        "_discovery",
        "_enforce_key_usage_verification",
        "_http_client",
        "_jwks_cache",
        "_jwks_cache_ttl",
    )

    ROTATION_COOLDOWN: int = 60
    """How long a fetched JWKS is kept before another one is allowed."""

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the discovery, the cache, the client and the four knobs
        self,
        discovery: OidcDiscovery,
        jwks_cache: CacheInterface,
        http_client: HttpClientInterface,
        algorithms: Sequence[str] = ("RS256",),
        jwks_cache_ttl: int = 3600,
        enforce_key_usage_verification: bool = True,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record where the keys come from, which are accepted, and how long they are kept.

        Args:
            discovery: Reads the ``jwks_uri`` off the provider's discovery
                document.
            jwks_cache: Where the fetched keys are kept.
            http_client: The client the JWKS endpoint is reached with.
            algorithms: The signature algorithms accepted to verify the ID
                token (e.g. ``("RS256",)``) — only asymmetric ones, never a
                MAC algorithm.
            jwks_cache_ttl: The JWKS cache lifetime used when the provider
                advertises none.
            enforce_key_usage_verification: Whether only keys explicitly
                designated for signatures are kept.
            clock: What the rotation cooldown is counted on.

        Raises:
            AuthenticationError: When an algorithm names a MAC method, which
                no public key the provider publishes may ever serve.
        """
        for name in algorithms:
            if name not in _ASYMMETRIC:
                raise AuthenticationError(
                    f'Unsupported OIDC ID token signature algorithm "{name}". Supported '
                    f'algorithms are: "{", ".join(_ASYMMETRIC)}".',
                )
        self._discovery = discovery
        self._jwks_cache = jwks_cache
        self._http_client = http_client
        self._algorithms = tuple(algorithms)
        self._jwks_cache_ttl = jwks_cache_ttl
        self._enforce_key_usage_verification = enforce_key_usage_verification
        self._clock = clock if clock is not None else SystemClock()

    async def verify(self, id_token: str) -> dict[str, object]:
        """Verify the signature of the given ID token and return its claims.

        The claims are only structurally valid at this point: they still have
        to be validated by :meth:`OidcIdToken.validate_claims
        <xtr_security_http.oidc.oidc_id_token.OidcIdToken.validate_claims>`.

        Returns:
            The claims of the verified ID token.

        Raises:
            AuthenticationError: When the signature cannot be verified.
        """
        from joserfc import jws  # noqa: PLC0415 -- guarded behind the oidc extra

        try:
            signature = jws.extract_compact(id_token.encode())
        except Exception as error:
            raise AuthenticationError("Invalid ID token format.") from error
        # The "alg" header is checked first, and required: a token announcing
        # an algorithm the provider is not configured for is rejected before
        # any request is sent to its JWKS — and no MAC algorithm is ever
        # accepted, so a public key published by the provider can never be
        # turned into the shared secret of an "HS256" token (key confusion).
        headers = cast("Mapping[str, object]", signature.headers())
        algorithm = headers.get("alg")
        if not isinstance(algorithm, str) or algorithm not in self._algorithms:
            expected = '", "'.join(self._algorithms)
            raise AuthenticationError(
                f'The ID token is not signed with any of the expected algorithms ("{expected}").',
            )
        kid = headers.get("kid")
        if kid is not None and not isinstance(kid, str):
            raise AuthenticationError('The ID token "kid" header must be a string.')
        keys = await self._get_keys(kid)
        if not keys:
            raise AuthenticationError(
                "The OIDC provider published no signing key usable to verify the "
                "ID token signature.",
            )
        key_set = _key_set(keys)
        try:
            token = jwt.decode(id_token, key_set, algorithms=list(self._algorithms))
        except (JoseError, ValueError) as error:
            raise AuthenticationError(
                f"The ID token signature could not be verified: {error}",
            ) from error
        claims = token.claims
        if not isinstance(claims, dict):  # pyright: ignore[reportUnnecessaryIsInstance] -- the library types the payload as an object; a token whose payload is not a JSON object decodes to one
            raise AuthenticationError("Invalid ID token payload.")
        return claims

    async def _get_keys(self, kid: str | None) -> list[dict[str, object]]:
        """Return the cached signing keys of the provider, refetched on an unknown ``kid``.

        A provider that rotated its keys signs with one the cached JWKS does
        not know yet. The refetch is throttled, so that tokens carrying an
        unknown ``kid`` cannot drive one outbound request each.
        """
        # The JWKS carries the very keys the verification relies on, so a
        # discovery document downgrading its transport to plain HTTP must not
        # be honored.
        jwks_uri = await self._discovery.get_secure_endpoint("jwks_uri")
        cache_key = self._cache_key(jwks_uri)
        entry = await self._fetch_entry(jwks_uri, cache_key)
        if (
            kid is not None
            and not _has_key(cast("list[dict[str, object]]", entry["keys"]), kid)
            and int(cast("int", entry["fetched_at"]))
            <= int(self._clock.now().timestamp()) - self.ROTATION_COOLDOWN
        ):
            entry = await self._fetch_entry(jwks_uri, cache_key, beta=math.inf)
        return cast("list[dict[str, object]]", entry["keys"])

    async def _fetch_entry(
        self,
        jwks_uri: str,
        cache_key: str,
        *,
        beta: float | None = None,
    ) -> dict[str, object]:
        """Fetch the JWKS entry from the cache, computing it on a miss."""

        async def compute(item: ItemInterface) -> dict[str, object]:
            keys = await OidcJwks.fetch_keys(
                self._http_client,
                jwks_uri,
                item,
                default_ttl=self._jwks_cache_ttl,
                enforce_key_usage_verification=self._enforce_key_usage_verification,
                clock=self._clock,
            )
            # The JWKS is stored with the time it was fetched, so the rotation
            # refetch above can be throttled without a second cache entry.
            return {"keys": keys, "fetched_at": int(self._clock.now().timestamp())}

        return await self._jwks_cache.get(cache_key, compute, beta=beta)

    def _cache_key(self, jwks_uri: str) -> str:
        """Return the key the JWKS is cached under.

        The strict and lax filters yield different key sets, so each gets its
        own entry; the strictness is kept out of the hash, where a
        ``jwks_uri`` ending with the marker would collide with the other
        strictness of the same endpoint.
        """
        marker = "" if self._enforce_key_usage_verification else "lax."
        return f"oidc_jwks.{marker}{sha256(jwks_uri.encode()).hexdigest()}"


def _key_set(keys: Sequence[Mapping[str, object]]) -> KeySet:
    """Turn the cached key dictionaries into the key set the verifier reads."""
    serialization = cast("KeySetSerialization", cast("object", {"keys": list(keys)}))
    return KeySet.import_key_set(serialization)


def _has_key(keys: Sequence[Mapping[str, object]], kid: str) -> bool:
    """Tell whether a key set holds the key ``kid`` names."""
    for key in keys:
        held = key.get("kid")
        if held is not None and hmac.compare_digest(kid, str(held)):
            return True
    return False
