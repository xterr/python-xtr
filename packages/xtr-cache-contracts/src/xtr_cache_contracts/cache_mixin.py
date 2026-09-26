"""Fetch-or-compute, for a class that already knows how to read, save and delete items."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from random import random
from typing import TYPE_CHECKING, Final, TypeVar, cast

from typing_extensions import override
from xtr_clock import now

from .cache_interface import CacheInterface
from .exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from .callback import Callback
    from .item_interface import ItemInterface
    from .metadata import Metadata

__all__ = ["CacheMixin"]

_T = TypeVar("_T")

_DEFAULT_BETA: Final = 1.0
"""The ``beta`` used when none is given; what the early-expiry model is tuned for."""


class CacheMixin(CacheInterface, ABC):
    """Implements :class:`~xtr_cache_contracts.cache_interface.CacheInterface` on a pool.

    A class that implements
    :class:`~xtr_cache_contracts.cache_item_pool_interface.CacheItemPoolInterface`
    derives from this too and gets :meth:`get` and :meth:`delete` built on its
    own :meth:`get_item`, :meth:`save` and :meth:`delete_item`. List it after
    the pool's interfaces, so the pool's own methods are the ones found.

    Early recomputation: a hit whose metadata says when it expires and how
    long it took to compute may be recomputed before it expires, with a
    chance that grows as expiry nears. Under load, one caller refreshes the
    value while the others still read the old one, rather than all of them
    missing at the same moment. A value stored without that metadata is only
    recomputed once it has expired. The time is read from the clock in force
    (:func:`xtr_clock.now`), so freezing it in a test freezes this too.

    What this does not do is make concurrent misses on one key compute once:
    that needs a lock or a shared in-flight computation, and is the
    implementation's to add by overriding :meth:`get`.
    """

    @abstractmethod
    async def get_item(self, key: str, /) -> ItemInterface:
        """Return the item for ``key``, a hit or a miss."""

    @abstractmethod
    async def save(self, item: ItemInterface, /) -> bool:
        """Store ``item`` now; ``False`` when that failed."""

    @abstractmethod
    async def delete_item(self, key: str, /) -> bool:
        """Remove the item under ``key``; ``False`` when that failed."""

    @override
    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: Metadata | None = None,
    ) -> _T:
        """Return the value under ``key``, computing and saving it on a miss.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key, or ``beta``
                is negative or not a number.
        """
        beta = _DEFAULT_BETA if beta is None else beta
        # Written this way round so that NaN, which compares false to everything, is refused too.
        if not beta >= 0:
            raise InvalidArgumentError(f"beta must be zero or more, got {beta!r}")

        item = await self.get_item(key)
        found = item.metadata
        if metadata is not None:
            metadata.update(found)

        if (
            item.is_hit()
            and not math.isinf(beta)
            and not _elect_early_recomputation(item, found, beta)
        ):
            # The key's value was stored by the same callback type, which is the caller's promise.
            return cast("_T", item.get())

        value = await callback(item)
        _ = item.set(value)
        if not await self.save(item) and metadata is not None:
            metadata["save_failed"] = True

        return value

    @override
    async def delete(self, key: str, /) -> bool:
        """Remove the value under ``key``; ``False`` when the backend failed."""
        return await self.delete_item(key)


def _elect_early_recomputation(item: ItemInterface, metadata: Metadata, beta: float) -> bool:
    """Decide whether a hit should be recomputed now, ahead of its expiry.

    The value is recomputed when its expiry falls within a random span ahead
    of now — the time it took to compute, scaled by ``beta`` and by an
    exponentially distributed factor. Values that are slow to compute are
    refreshed earlier, and callers spread over time do not all pick the same
    moment. An elected item has its expiry reset, so the pool's default
    lifetime applies to the recomputed value unless the callback sets one.
    """
    expiry = metadata.get("expiry")
    ctime = metadata.get("ctime")
    if not expiry or not ctime:
        return False

    if expiry > now().timestamp() - ctime / 1000 * beta * math.log(_draw()):
        return False

    _ = item.expires_at(None)

    return True


def _draw() -> float:
    """Return a random number in ``(0, 1]``, so its logarithm is always defined."""
    return 1.0 - random()  # noqa: S311 — spreads recomputation over time; nothing here is a secret.
