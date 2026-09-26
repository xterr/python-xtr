"""A store of cache items: look them up, save them, delete them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .item_interface import ItemInterface

__all__ = ["CacheItemPoolInterface"]


@runtime_checkable
class CacheItemPoolInterface(Protocol):
    """The item-level view of a cache, for code that needs more than fetch-or-compute.

    Most code should depend on
    :class:`~xtr_cache_contracts.cache_interface.CacheInterface`. This is the
    level below it: a hit told apart from a miss, several keys read in one
    round trip, writes batched until :meth:`commit`. It is also the level a
    backend implements — :class:`~xtr_cache_contracts.cache_mixin.CacheMixin`
    builds the fetch-or-compute contract on top of it.

    The rules:

    - A key is a non-empty string without any of
      :data:`~xtr_cache_contracts.item_interface.RESERVED_CHARACTERS`. Letters,
      digits, ``_`` and ``.`` up to 64 characters work everywhere; a pool may
      accept more. A key it refuses raises
      :class:`~xtr_cache_contracts.exception.InvalidArgumentError`.
    - A backend failure never raises: the call returns ``False``, or reads as
      a miss, and the implementation logs it. Code that caches keeps working
      when the cache does not.
    - An item is saved only into the pool that handed it out.
    """

    async def get_item(self, key: str, /) -> ItemInterface:
        """Return the item for ``key``, a hit or a miss.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key.
        """
        ...

    async def get_items(self, keys: Iterable[str], /) -> Mapping[str, ItemInterface]:
        """Return an item for each of ``keys``, hits and misses alike, in the order asked.

        Raises:
            InvalidArgumentError: When a key is not a valid key.
        """
        ...

    async def has_item(self, key: str, /) -> bool:
        """Tell whether the pool holds a value for ``key``.

        Do not follow it with :meth:`get_item`: the value may expire in
        between. Read the item and ask it
        :meth:`~xtr_cache_contracts.item_interface.ItemInterface.is_hit`
        instead.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key.
        """
        ...

    async def clear(self, prefix: str = "") -> bool:
        """Remove every item whose key starts with ``prefix``; every item, by default.

        Items saved as deferred and not yet committed are dropped too.

        Returns:
            ``False`` when the backend failed; ``True`` otherwise.
        """
        ...

    async def delete_item(self, key: str, /) -> bool:
        """Remove the item under ``key``; a key holding nothing is fine.

        Returns:
            ``False`` when the backend failed; ``True`` otherwise.

        Raises:
            InvalidArgumentError: When ``key`` is not a valid key.
        """
        ...

    async def delete_items(self, keys: Iterable[str], /) -> bool:
        """Remove the items under ``keys``.

        Returns:
            ``False`` when the backend failed for any of them; ``True``
            otherwise.

        Raises:
            InvalidArgumentError: When a key is not a valid key.
        """
        ...

    async def save(self, item: ItemInterface, /) -> bool:
        """Store ``item`` now.

        Returns:
            ``False`` when the backend failed, or when ``item`` came from
            another pool; ``True`` otherwise.
        """
        ...

    async def save_deferred(self, item: ItemInterface, /) -> bool:
        """Queue ``item`` to be stored by the next :meth:`commit`.

        Reading a queued item's key from this pool commits the queue first, so
        the pool never answers with a value older than one it was given.
        Nothing commits the queue on its own when the pool is discarded: call
        :meth:`commit`.

        Returns:
            ``False`` when ``item`` came from another pool; ``True`` otherwise.
        """
        ...

    async def commit(self) -> bool:
        """Store every item queued by :meth:`save_deferred`.

        Returns:
            ``False`` when the backend failed for any of them; ``True``
            otherwise.
        """
        ...
