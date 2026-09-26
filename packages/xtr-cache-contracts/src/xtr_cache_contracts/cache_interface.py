"""Read a value from a cache, computing and storing it when it is missing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from .callback import Callback
    from .metadata import Metadata

__all__ = ["CacheInterface"]

_T = TypeVar("_T")


@runtime_checkable
class CacheInterface(Protocol):
    """Covers most caching needs in two calls: fetch-or-compute, and forget.

    The type code that caches should depend on. Instead of checking for a
    value, computing it on a miss and saving it — three steps, with a race
    between each — a caller hands :meth:`get` the function that computes the
    value, and the cache decides when to call it:

    ```python
    profile = await cache.get(f"profile.{user_id}", load_profile)
    ```

    Deciding in one place is what lets an implementation protect a backend
    from a stampede — many callers missing the same key at once, all
    computing it — by computing it once and sharing the result, or by
    refreshing a value shortly before it expires.
    """

    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: Metadata | None = None,
    ) -> _T:
        """Return the value cached under ``key``, computing and saving it on a miss.

        On a miss ``callback`` is awaited with the item for ``key``; what it
        returns is saved and returned. A value that cannot be saved is still
        returned — the cache is an optimisation, not a dependency — and
        reported through ``metadata``.

        On a hit the stored value is returned as the type ``callback`` would
        have returned: keep one key for one type.

        Args:
            key: The key the value is stored under.
            callback: Computes the value on a miss.
            beta: How eagerly to recompute a value before it expires. The
                chance grows as expiry nears, and faster the larger ``beta``
                is. ``0`` disables early recomputation; ``math.inf`` forces
                recomputation now. ``None`` lets the implementation choose,
                ``1.0`` being the usual choice.
            metadata: A mapping to fill with the metadata of the value — see
                :class:`~xtr_cache_contracts.metadata.Metadata` — plus
                ``save_failed`` when a computed value could not be saved.
                Keys already in it are overwritten, not cleared.

        Returns:
            The cached value, or the one ``callback`` computed.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key, or ``beta``
                is negative.
        """
        ...

    async def delete(self, key: str, /) -> bool:
        """Remove the value under ``key``; a key holding nothing is fine.

        Returns:
            ``False`` when the backend failed; ``True`` otherwise.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key.
        """
        ...
