"""One cached entry: its key, its value if there is one, and how long it lives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime, timedelta

    from .metadata import Metadata

__all__ = ["RESERVED_CHARACTERS", "ItemInterface"]

RESERVED_CHARACTERS: Final = "{}()/\\@:"
"""Characters no key and no tag may contain.

Pools use them for their own structure — namespace separators above all — so
a key holding one could reach into another key's space.
"""


@runtime_checkable
class ItemInterface(Protocol):
    """A cache entry as a pool hands it out: looked up, maybe found, ready to save.

    A pool returns an item for every key it is asked about, found or not;
    :meth:`is_hit` tells which. That is what lets ``None`` be a value like any
    other rather than a stand-in for "not cached".

    An item is a plain object in memory. Changing it — :meth:`set`,
    :meth:`expires_after`, :meth:`tag` — reaches the backend only once the item
    is handed back to the pool it came from, through
    :meth:`CacheItemPoolInterface.save
    <xtr_cache_contracts.cache_item_pool_interface.CacheItemPoolInterface.save>`
    or, inside :meth:`CacheInterface.get
    <xtr_cache_contracts.cache_interface.CacheInterface.get>`, by the pool
    itself. The mutators return the item, so calls chain.
    """

    @property
    def key(self) -> str:
        """The key the item is stored under."""
        ...

    def get(self) -> object:
        """Return the value; ``None`` when the item is not a hit.

        Typed ``object`` because a pool holds values of any type: narrow it
        where the type is known. :meth:`CacheInterface.get
        <xtr_cache_contracts.cache_interface.CacheInterface.get>` does that
        for you, through the type its callback returns.
        """
        ...

    def is_hit(self) -> bool:
        """Tell whether the pool had a value for the key when the item was looked up."""
        ...

    def set(self, value: object, /) -> Self:
        """Set the value to save; the item is not saved until the pool is told to."""
        ...

    def expires_at(self, expiration: datetime | None, /) -> Self:
        """Expire the item at ``expiration``; ``None`` falls back to the pool's default."""
        ...

    def expires_after(self, ttl: float | timedelta | None, /) -> Self:
        """Expire the item ``ttl`` from now, in seconds or as a duration.

        A lifetime of zero or less expires the item at once: saving it removes
        whatever the pool held under its key. ``None`` falls back to the
        pool's default.
        """
        ...

    def tag(self, tags: str | Iterable[str], /) -> Self:
        """Add one tag, or several, to invalidate the item by later.

        Tags follow the same rules as keys.

        Raises:
            InvalidArgumentError: When a tag is empty or holds a reserved
                character.
            CacheError: When the item comes from a pool that cannot store
                tags.
        """
        ...

    @property
    def metadata(self) -> Metadata:
        """What the pool stored alongside the value; empty when it stored nothing."""
        ...
