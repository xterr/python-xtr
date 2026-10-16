"""A session storage that keeps its entries in a cache pool (needs the ``cache`` extra).

Importing this module requires xtr-cache-contracts, brought by the ``cache``
extra of xtr-http-foundation. Importing :mod:`xtr_http_foundation` itself pulls
it in nowhere; only reaching for this module by name does, so an application
that never stores sessions in a pool carries no caching contract.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override

from xtr_http_foundation.exception import InvalidArgumentError, SessionError

from .session_storage_interface import SessionStorageInterface

try:
    import xtr_cache_contracts as _xtr_cache_contracts
except ImportError as _error:  # pragma: no cover -- only an install without the extra walks this.
    raise ImportError(
        "The cache-pool session storage needs xtr-cache-contracts; install the 'cache' extra: "
        'uv add "xtr-http-foundation[cache]".',
    ) from _error
else:
    del _xtr_cache_contracts

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_cache_contracts import CacheItemPoolInterface

__all__ = ["CachePoolSessionStorage"]

# The entry lives under the pool's own name for a session, so several
# applications can share one pool without reading each other's.
_KEY_PREFIX: Final = "session."

# How long an entry lives when the write names no lifetime of its own:
# twenty-four minutes, the span a session is given between requests.
_DEFAULT_TTL: Final = 1440.0


@final
class CachePoolSessionStorage(SessionStorageInterface):
    """Keeps the sessions in any cache pool, as JSON, expiring by the item's own expiry.

    The wire format is JSON and only JSON — a session store is input a
    stranger can influence the shape of, and deserialising such input is
    code execution, which JSON never is; pickle is not an option and will
    not be. A value that cannot round-trip — a set, an object, a
    dictionary keyed by anything but strings — is refused at ``write``,
    loudly, rather than stored and quietly changed.

    Reads are forgiving where writes are not: an entry that no longer
    decodes — expired by the pool, or written by nobody knows what —
    reads as no session, and the session starts fresh. A write the pool
    cannot keep, or a delete it cannot make, is a failure the caller must
    hear: a login that cannot persist must not pretend it did.
    """

    __slots__ = ("_pool", "_ttl")

    def __init__(self, pool: CacheItemPoolInterface, *, ttl: float = _DEFAULT_TTL) -> None:
        """Record the pool the sessions live in and how long an entry lives by default.

        Args:
            pool: The pool the sessions are kept in.
            ttl: How many seconds an entry lives when the write names no
                lifetime of its own.
        """
        self._pool = pool
        self._ttl = ttl

    @override
    async def read(self, session_id: str) -> Mapping[str, object] | None:
        """Return the attributes stored under ``session_id``, or ``None`` when it holds nothing.

        An entry the pool expired answers as nothing, and so does one that
        no longer decodes: the stranger's cookie is theirs to misspell, and
        a store nobody can read is a store no session is in.
        """
        item = await self._pool.get_item(_KEY_PREFIX + session_id)
        if not item.is_hit():
            return None

        value = item.get()
        if not isinstance(value, str):
            return None

        try:
            decoded = cast("object", json.loads(value))
        except ValueError:
            return None

        if not isinstance(decoded, dict):
            return None

        # A decoded JSON object is keyed by strings; the cast says so once
        # rather than at every lookup the caller makes.
        return cast("dict[str, object]", decoded)

    @override
    async def write(self, session_id: str, data: Mapping[str, object], ttl: float | None) -> None:
        """Store ``data`` under ``session_id`` as JSON, to live as long as ``ttl`` names.

        Raises:
            InvalidArgumentError: When a value in ``data`` cannot round-trip
                through JSON.
            SessionError: When the pool cannot keep the entry.
        """
        encoded = _encoded(data)

        item = await self._pool.get_item(_KEY_PREFIX + session_id)
        _ = item.set(encoded).expires_after(ttl if ttl is not None else self._ttl)

        if not await self._pool.save(item):
            raise SessionError(f'The pool could not keep the session "{session_id}".')

    @override
    async def delete(self, session_id: str) -> None:
        """Remove the entry under ``session_id``; an ID holding nothing is fine.

        Raises:
            SessionError: When the pool cannot remove the entry.
        """
        if not await self._pool.delete_item(_KEY_PREFIX + session_id):
            raise SessionError(f'The pool could not remove the session "{session_id}".')


def _encoded(data: Mapping[str, object]) -> str:
    """Return ``data`` as the JSON an entry stores, or refuse what cannot round-trip.

    A value that would come back as something else than it went in — a
    tuple that would return a list, a key that would return a string — is
    not a value the session can rely on reading again, so it is refused
    here, where the caller can still hear it.

    Raises:
        InvalidArgumentError: When ``data`` holds a value JSON cannot give
            back as it was given.
    """
    values = dict(data)

    try:
        encoded = json.dumps(values, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise InvalidArgumentError(
            "A session value must round-trip through JSON — a string, a number, a boolean, "
            f"None, a list or a dictionary of them — and one of them does not: {error}.",
        ) from error

    decoded = cast("object", json.loads(encoded))
    if not isinstance(decoded, dict) or decoded != values:
        raise InvalidArgumentError(
            "A session value must round-trip through JSON — a string, a number, a boolean, "
            "None, a list or a dictionary of them; something in this session is not.",
        )

    return encoded
