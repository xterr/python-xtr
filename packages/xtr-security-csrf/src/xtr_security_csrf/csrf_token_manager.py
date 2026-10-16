"""The default token manager: values minted per id, masked on the way out."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .csrf_token import CsrfToken
from .csrf_token_manager_interface import CsrfTokenManagerInterface
from .token_generator.uri_safe_token_generator import UriSafeTokenGenerator

if TYPE_CHECKING:
    from collections.abc import Callable

    from .token_generator.token_generator_interface import TokenGeneratorInterface
    from .token_storage.token_storage_interface import TokenStorageInterface

__all__ = ["CsrfTokenManager"]

# The key a handed-out value is masked with. Long enough that guessing it is
# hopeless, short enough that masking costs nothing.
_MASK_KEY_LENGTH: int = 32
# A masked value is three dot-separated parts: the prefix, the key, the value.
_MASKED_PARTS: int = 3


@final
class CsrfTokenManager(CsrfTokenManagerInterface):
    """Mints a value per token id, stores it, and masks what it hands out.

    What answers for an id is not the value that is stored: every value
    handed out is masked with a fresh key, so two renders of the same form
    carry different strings, and a page that compresses its response cannot
    be made to leak a token by echoing one back. The masked value is all a
    caller ever sees; the stored one is all the manager ever compares.

    The id a value is stored under is the namespace followed by the token
    id, so tokens minted for one origin do not answer for another.
    """

    __slots__ = ("_generator", "_namespace", "_storage")

    def __init__(
        self,
        storage: TokenStorageInterface,
        generator: TokenGeneratorInterface | None = None,
        namespace: str | Callable[[], str] | None = None,
    ) -> None:
        """Record where values are kept, what mints them, and how ids are prefixed.

        Args:
            storage: Where token values are kept, by namespaced id.
            generator: What mints a fresh value; a URI-safe generator when
                nothing is given.
            namespace: The prefix every stored id carries, so tokens minted
                for one origin do not answer for another: a string used as
                it is, or a callable asked each time — the scheme a request
                arrived under can change between calls, so it is read per
                call, not once. ``None`` prefixes nothing.
        """
        self._storage = storage
        self._generator = generator if generator is not None else UriSafeTokenGenerator()
        self._namespace = namespace

    @override
    async def get_token(self, token_id: str) -> CsrfToken:
        """Return the token for ``token_id``, minting one where none is stored.

        A value already stored is handed out again — masked anew, so the
        string differs, but it answers for the same stored value.
        """
        namespaced_id = self._namespaced_id(token_id)
        if await self._storage.has_token(namespaced_id):
            value = await self._storage.get_token(namespaced_id)
        else:
            value = self._generator.generate_token()
            await self._storage.set_token(namespaced_id, value)

        return CsrfToken(token_id, self._randomize(value))

    @override
    async def refresh_token(self, token_id: str) -> CsrfToken:
        """Mint a fresh value for ``token_id``, replacing whatever was stored."""
        namespaced_id = self._namespaced_id(token_id)
        value = self._generator.generate_token()
        await self._storage.set_token(namespaced_id, value)

        return CsrfToken(token_id, self._randomize(value))

    @override
    async def remove_token(self, token_id: str) -> str | None:
        """Drop the value under ``token_id``, returning what it held."""
        return await self._storage.remove_token(self._namespaced_id(token_id))

    @override
    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Tell whether ``token`` carries the value stored under its id.

        The comparison is constant-time, and the value it is handed is never
        trusted to be well-formed: one that does not read as a value this
        manager minted is compared as it came, and does not check out.
        """
        namespaced_id = self._namespaced_id(token.get_id())
        if not await self._storage.has_token(namespaced_id):
            return False

        stored = await self._storage.get_token(namespaced_id)
        return hmac.compare_digest(
            stored.encode(),
            self._derandomize(token.get_value()).encode(),
        )

    def _namespaced_id(self, token_id: str) -> str:
        """Return the id as it is stored: the namespace, then the id."""
        namespace = self._namespace
        if namespace is None:
            return token_id
        if isinstance(namespace, str):
            return namespace + token_id
        return namespace() + token_id

    def _randomize(self, value: str) -> str:
        """Mask ``value`` with a fresh key, so what is handed out differs every call.

        The key travels with the masked value — there is nothing to keep
        between calls — and a short hex prefix of key-derived length heads
        the three parts, so two values of the same token are not even the
        same length. The prefix is never read back; only the key and the
        masked value are.
        """
        key = secrets.token_bytes(_MASK_KEY_LENGTH)
        masked = _xor(value.encode(), key)
        prefix = hashlib.sha256(key).hexdigest()[: 1 + key[0] % 32]
        return f"{prefix}.{_encode(key)}.{_encode(masked)}"

    def _derandomize(self, value: str) -> str:
        """Return the stored value a handed-out string masks, or the string itself.

        Anything that does not read as a masked value — not three parts, a
        part that is not the encoding it claims, bytes that are not text —
        is returned exactly as it came, and so fails the comparison that
        follows. A caller's string is never trusted to be well-formed.
        """
        parts = value.split(".")
        if len(parts) != _MASKED_PARTS:
            return value

        try:
            key = _decode(parts[1])
            if not key:
                return value
            masked = _decode(parts[2])
            return _xor(masked, key).decode()
        except ValueError:
            return value


def _xor(value: bytes, key: bytes) -> bytes:
    """Return ``value`` masked with ``key``, byte for byte.

    The key is repeated until it covers the value, and the result is as
    long as the shorter of the two — the value, once it is.
    """
    if len(value) > len(key):
        key = key * ((len(value) + len(key) - 1) // len(key))
    return bytes(left ^ right for left, right in zip(value, key, strict=False))


def _encode(data: bytes) -> str:
    """Return ``data`` as URI-safe base64, without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(data: str) -> bytes:
    """Return the bytes a URI-safe, unpadded value encodes."""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
