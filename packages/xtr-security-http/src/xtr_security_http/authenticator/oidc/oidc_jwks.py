"""The keys a third-party OIDC token is verified against, and a fixed source of them."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol, cast, final, runtime_checkable

from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from joserfc._keys import KeySetSerialization

__all__ = ["OidcKeySetProviderInterface", "StaticOidcKeySetProvider"]


@runtime_checkable
class OidcKeySetProviderInterface(Protocol):
    """Supplies the public keys a third-party OIDC token is verified against.

    A token names its key by ``kid``; the whole set is handed to the verifier,
    which picks the one that matches. A remote provider caches the set, and
    ``force_refresh`` asks it to fetch again — the handler does so once when a
    token names a ``kid`` the cached set does not hold, a key rotation the
    provider had not yet seen.
    """

    async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
        """Return the key set a token is verified against.

        Args:
            force_refresh: Fetch a fresh set rather than answer from the cache,
                subject to a provider's own cooldown.

        Raises:
            OidcKeySetError: When the key set cannot be fetched, discovered or
                read.
        """
        ...


@final
class StaticOidcKeySetProvider(OidcKeySetProviderInterface):
    """Holds a fixed key set read from a JWKS document.

    For an issuer whose keys are known ahead of time and pinned in the
    configuration, rather than fetched. The document is read once, as the
    provider is made, so a malformed one fails here rather than at the first
    token; :meth:`get_key_set` always answers the same set, ``force_refresh``
    or not, since there is nowhere to refresh from.
    """

    __slots__ = ("_key_set",)

    def __init__(self, jwks_json: str | Mapping[str, object]) -> None:
        """Build the key set from ``jwks_json``, a JWKS string or mapping.

        Raises:
            InvalidArgumentError: When the document is not a readable JWK set.
        """
        self._key_set = _read_key_set(jwks_json)

    @override
    async def get_key_set(self, *, force_refresh: bool = False) -> KeySet:
        """Return the fixed key set, whether or not a refresh is asked for."""
        del force_refresh
        return self._key_set


def _read_key_set(jwks_json: str | Mapping[str, object]) -> KeySet:
    """Turn a JWKS string or mapping into a joserfc key set.

    Raises:
        InvalidArgumentError: When the document is not a readable JWK set.
    """
    try:
        document: object = json.loads(jwks_json) if isinstance(jwks_json, str) else dict(jwks_json)
        if not isinstance(document, dict):
            raise InvalidArgumentError("A JWK set document must be a JSON object.")
        serialization = cast("KeySetSerialization", cast("object", document))
        return KeySet.import_key_set(serialization)
    except (JoseError, ValueError) as error:
        raise InvalidArgumentError(f"The JWK set document could not be read: {error}") from error
