"""An item pool kept in a dictionary, to test what is built on the contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Self, final

from typing_extensions import override
from xtr_clock import now

from xtr_cache_contracts import (
    RESERVED_CHARACTERS,
    CacheItemPoolInterface,
    CacheMixin,
    InvalidArgumentError,
    ItemInterface,
    Metadata,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

__all__ = ["InMemoryItem", "InMemoryPool"]


def _validate(key: str) -> str:
    if not key or any(character in RESERVED_CHARACTERS for character in key):
        raise InvalidArgumentError(f"{key!r} is not a valid key")

    return key


@dataclass(slots=True)
class _Entry:
    value: object
    expiry: float | None
    metadata: Metadata = field(default_factory=Metadata)


@final
class InMemoryItem(ItemInterface):
    """An item that remembers the pool it came from."""

    __slots__ = ("_expiry", "_hit", "_key", "_metadata", "_tags", "_value", "pool")

    def __init__(
        self,
        pool: InMemoryPool,
        key: str,
        value: object,
        *,
        hit: bool,
        metadata: Metadata,
    ) -> None:
        self.pool = pool
        self._key = key
        self._value = value
        self._hit = hit
        self._metadata = metadata
        self._expiry: float | None = None
        self._tags: list[str] = []

    @property
    @override
    def key(self) -> str:
        return self._key

    @property
    def expiry(self) -> float | None:
        """The Unix timestamp the item expires at, when one was set."""
        return self._expiry

    @property
    def tags(self) -> tuple[str, ...]:
        """The tags added since the item was read."""
        return tuple(self._tags)

    @override
    def get(self) -> object:
        return self._value

    @override
    def is_hit(self) -> bool:
        return self._hit

    @override
    def set(self, value: object, /) -> Self:
        self._value = value
        return self

    @override
    def expires_at(self, expiration: datetime | None, /) -> Self:
        self._expiry = None if expiration is None else expiration.timestamp()
        return self

    @override
    def expires_after(self, ttl: float | timedelta | None, /) -> Self:
        if ttl is None:
            self._expiry = None
            return self

        seconds = ttl.total_seconds() if isinstance(ttl, timedelta) else ttl
        self._expiry = now().timestamp() + seconds
        return self

    @override
    def tag(self, tags: str | Iterable[str], /) -> Self:
        for tag in [tags] if isinstance(tags, str) else tags:
            if tag not in self._tags:
                self._tags.append(_validate(tag))
        return self

    @property
    @override
    def metadata(self) -> Metadata:
        return self._metadata


class InMemoryPool(CacheItemPoolInterface, CacheMixin):
    """Keeps items in a dictionary, with a switch that makes every save fail."""

    def __init__(self) -> None:
        self.fail_saves: bool = False
        self._entries: dict[str, _Entry] = {}
        self._deferred: dict[str, InMemoryItem] = {}

    def seed(self, key: str, value: object, metadata: Metadata) -> None:
        """Store ``value`` as if it had been saved with ``metadata``, expiring when it says."""
        self._entries[_validate(key)] = _Entry(value, metadata.get("expiry"), metadata)

    @override
    async def get_item(self, key: str, /) -> InMemoryItem:
        _ = _validate(key)
        if key in self._deferred:
            _ = await self.commit()

        entry = self._entries.get(key)
        if entry is not None and entry.expiry is not None and entry.expiry <= now().timestamp():
            del self._entries[key]
            entry = None

        if entry is None:
            return InMemoryItem(self, key, None, hit=False, metadata=Metadata())

        return InMemoryItem(self, key, entry.value, hit=True, metadata=Metadata(**entry.metadata))

    @override
    async def get_items(self, keys: Iterable[str], /) -> Mapping[str, InMemoryItem]:
        return {key: await self.get_item(key) for key in keys}

    @override
    async def has_item(self, key: str, /) -> bool:
        return (await self.get_item(key)).is_hit()

    @override
    async def clear(self, prefix: str = "") -> bool:
        self._entries = {k: v for k, v in self._entries.items() if not k.startswith(prefix)}
        self._deferred = {k: v for k, v in self._deferred.items() if not k.startswith(prefix)}
        return True

    @override
    async def delete_item(self, key: str, /) -> bool:
        return await self.delete_items([key])

    @override
    async def delete_items(self, keys: Iterable[str], /) -> bool:
        for key in keys:
            _ = self._entries.pop(_validate(key), None)
            _ = self._deferred.pop(key, None)
        return True

    @override
    async def save(self, item: ItemInterface, /) -> bool:
        if not isinstance(item, InMemoryItem) or item.pool is not self or self.fail_saves:
            return False

        if item.expiry is not None and item.expiry <= now().timestamp():
            _ = self._entries.pop(item.key, None)
            return True

        metadata = Metadata()
        if item.expiry is not None:
            metadata["expiry"] = item.expiry
        if item.tags:
            metadata["tags"] = item.tags
        self._entries[item.key] = _Entry(item.get(), item.expiry, metadata)
        return True

    @override
    async def save_deferred(self, item: ItemInterface, /) -> bool:
        if not isinstance(item, InMemoryItem) or item.pool is not self:
            return False

        self._deferred[item.key] = item
        return True

    @override
    async def commit(self) -> bool:
        deferred, self._deferred = self._deferred, {}
        saved = [await self.save(item) for item in deferred.values()]
        return all(saved)
