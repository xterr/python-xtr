"""Fetching an OIDC provider's signing keys, and how long they stay fresh.

The ``oidc`` access-token handler and the ``oidc_login`` authenticator both
parse and filter JWKS responses through this helper, so the two OIDC entry
points accept the same key material.
"""

from __future__ import annotations

import json
import re
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Final, cast, final

from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_cache_contracts import ItemInterface
    from xtr_clock import ClockInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface

__all__ = ["OidcJwks"]

_MAX_AGE: Final = re.compile(r"max-age=(\d+)")
"""The ``Cache-Control`` directive that names the freshness lifetime."""

_ENCRYPTION_OPS: Final = frozenset(
    {"encrypt", "decrypt", "wrapKey", "unwrapKey", "deriveKey", "deriveBits"},
)
"""The ``key_ops`` that scope a key to encryption, never to signing."""

_SIGNATURE_OPS: Final = frozenset({"sign", "verify"})
"""The ``key_ops`` that scope a key to signatures."""


@final
class OidcJwks:
    """Reads signing keys out of a JWKS endpoint response, with their TTL.

    A helper rather than a service: both OIDC entry points fetch keys the same
    way, so the one place that knows how lives here, and neither carries the
    other's shape. Nothing here is stateful — the caller owns the cache entry
    the keys land in.
    """

    __slots__ = ()

    MAX_TTL: Final = 30 * 24 * 60 * 60
    """The ceiling on a cache entry's lifetime, so keys are never kept for good."""

    MAX_JWKS_SIZE: Final = 1024 * 1024
    """The most JWKS bytes an answer may hold before it is refused.

    JWKS documents are small; the bound keeps a provider from parking bulk in
    a cache entry every verification reads."""

    @staticmethod
    async def from_response(
        response: HttpResponseInterface,
        enforce_key_usage_verification: bool = True,
        clock: ClockInterface | None = None,
    ) -> tuple[list[dict[str, object]], int | None]:
        """Extract the signing keys a response carries, with their remaining TTL.

        The TTL, in seconds, is what remains of the freshness lifetime the
        provider advertises through ``Cache-Control: max-age`` or ``Expires``,
        once the current age of the response is subtracted (RFC 9111, Section
        4.2). It is ``None`` when the provider advertises none, or the response
        is already stale. With ``Expires`` the lifetime is counted from the
        ``Date`` of the response, or from the clock without one.

        Args:
            response: The JWKS endpoint's answer.
            enforce_key_usage_verification: When true (the default, strict),
                only JWKs whose ``use`` is ``sig`` or whose ``key_ops`` holds
                ``sign``/``verify`` are kept. When false (lax), JWKs missing
                both are kept too; JWKs explicitly scoped to encryption are
                dropped either way.
            clock: What the response's age is counted from.

        Returns:
            The filtered signing keys, and the TTL the answer leaves.

        Raises:
            AuthenticationError: When the JWKS cannot be fetched, is too
                large, or does not decode.
        """
        reader = clock if clock is not None else SystemClock()
        content = await _content(response)
        if len(content) > OidcJwks.MAX_JWKS_SIZE:
            raise AuthenticationError(
                "The OIDC provider JWKS exceeds the maximum size of 1 MiB.",
            )
        try:
            document = cast("object", json.loads(content))
        except ValueError as error:
            raise AuthenticationError(
                f"The OIDC provider JWKS could not be fetched: invalid JSON: {error}",
            ) from error
        members = cast("dict[str, object]", document) if isinstance(document, dict) else {}
        keys = members.get("keys")
        raw = (
            [
                cast("dict[str, object]", key)
                for key in cast("Sequence[object]", keys)
                if isinstance(key, dict)
            ]
            if isinstance(keys, list)
            else []
        )
        return (
            _filter_signature_keys(raw, enforce_key_usage_verification),
            _remaining_ttl(response, reader),
        )

    @staticmethod
    async def fetch_keys(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the client, the endpoint, the item and the three knobs
        http_client: HttpClientInterface,
        jwks_uri: str,
        item: ItemInterface,
        default_ttl: int = 3600,
        enforce_key_usage_verification: bool = True,
        clock: ClockInterface | None = None,
    ) -> list[dict[str, object]]:
        """Fetch the provider's signing keys from ``jwks_uri`` into a cache item.

        The item's lifetime is what the response headers leave, capped at
        :attr:`MAX_TTL`, or ``default_ttl`` when the headers name nothing.

        Args:
            http_client: The client the JWKS endpoint is reached with.
            jwks_uri: The endpoint the keys are fetched from.
            item: The cache entry the keys and their lifetime land in.
            default_ttl: The lifetime used when the provider advertises none.
            enforce_key_usage_verification: As in :meth:`from_response`.
            clock: What the response's age is counted from.

        Returns:
            The filtered signing keys.

        Raises:
            AuthenticationError: When the JWKS cannot be fetched or decoded.
        """
        try:
            response = await http_client.request("GET", jwks_uri, max_redirects=0)
        except Exception as error:
            raise AuthenticationError(
                f"The OIDC provider JWKS could not be fetched: {error}",
            ) from error
        keys, ttl = await OidcJwks.from_response(
            response,
            enforce_key_usage_verification,
            clock,
        )
        _ = item.expires_after(min(ttl if ttl is not None else default_ttl, OidcJwks.MAX_TTL))
        return keys


async def _content(response: HttpResponseInterface) -> bytes:
    """Read a response's body, turning transport failures into the OIDC refusal.

    No redirect is followed on the way: the endpoint was weighed where its
    announcement was read from, and a redirect would change where the keys
    come from.
    """
    try:
        async with response:
            return await response.get_content()
    except Exception as error:
        raise AuthenticationError(
            f"The OIDC provider JWKS could not be fetched: {error}",
        ) from error


def _remaining_ttl(response: HttpResponseInterface, clock: ClockInterface) -> int | None:
    """Return what remains of the freshness lifetime a response's headers advertise.

    RFC 9111, Section 4.2.3: the current age of the response — the ``Age``
    header, or the time since the response's own ``Date`` — is subtracted from
    the advertised lifetime, and nothing is left of a stale answer.
    """
    now = int(clock.now().timestamp())
    date = _http_date(response, "date")
    age = _header_int(response, "age")
    match = _header(response, "cache-control")
    ttl: int | None = None
    if match is not None:
        max_age = _MAX_AGE.search(match)
        if max_age is not None:
            ttl = int(max_age.group(1))
    if ttl is None:
        expires = _http_date(response, "expires")
        if expires is not None:
            ttl = expires - (date if date is not None else now)
    if ttl is None:
        return None
    current_age = max(now - date if date is not None else 0, age)
    return ttl - current_age if ttl - current_age > 0 else None


def _filter_signature_keys(
    keys: Sequence[Mapping[str, object]],
    enforce_key_usage_verification: bool,
) -> list[dict[str, object]]:
    """Keep only the keys a signature may be verified with.

    RFC 7517 makes ``kty`` mandatory, and both it and ``kid`` strings. An
    entry breaking that is unusable, and worse than useless: one without a
    ``kty`` — or with a ``kid`` that is not a string — makes the key set
    reader throw, so a single odd entry would fail every verification with an
    error instead of an authentication failure.
    """
    kept: list[dict[str, object]] = []
    for jwk in keys:
        kty = jwk.get("kty")
        if not isinstance(kty, str) or not kty:
            continue
        kid = jwk.get("kid")
        if kid is not None and not isinstance(kid, str):
            continue
        if _is_signature_key(jwk, enforce_key_usage_verification):
            kept.append(dict(jwk))
    return kept


def _is_signature_key(jwk: Mapping[str, object], strict: bool) -> bool:
    """Tell whether one JWK may verify a signature, under one strictness."""
    use = jwk.get("use")
    ops = jwk.get("key_ops")
    ops = cast("Sequence[object]", ops) if isinstance(ops, list) else None
    if strict:
        if use == "sig":
            return True
        return bool(ops) and bool(_SIGNATURE_OPS.intersection(_string_ops(ops)))
    if use == "enc":
        return False
    if ops is not None:
        has_enc = bool(_ENCRYPTION_OPS.intersection(_string_ops(ops)))
        has_sig = bool(_SIGNATURE_OPS.intersection(_string_ops(ops)))
        if has_enc and not has_sig:
            return False
    return True


def _string_ops(ops: Sequence[object]) -> set[str]:
    """Read the ``key_ops`` a JWK carries as the strings they must be."""
    return {op for op in ops if isinstance(op, str)}


def _header(response: HttpResponseInterface, name: str) -> str | None:
    """Return a response header's first value, or ``None``."""
    values = response.get_header(name)
    return values[0] if values else None


def _header_int(response: HttpResponseInterface, name: str) -> int:
    """Read a response header as an integer, or ``0`` when it names none."""
    value = _header(response, name)
    try:
        return int(value) if value is not None else 0
    except ValueError:
        return 0


def _http_date(response: HttpResponseInterface, name: str) -> int | None:
    """Read a response header as an HTTP date's Unix timestamp, or ``None``."""
    value = _header(response, name)
    if value is None:
        return None
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except (TypeError, ValueError):
        return None
